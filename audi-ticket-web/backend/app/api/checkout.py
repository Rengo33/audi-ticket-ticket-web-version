"""
Cart session list + mobile checkout proxy.

The proxy is the only supported checkout path. It rewrites URLs in the
upstream response so every subsequent request flows back through us,
carrying the cart cookie in a long-lived per-cart curl_cffi session.
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, Tuple

from curl_cffi.requests import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import BillingProfile, CartSession, Task
from ..schemas import CartSessionResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["checkout"])


# ─── Cart session cache ──────────────────────────────────────────────
# One AsyncSession per cart token so cookies stick across proxy hops.
# Entries self-evict when their cart expires or is unreachable.
_proxy_sessions: Dict[str, Tuple[AsyncSession, datetime]] = {}


async def _evict_session(token: str) -> None:
    entry = _proxy_sessions.pop(token, None)
    if entry:
        session, _ = entry
        try:
            await session.close()
        except Exception:
            pass


async def _get_proxy_session(cart: CartSession) -> AsyncSession:
    entry = _proxy_sessions.get(cart.token)
    if entry is None:
        session = AsyncSession(impersonate="chrome120")
        session.cookies.set(cart.cookie_name, cart.cookie_value, domain=cart.cookie_domain)
        _proxy_sessions[cart.token] = (session, cart.expires_at)
        return session
    return entry[0]


async def _require_cart(token: str, db: Session) -> CartSession:
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    if not cart:
        raise HTTPException(404, "Session not found")
    if datetime.utcnow() > cart.expires_at:
        await _evict_session(token)
        raise HTTPException(410, "Session expired")
    return cart


# ─── HTML rewrite ────────────────────────────────────────────────────
# Single-pass regex replaces upstream links with our proxy prefix.
# {PROXY} placeholder is substituted per-call.
_REWRITE_RE = re.compile(
    r"""https?://audidefuehrungen2\.regiondo\.de/"""                    # absolute
    r"""|(?<=href=")/(?!/)(?!checkout/[^"]*/proxy/)"""                  # relative href (skip //)
    r"""|(?<=href=')/(?!/)(?!checkout/[^']*/proxy/)"""
    r"""|(?<=action=")/(?!/)(?!checkout/[^"]*/proxy/)"""
    r"""|(?<=action=')/(?!/)(?!checkout/[^']*/proxy/)""",
    re.IGNORECASE,
)


def rewrite_html_for_proxy(html: str, token: str) -> str:
    """Rewrite upstream URLs to route back through the proxy."""
    proxy = f"/checkout/{token}/proxy/"
    html = _REWRITE_RE.sub(proxy, html)
    if "<head>" in html and "<base " not in html:
        html = html.replace("<head>", f'<head><base href="{proxy}">', 1)
    return html


def _rewrite_json_html(body: str, token: str) -> str:
    """Walk the JSON body and rewrite any embedded HTML fragment."""
    try:
        data = json.loads(body)
    except Exception:
        return body.replace("https:\\/\\/audidefuehrungen2.regiondo.de\\/", f"/checkout/{token}/proxy/")
    if isinstance(data, dict) and isinstance(data.get("html"), str):
        data["html"] = rewrite_html_for_proxy(data["html"], token)
    return json.dumps(data)


# ─── Routes ──────────────────────────────────────────────────────────


