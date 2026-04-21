"""
Discord webhook notifications with rate-limit handling.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from curl_cffi.requests import AsyncSession

from ..config import get_settings
from .core import CookieData

logger = logging.getLogger(__name__)
settings = get_settings()

# Queue + worker to avoid Discord rate limits (5 req / 2s per webhook)
_message_queue: asyncio.Queue = None
_worker_task: asyncio.Task = None

# Discord brand colors
_COLOR_GREEN  = 0x57F287
_COLOR_RED    = 0xED4245
_COLOR_YELLOW = 0xFEE75C
_COLOR_BLUE   = 0x5865F2

PRICE_CATEGORY_LABELS = ['Kat 3 - Block 237', 'Kat 1 - Block 136', 'Kat 1 - Block 328']

# Bayern Munich thumbnail — stable Wikimedia URL
_BAYERN_THUMB = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282002%E2%80%932017%29.svg/200px-FC_Bayern_M%C3%BCnchen_logo_%282002%E2%80%932017%29.svg.png"


def _get_queue() -> asyncio.Queue:
    global _message_queue
    if _message_queue is None:
        _message_queue = asyncio.Queue(maxsize=100)
    return _message_queue


async def _ensure_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_queue_worker())


async def _queue_worker():
    """Process queued Discord messages with rate-limit spacing."""
    queue = _get_queue()
    while True:
        message_data = await queue.get()
        try:
            await _send_now(message_data)
        except Exception as e:
            logger.error(f"Discord queue worker error: {e}")
        finally:
            queue.task_done()
        await asyncio.sleep(0.5)


async def _send_now(message_data: dict) -> bool:
    """Actually send a message to Discord webhook."""
    if not settings.discord_webhook_url:
        return False

    try:
        async with AsyncSession() as session:
            response = await session.post(
                settings.discord_webhook_url,
                json=message_data
            )

            if response.status_code == 429:
                retry_after = 2.0
                try:
                    retry_after = response.json().get('retry_after', 2.0)
                except Exception:
                    pass
                logger.warning(f"Discord rate limited, retrying after {retry_after}s")
                await asyncio.sleep(retry_after)
                response = await session.post(
                    settings.discord_webhook_url,
                    json=message_data
                )

            if response.status_code in [200, 204]:
                logger.info("Discord webhook sent successfully")
                return True
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return False


async def send_discord_message(message_data: dict):
    """Queue a message for delivery (rate-limit safe)."""
    await _ensure_worker()
    queue = _get_queue()
    if queue.full():
        logger.warning("Discord queue full, dropping message")
        return
    queue.put_nowait(message_data)


def _field(name: str, value: str, inline: bool = False) -> dict:
    return {"name": name, "value": value, "inline": inline}


def _product_label(product_url: str) -> str:
    """Turn a product URL into a readable hyperlink label."""
    slug = product_url.rstrip("/").split("/")[-1]
    label = slug.replace("-", " ").title()
    return f"[{label}]({product_url})"


def _embed(title: str, color: int, fields: list, thumbnail: bool = True) -> dict:
    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {"text": "Audi Ticket Bot"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    if thumbnail:
        embed["thumbnail"] = {"url": _BAYERN_THUMB}
    return embed


async def send_discord_notification(data: Dict[str, Any], product_url: str):
    """Send ticket availability notification."""
    fields = []
    for date, values in list(data.items())[:8]:
        for entry in values:
            try:
                dt_obj = datetime.strptime(f"{date} {entry['time']}", "%Y-%m-%d %H:%M:%S")
                dt_str = dt_obj.strftime("%d.%m.%Y — %H:%M")
                qty = entry['qty_available']
                icon = "🔴" if entry['traffic_light'] == 3 else "🟢"
                fields.append(_field(dt_str, f"{icon} {qty} available"))
            except Exception:
                continue

    if not fields:
        return

    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "🎫 Tickets Available!",
            _COLOR_GREEN,
            [_field("Website", "Audi Ticket"), _field("Product", _product_label(product_url))] + fields,
        )]
    }
    await send_discord_message(msg)


async def send_discord_cart_success(
    product_url: str,
    cookie: CookieData,
    quantity: int,
    total_time: float,
    checkout_token: str,
    price_category: int = 0,
):
    """Send cart success notification with checkout link."""
    checkout_link = f"{settings.base_url}/checkout/{checkout_token}/cart"
    cat_label = (
        PRICE_CATEGORY_LABELS[price_category]
        if price_category < len(PRICE_CATEGORY_LABELS)
        else f"Cat {price_category}"
    )

    fields = [
        _field("Website",  "Audi Ticket"),
        _field("Product",  _product_label(product_url)),
        _field("Quantity", f"{quantity}x"),
        _field("Category", cat_label),
        _field("Speed",    f"{total_time:.2f}s"),
        _field("Cookie",   f"`{cookie.value}`"),
        _field("Checkout", f"[Open Checkout →]({checkout_link})"),
    ]

    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed("✅ Added to Cart!", _COLOR_GREEN, fields)],
    }
    await send_discord_message(msg)


async def send_discord_aco_update(
    product_url: str, status: str, detail: str = "",
    profile_name: str = "", profile_email: str = "",
    order_ref: str = "", cart_id: str = "",
):
    """Send ACO status update to Discord."""
    colors = {
        "payment_ready": _COLOR_BLUE,
        "3ds_waiting":   _COLOR_YELLOW,
        "completed":     _COLOR_GREEN,
        "failed":        _COLOR_RED,
    }
    titles = {
        "payment_ready": "💳 Payment Ready",
        "3ds_waiting":   "🔐 3DS Verification Required",
        "completed":     "🎉 Order Confirmed!",
        "failed":        "❌ Checkout Failed",
    }

    base_fields = [
        _field("Website", "Audi Ticket"),
        _field("Product", _product_label(product_url)),
    ]

    if status == "completed":
        extra = [
            _field("Order Ref", f"`#{order_ref or 'unknown'}`"),
            *([_field("Cart",    f"#{cart_id}")] if cart_id else []),
            *([_field("Profile", profile_name)] if profile_name else []),
            *([_field("Email",   profile_email)] if profile_email else []),
        ]
    elif status == "failed":
        extra = [_field("Notes", detail)]
    else:
        extra = [_field("Status", detail)]

    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            titles.get(status, f"ACO: {status}"),
            colors.get(status, _COLOR_GREEN),
            base_fields + extra,
        )],
    }
    await send_discord_message(msg)
