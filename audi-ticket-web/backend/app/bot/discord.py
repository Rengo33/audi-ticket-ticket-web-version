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


def _get_queue() -> asyncio.Queue:
    global _message_queue
    if _message_queue is None:
        _message_queue = asyncio.Queue()
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
        # Discord allows 5 messages per 2 seconds — space them out
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
                # Rate limited — wait and retry once
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
    _get_queue().put_nowait(message_data)


async def send_discord_notification(data: Dict[str, Any], product_url: str):
    """Send ticket availability notification."""
    message = {
        "username": "Audi Ticket Bot",
        "embeds": [{
            "title": "🎫 Ticket Availability Update",
            "color": 65280,  # Green
            "timestamp": datetime.utcnow().isoformat(),
            "url": product_url,
            "description": ""
        }]
    }

    description = ""
    entries_count = 0

    for date, values in list(data.items())[:10]:
        for entry in values:
            try:
                dt_obj = datetime.strptime(f"{date} {entry['time']}", "%Y-%m-%d %H:%M:%S")
                dt_str = dt_obj.strftime("%d.%m.%Y - %H:%M")
                availability = entry['qty_available']
                status = "🔴 SOLD OUT" if entry['traffic_light'] == 3 else "🟢 AVAILABLE"
                description += f"{dt_str} - {availability} {status}\n"
                entries_count += 1
            except Exception:
                continue

    if entries_count == 0:
        return

    message["embeds"][0]["description"] = description
    await send_discord_message(message)


PRICE_CATEGORY_LABELS = ['Kat 3 - Block 237', 'Kat 1 - Block 136', 'Kat 1 - Block 328']


async def send_discord_cart_success(
    product_url: str,
    cookie: CookieData,
    quantity: int,
    total_time: float,
    checkout_token: str,
    price_category: int = 0
):
    """Send cart success notification with checkout link."""
    checkout_link = f"{settings.base_url}/checkout/{checkout_token}/cart"
    cat_label = PRICE_CATEGORY_LABELS[price_category] if price_category < len(PRICE_CATEGORY_LABELS) else f"Cat {price_category}"

    message = {
        "username": "Audi Ticket Bot",
        "embeds": [{
            "title": "✅ Added to Cart!",
            "color": 65280,  # Green
            "timestamp": datetime.utcnow().isoformat(),
            "description": (
                f"**Website**\nAudi Tickets\n\n"
                f"**Product**\n{product_url}\n\n"
                f"**Quantity**\n{quantity}\n\n"
                f"**Price Category**\n{cat_label}\n\n"
                f"**Speed**\n{total_time:.2f}s\n\n"
                f"**Cookie**\n`{cookie.value}`\n\n"
                f"**Console Script**\n```\ndocument.cookie='{cookie.name}={cookie.value};path=/;domain=.audidefuehrungen2.regiondo.de';location.href='https://audidefuehrungen2.regiondo.de/checkout/cart'\n```\n\n"
                f"**📱 Checkout Page**\n[Checkout Helper]({checkout_link})"
            ),
            "footer": {
                "text": f"Token: {checkout_token[:8]}..."
            }
        }]
    }

    await send_discord_message(message)