@router.get("/api/carts", response_model=list[CartSessionResponse])
async def list_cart_sessions(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    rows = (
        db.query(CartSession, Task.auto_checkout)
        .outerjoin(Task, CartSession.task_id == Task.id)
        .order_by(CartSession.created_at.desc())
        .limit(50)
        .all()
    )
    profile_ids = {c.billing_profile_id for c, _ in rows if c.billing_profile_id}
    profile_name_by_id: dict[int, str] = {}
    if profile_ids:
        for p in db.query(BillingProfile.id, BillingProfile.name).filter(
            BillingProfile.id.in_(profile_ids)
        ).all():
            profile_name_by_id[p.id] = p.name
    return [
        {
            "id": cart.id,
            "token": cart.token,
            "task_id": cart.task_id,
            "event_id": cart.event_id,
            "product_url": cart.product_url,
            "checkout_url": cart.checkout_url,
            "quantity": cart.quantity,
            "price_category": cart.price_category or 0,
            "checkout_status": cart.checkout_status,
            "auto_checkout": bool(auto_checkout),
            "billing_profile_id": cart.billing_profile_id,
            "billing_profile_name": profile_name_by_id.get(cart.billing_profile_id) if cart.billing_profile_id else None,
            "total_time": cart.total_time,
            "invoice_url": cart.invoice_url,
            "checkout_error": cart.checkout_error,
            "created_at": cart.created_at,
            "expires_at": cart.expires_at,
            "used_at": cart.used_at,
        }
        for cart, auto_checkout in rows
    ]


class ManualCheckoutBody(BaseModel):
    billing_profile_id: int


@router.post("/api/carts/{cart_id}/checkout")
async def manual_checkout(
    cart_id: int,
    body: ManualCheckoutBody,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    """Trigger ACO for a specific cart with a user-chosen profile.

    The dispatcher's global lock prevents racing with auto-dispatch or a
    duplicate click. `billing_profile_id` bypasses the used-check: the UI has
    already shown the user that the profile is used (badge + confirm).
    """
    cart = db.query(CartSession).filter(CartSession.id == cart_id).first()
    if not cart:
        raise HTTPException(404, "Cart not found")
    if cart.checkout_status not in ("pending", "failed"):
        raise HTTPException(409, f"Cart is {cart.checkout_status}, cannot start checkout")
    if datetime.utcnow() > cart.expires_at:
        raise HTTPException(410, "Cart expired")

    from ..bot.aco_dispatcher import AcoDispatcher
    ok, msg = await AcoDispatcher.get().run_checkout(
        cart_id=cart.id,
        profile_pool_ids=[],
        forced_profile_id=body.billing_profile_id,
    )
    return {"success": ok, "message": msg}


@router.get("/api/checkout/{token}/cookie")
async def get_checkout_cookie(token: str, db: Session = Depends(get_db)):
    """Return the raw cookie so the frontend can offer a copy button. Token is the auth."""
    cart = await _require_cart(token, db)
    return JSONResponse(
        content={
            "name": cart.cookie_name,
            "value": cart.cookie_value,
            "domain": cart.cookie_domain,
            "checkout_url": f"{settings.audi_base_url}/checkout/cart",
            "expires_at": cart.expires_at.isoformat() + "Z",
        }
    )


@router.get("/checkout/{token}")
async def checkout_root(token: str, db: Session = Depends(get_db)):
    """Legacy entry — redirect straight to the proxy cart."""
    await _require_cart(token, db)
    return RedirectResponse(url=f"/checkout/{token}/cart", status_code=302)


@router.get("/checkout/{token}/cart")
async def checkout_cart_page(token: str, db: Session = Depends(get_db)):
    cart = await _require_cart(token, db)

    if not cart.used_at:
        cart.used_at = datetime.utcnow()
        db.commit()

    session = await _get_proxy_session(cart)
    try:
        response = await session.get(f"{settings.audi_base_url}/checkout/cart")
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {e}")

    if response.status_code != 200:
        raise HTTPException(502, f"Audi server returned {response.status_code}")

    return HTMLResponse(content=rewrite_html_for_proxy(response.text, token))


@router.get("/checkout/{token}/proxy/{path:path}")
async def checkout_proxy_get(
    token: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cart = await _require_cart(token, db)
    session = await _get_proxy_session(cart)

    target = f"{settings.audi_base_url}/{path}"
    if request.query_params:
        target += f"?{request.query_params}"

    try:
        response = await session.get(target)
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {e}")

    ctype = response.headers.get("content-type", "")
    if "text/html" in ctype:
        return HTMLResponse(
            content=rewrite_html_for_proxy(response.text, token),
            status_code=response.status_code,
        )
    return Response(content=response.content, status_code=response.status_code, media_type=ctype)


@router.post("/checkout/{token}/proxy/{path:path}")
async def checkout_proxy_post(
    token: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cart = await _require_cart(token, db)
    session = await _get_proxy_session(cart)

    body = await request.body()
    ctype = request.headers.get("content-type", "")
    headers = {"Content-Type": ctype} if ctype else {}
    data = body.decode("utf-8") if "application/x-www-form-urlencoded" in ctype else body

    try:
        response = await session.post(f"{settings.audi_base_url}/{path}", data=data, headers=headers)
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {e}")

    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location", "")
        if location.startswith(settings.audi_base_url + "/"):
            location = location.replace(settings.audi_base_url + "/", f"/checkout/{token}/proxy/", 1)
        elif location.startswith("/"):
            location = f"/checkout/{token}/proxy{location}"
        if location:
            return RedirectResponse(url=location, status_code=response.status_code)

    resp_ctype = response.headers.get("content-type", "")
    text = response.text
    looks_json = text.lstrip()[:1] in ("{", "[")

    if "text/html" in resp_ctype and not looks_json:
        return HTMLResponse(
            content=rewrite_html_for_proxy(text, token),
            status_code=response.status_code,
        )
    if looks_json:
        return Response(
            content=_rewrite_json_html(text, token),
            status_code=response.status_code,
            media_type="application/json",
        )
    return Response(content=response.content, status_code=response.status_code, media_type=resp_ctype)
