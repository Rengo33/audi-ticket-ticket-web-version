"""
Task manager for running multiple monitoring tasks.
Uses a shared AvailabilityWatcher to deduplicate polling — multiple tasks
watching the same product URL share a single poller instead of each
hammering the site independently.
"""
import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from ..models import Task, TaskStatus, CartSession, TaskLog, BillingProfile
from ..config import get_settings
from ..database import SessionLocal
from .core import AudiTicketBot, CookieData
from .discord import send_discord_notification, send_discord_cart_success, send_discord_aco_update
from .checkout import AutoCheckout

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskSubscriber:
    """A task subscribed to an AvailabilityWatcher."""
    def __init__(self, task_id: int, product_url: str, quantity: int, num_threads: int, price_category: int):
        self.task_id = task_id
        self.product_url = product_url
        self.quantity = quantity
        self.num_threads = num_threads
        self.price_category = price_category
        self.previous_data = None
        self.waiting_until: Optional[datetime] = None
        self.processing = False


class AvailabilityWatcher:
    """
    Polls a single (event_id, ticket_id) pair and notifies all subscribed tasks.
    One poller per unique product, no matter how many tasks watch it.
    """
    def __init__(self, event_id: str, ticket_id: str, product_url: str, manager: 'TaskManager'):
        self.event_id = event_id
        self.ticket_id = ticket_id
        self.product_url = product_url
        self.manager = manager
        self.subscribers: Dict[int, TaskSubscriber] = {}
        self._task: Optional[asyncio.Task] = None
        self._bot: Optional[AudiTicketBot] = None
        self.scan_count = 0
        self._last_discord_data = None

    @property
    def key(self) -> str:
        return f"{self.event_id}:{self.ticket_id}"

    def add_subscriber(self, sub: TaskSubscriber):
        self.subscribers[sub.task_id] = sub
        logger.info(f"[Watcher {self.key}] Task {sub.task_id} subscribed ({len(self.subscribers)} total)")

    def remove_subscriber(self, task_id: int):
        self.subscribers.pop(task_id, None)
        logger.info(f"[Watcher {self.key}] Task {task_id} unsubscribed ({len(self.subscribers)} remaining)")

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._bot:
            await self._bot.close_session()
            self._bot = None

    async def _poll_loop(self):
        """Single polling loop shared by all subscribers."""
        db = SessionLocal()
        try:
            self._bot = AudiTicketBot()
            await self._bot.start_session()

            while self.subscribers:
                data = await self._bot.get_available_tickets(self.event_id, self.ticket_id)
                self.scan_count += 1

                # Calculate total available
                total_available = 0
                if data:
                    try:
                        total_available = sum(
                            sum(max(0, t.get('qty_available', 0)) for t in tickets)
                            for tickets in data.values()
                        )
                    except Exception:
                        total_available = 0

                # Batch-update all subscriber tasks in one commit
                now = datetime.utcnow()
                sub_ids = [sub.task_id for sub in self.subscribers.values()]
                if sub_ids:
                    db.query(Task).filter(Task.id.in_(sub_ids)).update({
                        Task.scan_count: self.scan_count,
                        Task.tickets_available: total_available,
                        Task.last_scan_at: now,
                    }, synchronize_session='fetch')
                    db.commit()

                # Broadcast scan update once with all task IDs
                now_iso = now.isoformat()
                for task_id in sub_ids:
                    await self.manager.broadcast({
                        "type": "scan_update",
                        "data": {
                            "task_id": task_id,
                            "scan_count": self.scan_count,
                            "tickets_available": total_available,
                            "last_scan_at": now_iso
                        }
                    })

                # Log periodically
                if self.scan_count == 1 or self.scan_count % 50 == 0:
                    msg = (f"Scan #{self.scan_count}: {total_available} tickets available"
                           if total_available > 0
                           else f"Scan #{self.scan_count}: No tickets available - waiting for release...")
                    if total_available > 0 or self.scan_count == 1:
                        msg += f" (shared watcher, {len(self.subscribers)} tasks)"
                        for sub in list(self.subscribers.values()):
                            await self.manager._log(sub.task_id, "info", msg, db)

                # Process availability for each subscriber
                if data and total_available > 0:
                    # Send Discord notification only when data changes
                    if data != self._last_discord_data:
                        self._last_discord_data = data
                        asyncio.create_task(
                            send_discord_notification(data, self.product_url)
                        )

                    for sub in list(self.subscribers.values()):
                        if sub.waiting_until and datetime.utcnow() < sub.waiting_until:
                            continue
                        if sub.processing:
                            continue
                        if data == sub.previous_data:
                            continue

                        sub.previous_data = data
                        sub.processing = True
                        asyncio.create_task(
                            self._handle_availability(sub, data)
                        )

                if data is None or (data and len(data) == 0):
                    await asyncio.sleep(5)

                await asyncio.sleep(settings.default_scan_interval)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            import traceback
            logger.error(f"[Watcher {self.key}] Error: {e}")
            logger.error(f"[Watcher {self.key}] Traceback: {traceback.format_exc()}")
            # Mark all subscribers as failed
            for sub in list(self.subscribers.values()):
                await self.manager._mark_failed(sub.task_id, str(e), db)
        finally:
            if self._bot:
                await self._bot.close_session()
                self._bot = None
            db.close()
            # Remove this watcher from the manager
            self.manager._remove_watcher(self.key)

    async def _handle_availability(self, sub: TaskSubscriber, data: dict):
        """Handle ticket availability for a single subscriber task."""
        db = SessionLocal()
        try:
            process_start_time = time.time()

            await self.manager._log(sub.task_id, "info",
                f"Change detected! Processing (cat {sub.price_category})...", db)

            for date, tickets in data.items():
                for ticket in tickets:
                    qty_available = ticket['qty_available']
                    if qty_available < sub.quantity:
                        continue

                    await self.manager._log(sub.task_id, "info",
                        f"Attempting {sub.quantity} ticket(s) for {date} @ {ticket['time']} ({qty_available} available)", db)

                    time_encoded = quote(ticket['time'], safe='')
                    time_short = ticket['time'][:5]
                    variations = ticket.get('variations', [])
                    if not variations:
                        continue

                    await self.manager._log(sub.task_id, "info",
                        f"Available variations: {variations} (selecting index {sub.price_category})", db)

                    # Build ordered list: preferred variation first, then fallbacks
                    if sub.price_category < len(variations):
                        preferred = variations[sub.price_category]
                        fallbacks = [v for i, v in enumerate(variations) if i != sub.price_category]
                    else:
                        await self.manager._log(sub.task_id, "warning",
                            f"Price category index {sub.price_category} not available (only {len(variations)} variations), trying all", db)
                        preferred = variations[0]
                        fallbacks = variations[1:]

                    for var_idx, variation in enumerate([preferred] + fallbacks):
                        is_fallback = var_idx > 0
                        if is_fallback:
                            await self.manager._log(sub.task_id, "warning",
                                f"Falling back to variation {variation}", db)

                        option_number = await self._bot.get_option_number(
                            self.event_id, variation, date, time_encoded
                        )

                        if not option_number:
                            continue

                        max_possible_carts = qty_available // sub.quantity
                        actual_threads = min(sub.num_threads, max(1, max_possible_carts))

                        await self.manager._log(sub.task_id, "info",
                            f"Running {actual_threads} ATC thread(s) for variation {variation}", db)

                        atc_tasks = []
                        for _ in range(actual_threads):
                            atc_tasks.append(
                                self.manager._attempt_atc(
                                    sub.task_id, self._bot, self.event_id, date,
                                    time_short, variation, option_number,
                                    sub.quantity, sub.product_url, sub.price_category,
                                    process_start_time, db
                                )
                            )

                        results = await asyncio.gather(*atc_tasks, return_exceptions=True)

                        if any(r is True for r in results if not isinstance(r, Exception)):
                            await self._handle_cart_success(sub, db)
                            return

                        # ATC failed for this variation, try next
                        if not is_fallback:
                            await self.manager._log(sub.task_id, "warning",
                                f"Primary variation {variation} failed, trying fallbacks...", db)

                    return
        finally:
            sub.processing = False
            db.close()

    async def _handle_cart_success(self, sub: TaskSubscriber, db: Session):
        """Handle successful cart — check for ACO, then wait for re-cart."""
        task = db.query(Task).filter(Task.id == sub.task_id).first()
        auto_checkout = getattr(task, 'auto_checkout', False) if task else False
        billing_profile_id = getattr(task, 'billing_profile_id', None) if task else None

        if auto_checkout and billing_profile_id:
            # ACO: run auto-checkout
            await self._run_auto_checkout(sub, task, db)
        else:
            # Normal flow: just notify and wait for manual checkout
            await self.manager._log(sub.task_id, "success",
                "Successfully carted! Sleeping 17 min then will re-cart...", db)

        if task:
            task.status = TaskStatus.SUCCESS.value
            task.completed_at = datetime.utcnow()
            db.commit()

        await self.manager.broadcast({
            "type": "task_update",
            "data": {"task_id": sub.task_id, "status": "success"}
        })

        await asyncio.sleep(3)

        cart_hold = settings.cart_hold_time
        task = db.query(Task).filter(Task.id == sub.task_id).first()
        if task:
            task.status = TaskStatus.WAITING.value
            db.commit()

        await self.manager.broadcast({
            "type": "task_update",
            "data": {
                "task_id": sub.task_id,
                "status": "waiting",
                "recart_at": (datetime.utcnow() + timedelta(seconds=cart_hold - 3)).isoformat()
            }
        })

        await self.manager._log(sub.task_id, "info",
            f"Waiting {cart_hold // 60} min before re-cart...", db)

        sub.waiting_until = datetime.utcnow() + timedelta(seconds=cart_hold - 3)
        sub.previous_data = None

        asyncio.create_task(self._reactivate_after_wait(sub, cart_hold - 3))

    async def _run_auto_checkout(self, sub: TaskSubscriber, task: Task, db: Session):
        """Run the full auto-checkout flow after successful ATC."""
        # Support multiple billing profiles (comma-separated IDs)
        profile_id_str = str(task.billing_profile_id or "")
        profile_ids = [int(x.strip()) for x in profile_id_str.split(",") if x.strip().isdigit()]

        if not profile_ids:
            await self.manager._log(sub.task_id, "error", "ACO: No billing profile IDs configured", db)
            return

        profiles = db.query(BillingProfile).filter(BillingProfile.id.in_(profile_ids)).all()
        profile_map = {p.id: p for p in profiles}

        # Maintain the order from the config
        ordered_profiles = [profile_map[pid] for pid in profile_ids if pid in profile_map]
        if not ordered_profiles:
            await self.manager._log(sub.task_id, "error", "ACO: Billing profile(s) not found", db)
            return

        # Get only pending, non-expired cart sessions from this cart cycle
        now = datetime.utcnow()
        carts = db.query(CartSession).filter(
            CartSession.task_id == sub.task_id,
            CartSession.checkout_status == "pending",
            CartSession.expires_at > now
        ).order_by(CartSession.created_at.desc()).all()

        if not carts:
            await self.manager._log(sub.task_id, "error", "ACO: No pending cart sessions found", db)
            return

        profile_names = ", ".join(p.name for p in ordered_profiles)
        await self.manager._log(sub.task_id, "info",
            f"ACO: Processing {len(carts)} cart(s) with {len(ordered_profiles)} profile(s): {profile_names}", db)

        for i, cart in enumerate(carts):
            # Round-robin assign profiles to carts
            profile = ordered_profiles[i % len(ordered_profiles)]
            if i > 0:
                await self.manager._log(sub.task_id, "info", "ACO: Waiting 15s before next checkout...", db)
                await asyncio.sleep(15)

            await self.manager._log(sub.task_id, "info",
                f"ACO: Checkout {i+1}/{len(carts)} (cart {cart.id})...", db)

            await self._run_single_checkout(sub, cart, profile, db)

    async def _run_single_checkout(self, sub, cart, profile, db):
        """Run ACO for a single cart session."""
        async with AutoCheckout(cart.cookie_name, cart.cookie_value) as aco:
            # Step 1: Submit billing
            result = await aco.submit_billing(profile)
            if not result.success:
                await self.manager._log(sub.task_id, "error", f"ACO: Billing failed: {result.message}", db)
                cart.checkout_status = "failed"
                cart.checkout_error = result.message
                db.commit()
                await send_discord_aco_update(sub.product_url, "failed", f"Cart {cart.id}: {result.message}")
                return

            await self.manager._log(sub.task_id, "info", f"ACO: Billing submitted. PI: {result.payment_intent_id}", db)
            cart.checkout_status = "billing_done"
            cart.payment_intent_id = result.payment_intent_id
            cart.client_secret = result.client_secret
            db.commit()

            # Step 2: Confirm payment via browser
            pi_id = result.payment_intent_id
            client_secret = result.client_secret

            await self.manager._log(sub.task_id, "info", "ACO: Confirming payment via Stripe.js browser...", db)
            await send_discord_aco_update(sub.product_url, "3ds_waiting",
                f"Cart {cart.id}: Payment processing — approve 3DS if prompted!")

            result = await aco.confirm_payment(profile, pi_id, client_secret)

            if not result.success:
                await self.manager._log(sub.task_id, "error", f"ACO: Payment failed: {result.message}", db)
                cart.checkout_status = "failed"
                cart.checkout_error = result.message
                db.commit()
                await send_discord_aco_update(sub.product_url, "failed", f"Cart {cart.id}: {result.message}")
                return

            pm_id = result.payment_method_id
            await self.manager._log(sub.task_id, "success", "ACO: Payment confirmed!", db)

            # Step 3: Place order
            cart.checkout_status = "payment_confirmed"
            cart.payment_method_id = pm_id
            db.commit()

            cardholder = f"{profile.firstname} {profile.lastname}"
            order_result = await aco.place_order(pi_id, pm_id, cardholder)

            if order_result.success:
                await self.manager._log(sub.task_id, "success", f"ACO: Cart {cart.id} — {order_result.message}", db)
                cart.checkout_status = "completed"
                db.commit()
                await send_discord_aco_update(sub.product_url, "completed", f"Cart {cart.id}: Order confirmed!")
                await self.manager.broadcast({
                    "type": "task_update",
                    "data": {"task_id": sub.task_id, "status": "checkout_complete"}
                })
            else:
                await self.manager._log(sub.task_id, "error", f"ACO: Cart {cart.id} order failed: {order_result.message}", db)
                cart.checkout_status = "failed"
                cart.checkout_error = order_result.message
                db.commit()
                await send_discord_aco_update(sub.product_url, "failed", f"Cart {cart.id}: {order_result.message}")

    async def _reactivate_after_wait(self, sub: TaskSubscriber, wait_seconds: int):
        """Reactivate a subscriber after cart hold wait."""
        await asyncio.sleep(wait_seconds)

        if sub.task_id not in self.subscribers:
            return

        sub.waiting_until = None
        sub.previous_data = None
        sub.processing = False

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == sub.task_id).first()
            if task:
                task.status = TaskStatus.RUNNING.value
                task.completed_at = None
                db.commit()

            await self.manager.broadcast({
                "type": "task_update",
                "data": {"task_id": sub.task_id, "status": "running"}
            })

            await self.manager._log(sub.task_id, "info",
                "Cart hold expired, resuming monitoring for re-cart...", db)
        finally:
            db.close()


