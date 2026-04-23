"""
Global ACO dispatcher.

One checkout at a time across all tasks (auto + manual). Each call:
  1. Re-validates the cart (pending, not expired)
  2. Picks next unused profile from the pool (or uses forced profile from manual trigger)
  3. Commits `running` status + profile assignment to prevent double-fire
  4. Runs the three-step billing/payment/order flow via run_single_checkout
  5. On failure, resets status back to pending so the cart stays manually usable

Profile "used" state is derived from completed CartSessions for the same event_id —
no separate table, auto-resets on new event.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..models import BillingProfile, CartSession
from ..database import SessionLocal
from .checkout import AutoCheckout
from .discord import send_discord_aco_update

logger = logging.getLogger(__name__)


def used_profile_ids_for_event(event_id: Optional[str], db: Session) -> set[int]:
    """Profile IDs that already completed a checkout for this event."""
    if not event_id:
        return set()
    rows = (
        db.query(CartSession.billing_profile_id)
        .filter(
            CartSession.event_id == event_id,
            CartSession.checkout_status == "completed",
            CartSession.billing_profile_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


async def _log(task_id: Optional[int], level: str, message: str, db: Session):
    """Best-effort log through TaskManager (same as monitor._log)."""
    from .monitor import task_manager  # noqa: WPS433 — lazy to avoid circular import
    if task_id is not None:
        try:
            await task_manager._log(task_id, level, message, db)
            return
        except Exception:
            pass
    logger.log(
        {"error": logging.ERROR, "warning": logging.WARNING, "success": logging.INFO}.get(level, logging.INFO),
        f"[ACO cart-log task={task_id}] {message}",
    )


async def _broadcast_cart_update(cart: CartSession):
    """Push a cart_update WS message so the Carts view animates live."""
    from .monitor import task_manager  # noqa: WPS433
    try:
        await task_manager.broadcast({
            "type": "cart_update",
            "data": {
                "cart_id": cart.id,
                "token": cart.token,
                "checkout_status": cart.checkout_status,
                "billing_profile_id": cart.billing_profile_id,
                "invoice_url": cart.invoice_url,
                "checkout_error": cart.checkout_error,
            },
        })
    except Exception:
        pass


async def run_single_checkout(cart: CartSession, profile: BillingProfile, db: Session) -> bool:
    """Run the three-step checkout for one (cart, profile). Returns True on completed order.

    Moved out of MonitorEngine so it can be invoked from the API as well.
    All logs are piped through TaskManager._log when a task_id is set on the cart.
    """
    task_id = cart.task_id
    product_url = cart.product_url

    async with AutoCheckout(cart.cookie_name, cart.cookie_value) as aco:
        # Step 1 — billing
        result = await aco.submit_billing(profile)
        if not result.success:
            await _log(task_id, "error", f"ACO: Billing failed: {result.message}", db)
            cart.checkout_status = "failed"
            cart.checkout_error = result.message
            db.commit()
            await _broadcast_cart_update(cart)
            await send_discord_aco_update(product_url, "failed", f"Cart {cart.id}: {result.message}")
            return False

        await _log(task_id, "info", f"ACO: Billing submitted. PI: {result.payment_intent_id}", db)
        cart.checkout_status = "billing_done"
        cart.payment_intent_id = result.payment_intent_id
        cart.client_secret = result.client_secret
        db.commit()
        await _broadcast_cart_update(cart)

        pi_id = result.payment_intent_id
        client_secret = result.client_secret

        # Step 2 — payment confirm
        await _log(task_id, "info", "ACO: Confirming payment via Stripe.js browser...", db)
        await send_discord_aco_update(
            product_url, "3ds_waiting",
            f"Cart {cart.id}: Payment processing — approve 3DS if prompted!",
        )

        result = await aco.confirm_payment(profile, pi_id, client_secret)
        if not result.success:
            await _log(task_id, "error", f"ACO: Payment failed: {result.message}", db)
            cart.checkout_status = "failed"
            cart.checkout_error = result.message
            db.commit()
            await _broadcast_cart_update(cart)
            await send_discord_aco_update(product_url, "failed", f"Cart {cart.id}: {result.message}")
            return False

        pm_id = result.payment_method_id
        await _log(task_id, "success", "ACO: Payment confirmed!", db)

        cart.checkout_status = "payment_confirmed"
        cart.payment_method_id = pm_id
        db.commit()
        await _broadcast_cart_update(cart)

        # Step 3 — place order
        cardholder = f"{profile.firstname} {profile.lastname}"
        order_result = await aco.place_order(pi_id, pm_id, cardholder)

        if order_result.success:
            await _log(task_id, "success", f"ACO: Cart {cart.id} — {order_result.message}", db)
            cart.checkout_status = "completed"
            if order_result.invoice_url:
                cart.invoice_url = order_result.invoice_url
                await _log(task_id, "info", f"ACO: Invoice URL saved for cart {cart.id}", db)
            db.commit()
            await _broadcast_cart_update(cart)
            await send_discord_aco_update(
                product_url, "completed",
                profile_name=profile.name, profile_email=profile.email,
                order_ref=order_result.order_ref, cart_id=str(cart.id),
            )
            from .monitor import task_manager  # noqa: WPS433
            if task_id is not None:
                try:
                    await task_manager.broadcast({
                        "type": "task_update",
                        "data": {"task_id": task_id, "status": "checkout_complete"},
                    })
                except Exception:
                    pass
            return True

        await _log(task_id, "error", f"ACO: Cart {cart.id} order failed: {order_result.message}", db)
        cart.checkout_status = "failed"
        cart.checkout_error = order_result.message
        db.commit()
        await _broadcast_cart_update(cart)
        await send_discord_aco_update(product_url, "failed", f"Cart {cart.id}: {order_result.message}")
        return False


class AcoDispatcher:
    """Global serial ACO runner. One checkout at a time."""

    _instance: Optional["AcoDispatcher"] = None

    def __init__(self):
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "AcoDispatcher":
        if cls._instance is None:
            cls._instance = AcoDispatcher()
        return cls._instance

    async def run_checkout(
        self,
        cart_id: int,
        profile_pool_ids: list[int],
        forced_profile_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Attempt ACO on a single cart.

        - Auto path: caller passes the task's profile pool; dispatcher picks the
          first profile not yet used for this event.
        - Manual path: caller passes `forced_profile_id`; dispatcher skips the
          used-check and runs with that profile (user consented).

        Returns (success, message).
        """
        async with self._lock:
            db = SessionLocal()
            try:
                cart = db.query(CartSession).filter(CartSession.id == cart_id).first()
                if not cart:
                    return False, "Cart not found"
                if cart.checkout_status not in ("pending", "failed"):
                    return False, f"Cart already {cart.checkout_status}"
                if cart.expires_at and datetime.utcnow() > cart.expires_at:
                    return False, "Cart expired"

                # Pick a profile
                if forced_profile_id is not None:
                    profile = db.query(BillingProfile).filter(
                        BillingProfile.id == forced_profile_id
                    ).first()
                    if not profile:
                        return False, f"Profile {forced_profile_id} not found"
                else:
                    used = used_profile_ids_for_event(cart.event_id, db)
                    chosen_id = next(
                        (pid for pid in profile_pool_ids if pid not in used),
                        None,
                    )
                    if chosen_id is None:
                        await _log(
                            cart.task_id, "info",
                            f"ACO: Profile pool exhausted for event {cart.event_id} — cart {cart.id} left pending for manual checkout.",
                            db,
                        )
                        return False, "Profile pool exhausted"
                    profile = db.query(BillingProfile).filter(BillingProfile.id == chosen_id).first()
                    if not profile:
                        return False, f"Profile {chosen_id} not found"

                # Lock the cart + assign profile. Clear any stale payment
                # state from a prior failed attempt so the retry starts clean.
                cart.checkout_status = "running"
                cart.billing_profile_id = profile.id
                cart.checkout_error = None
                cart.client_secret = None
                cart.payment_intent_id = None
                cart.payment_method_id = None
                cart.invoice_url = None
                db.commit()
                await _broadcast_cart_update(cart)
                await _log(
                    cart.task_id, "info",
                    f"ACO: Dispatcher picked profile '{profile.name}' for cart {cart.id}", db,
                )

                try:
                    ok = await run_single_checkout(cart, profile, db)
                except Exception as e:  # noqa: BLE001
                    logger.exception(f"ACO dispatcher: unhandled exception for cart {cart_id}")
                    cart.checkout_status = "failed"
                    cart.checkout_error = f"Unhandled: {e}"
                    db.commit()
                    await _broadcast_cart_update(cart)
                    return False, str(e)

                return (ok, "completed" if ok else (cart.checkout_error or "failed"))
            finally:
                db.close()