class TaskManager:
    """
    Manages multiple monitoring tasks.
    Tasks sharing the same product URL share a single AvailabilityWatcher.
    """

    def __init__(self):
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.task_data: Dict[int, dict] = {}
        self._ws_broadcast: Optional[Callable] = None
        self._watchers: Dict[str, AvailabilityWatcher] = {}  # key -> watcher
        self._task_watcher_map: Dict[int, str] = {}  # task_id -> watcher key

    def set_ws_broadcast(self, callback: Callable):
        self._ws_broadcast = callback

    async def broadcast(self, message: dict):
        if self._ws_broadcast:
            await self._ws_broadcast(message)

    def _remove_watcher(self, key: str):
        """Remove a watcher (called when its poll loop exits)."""
        self._watchers.pop(key, None)
        # Clean up task mappings
        to_remove = [tid for tid, k in self._task_watcher_map.items() if k == key]
        for tid in to_remove:
            self._task_watcher_map.pop(tid, None)
            self.active_tasks.pop(tid, None)
            self.task_data.pop(tid, None)

    async def start_task(self, task: Task, db: Session) -> bool:
        """Start a monitoring task."""
        logger.info(f"TaskManager.start_task called for task {task.id}")

        if task.id in self.active_tasks:
            logger.warning(f"Task {task.id} already in active_tasks, returning False")
            return False

        # Update task status
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.utcnow()
        db.commit()

        price_category = task.price_category or 0

        # Extract event details to find or create a watcher
        async_task = asyncio.create_task(
            self._setup_task(task.id, task.product_url, task.quantity, task.num_threads, price_category)
        )
        self.active_tasks[task.id] = async_task
        self.task_data[task.id] = {"previous_data": None}

        await self.broadcast({
            "type": "task_update",
            "data": {"task_id": task.id, "status": "running"}
        })

        return True

    async def _setup_task(self, task_id: int, product_url: str, quantity: int, num_threads: int, price_category: int):
        """Extract event IDs and subscribe to a shared watcher."""
        db = SessionLocal()
        try:
            async with AudiTicketBot() as bot:
                await self._log(task_id, "info", f"Started monitoring: {product_url}", db)

                event_id, ticket_id, categories = await bot.extract_event_details(product_url)

                if not event_id or not ticket_id:
                    await self._log(task_id, "error", "Could not extract Event/Ticket ID", db)
                    await self._mark_failed(task_id, "Could not extract Event/Ticket ID", db)
                    return

                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.event_id = event_id
                    task.ticket_id = ticket_id
                    db.commit()

                await self._log(task_id, "info", f"Event ID: {event_id}, Ticket ID: {ticket_id}", db)
                if categories:
                    await self._log(task_id, "info", f"Price categories from page: {categories}", db)
                    await self._log(task_id, "info",
                        f"Selected category index {price_category}: {categories[price_category] if price_category < len(categories) else 'unknown'}", db)

            # Find or create watcher
            watcher_key = f"{event_id}:{ticket_id}"
            if watcher_key in self._watchers:
                watcher = self._watchers[watcher_key]
                await self._log(task_id, "info",
                    f"Joining shared watcher (already monitoring with {len(watcher.subscribers)} other task(s))", db)
            else:
                watcher = AvailabilityWatcher(event_id, ticket_id, product_url, self)
                self._watchers[watcher_key] = watcher
                await self._log(task_id, "info", "Created new availability watcher", db)

            # Subscribe
            sub = TaskSubscriber(task_id, product_url, quantity, num_threads, price_category)
            watcher.add_subscriber(sub)
            self._task_watcher_map[task_id] = watcher_key

            # Start watcher if not already running
            await watcher.start()

            # Keep this coroutine alive while the task is subscribed
            # (so active_tasks[task_id] stays valid)
            try:
                while task_id in watcher.subscribers:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                watcher.remove_subscriber(task_id)
                if not watcher.subscribers:
                    await watcher.stop()
                raise

        except asyncio.CancelledError:
            raise
        except Exception as e:
            import traceback
            logger.error(f"Task {task_id} setup error: {e}")
            logger.error(traceback.format_exc())
            await self._mark_failed(task_id, str(e), db)
        finally:
            db.close()

    async def stop_task(self, task_id: int, db: Session) -> bool:
        """Stop a running task."""
        was_active = task_id in self.active_tasks

        # Unsubscribe from watcher
        watcher_key = self._task_watcher_map.pop(task_id, None)
        if watcher_key and watcher_key in self._watchers:
            watcher = self._watchers[watcher_key]
            watcher.remove_subscriber(task_id)
            if not watcher.subscribers:
                await watcher.stop()
                self._watchers.pop(watcher_key, None)

        if was_active:
            self.active_tasks[task_id].cancel()
            try:
                await self.active_tasks[task_id]
            except asyncio.CancelledError:
                pass
            del self.active_tasks[task_id]
            if task_id in self.task_data:
                del self.task_data[task_id]

        task = db.query(Task).filter(Task.id == task_id).first()
        if task and task.status in (TaskStatus.RUNNING.value, TaskStatus.SUCCESS.value, TaskStatus.WAITING.value, TaskStatus.PENDING.value):
            task.status = TaskStatus.STOPPED.value
            task.completed_at = datetime.utcnow()
            db.commit()

            await self.broadcast({
                "type": "task_update",
                "data": {"task_id": task_id, "status": "stopped"}
            })
            return True

        return was_active

    async def _log(self, task_id: int, level: str, message: str, db: Session):
        """Add log entry for task."""
        try:
            log = TaskLog(task_id=task_id, level=level, message=message)
            db.add(log)
            db.commit()
            logger.info(f"[Task {task_id}] DB log committed: {message}")
        except Exception as e:
            logger.error(f"[Task {task_id}] DB log error: {e}")
            db.rollback()

        try:
            await self.broadcast({
                "type": "log",
                "data": {
                    "task_id": task_id,
                    "level": level,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
        except Exception as e:
            logger.error(f"[Task {task_id}] Broadcast error: {e}")

    async def _attempt_atc(
        self, task_id: int, bot: AudiTicketBot, event_id: str, date: str,
        time_short: str, variation: str, option_number: str, quantity: int,
        product_url: str, price_category: int, start_time: float, db: Session
    ) -> bool:
        """Attempt to add to cart (single thread)."""
        async with AudiTicketBot() as atc_bot:
            success, cookie, error = await atc_bot.add_to_cart(
                event_id, date, time_short, variation,
                option_number, quantity, product_url
            )

            if success and cookie:
                total_time = time.time() - start_time

                await self._log(task_id, "success",
                    f"Cookie secured: {cookie.name} (Time: {total_time:.2f}s)", db)

                token = secrets.token_urlsafe(32)
                cart_session = CartSession(
                    token=token, task_id=task_id,
                    cookie_name=cookie.name, cookie_value=cookie.value,
                    cookie_domain=cookie.domain, product_url=product_url,
                    checkout_url="https://audidefuehrungen2.regiondo.de/checkout/cart",
                    quantity=quantity, price_category=price_category,
                    total_time=total_time,
                    expires_at=datetime.utcnow() + timedelta(seconds=settings.cart_hold_time)
                )
                db.add(cart_session)
                db.commit()

                await self.broadcast({
                    "type": "cart_success",
                    "data": {
                        "task_id": task_id, "token": token,
                        "quantity": quantity, "total_time": total_time
                    }
                })

                await send_discord_cart_success(
                    product_url, cookie, quantity, total_time, token, price_category
                )

                return True
            else:
                if error:
                    await self._log(task_id, "warning", f"ATC failed: {error}", db)
                return False

    async def _mark_failed(self, task_id: int, error: str, db: Session):
        """Mark task as failed."""
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = error
            task.completed_at = datetime.utcnow()
            db.commit()

        self.active_tasks.pop(task_id, None)
        self._task_watcher_map.pop(task_id, None)

        await self.broadcast({
            "type": "task_update",
            "data": {"task_id": task_id, "status": "failed", "error": error}
        })


# Global task manager instance
task_manager = TaskManager()
