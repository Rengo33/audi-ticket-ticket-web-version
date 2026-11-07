"""
Discord webhook notifications with rate-limit handling.
"""
import asyncio
import logging
from datetime import datetime, timezone
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


SHOP_URL = "https://audidefuehrungen2.regiondo.de"
MAX_LINK_QTY = 4  # per-order cap of the Bayern games


def cart_link(product_id: str, date: str, time_: str, variation_id: str, option_id: str, qty: int) -> str:
    """A link that carts into the browser that opens it, in that person's own
    session: the shop's own fallback for cookie-blocked browsers (GET ajaxadd,
    then a redirect to the cart). Time as the shop's JS sends it ("20:30",
    ranges "10:00-16:00"); brackets encoded so Discord markdown keeps the URL."""
    t = "-".join(part[:5] for part in time_.split("-"))
    return (f"{SHOP_URL}/checkout/ajaxcart/ajaxadd/product/{product_id}"
            f"?ticket_date={date}&ticket_time={t}&ticket_variation={variation_id}"
            f"&ticket_option_qty%5B{option_id}%5D={qty}")


def _category_field(categories: Optional[list], slot: Optional[tuple] = None) -> list:
    """One field per category: "🟢 24 / 180 left", plus 1×–4× cart links when
    `slot` = (product_id, date, time) is known and the category has stock."""
    if not categories:
        return []
    fields = []
    for c in categories:
        value = f"{'🟢' if c['available'] else '🔴'} **{c['available']}** / {c['capacity']} left"
        if slot and c['available'] > 0 and c.get('option_id'):
            top = min(c['available'], c.get('max_qty') or MAX_LINK_QTY, MAX_LINK_QTY)
            links = " · ".join(f"[{n}×]({cart_link(*slot, c['variation_id'], c['option_id'], n)})"
                               for n in range(1, top + 1))
            value += f"\n🛒 {links}"
        fields.append(_field(c['title'], value))
    return fields


async def send_discord_notification(data: Dict[str, Any], product_url: str,
                                    categories: Optional[list] = None,
                                    product_id: Optional[str] = None):
    """Send ticket availability notification; `categories` (scraper.category_stock)
    adds the tickets left per category, and with `product_id` cart links that
    anyone can open to cart in their own browser (single-slot products only)."""
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

    # ponytail: links only for one date/time (every Bayern game); tours with many
    # slots would need a link set per slot and overflow the embed.
    slots = [(d, e['time']) for d, values in data.items() for e in values]
    slot = (product_id, *slots[0]) if product_id and len(slots) == 1 else None

    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "🎫 Tickets Available!",
            _COLOR_GREEN,
            [_field("Website", "Audi Ticket"), _field("Product", _product_label(product_url))]
            + fields + _category_field(categories, slot),
        )]
    }
    await send_discord_message(msg)


def _fact_fields(facts: Optional[dict]) -> list:
    """Kickoff / pickup / prices from scraper.product_facts as embed fields."""
    labels = (("kickoff", "Kickoff"), ("pickup", "Pickup"), ("prices", "Prices"))
    return [_field(label, facts[k]) for k, label in labels if facts and facts.get(k)]


async def send_discord_new_event(product_url: str, carted: bool, name: str = "",
                                 unreleased: bool = False, facts: Optional[dict] = None):
    """Release detector found a new product (on the listing, or created but not
    yet released when `unreleased`). `facts` adds kickoff, pickup and prices."""
    status = "🛒 Auto-carting now" if carted else "👀 Detected (no task started)"
    if unreleased and carted:
        status = "⏳ Task started — carts the moment it goes live"
    label = f"[{name}]({product_url})" if name else _product_label(product_url)
    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "🕵️ New event created (not released yet)" if unreleased else "🚨 New event detected!",
            0xDC052D,
            [_field("Product", label), _field("Action", status), *_fact_fields(facts)],
        )]
    }
    await send_discord_message(msg)


async def send_discord_flip(product_url: str, name: str, enabled: bool):
    """Audi switched a hidden product on (not public yet — often only a
    placeholder for a few seconds) or back off."""
    title = ("🟡 Enabled by Audi — not public yet (may be a placeholder)" if enabled
             else "⚪ Hidden again")
    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(title, 0xF5A623 if enabled else 0x9B9B9B,
                          [_field("Product", f"[{name}]({product_url})")], thumbnail=False)]
    }
    await send_discord_message(msg)


async def send_discord_edited(product_url: str, name: str, facts: Optional[dict] = None):
    """Audi saved a product that is still hidden — edits tend to come shortly
    before a release, so this is the early warning."""
    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "✏️ Hidden event edited — release may be near",
            0xF5A623,
            [_field("Product", f"[{name}]({product_url})"), *_fact_fields(facts)],
        )]
    }
    await send_discord_message(msg)


async def send_discord_released(product_url: str, name: str, found_at: datetime):
    """A product the detector found while hidden is now live in the product API.
    Checked once per detector scan, so the release time is accurate to ~30s."""
    mins = int((datetime.utcnow() - found_at).total_seconds() // 60)
    hidden = f"{mins // 60} h {mins % 60} min" if mins >= 60 else f"{mins} min"
    found = int(found_at.replace(tzinfo=timezone.utc).timestamp())
    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "✅ Released",
            _COLOR_GREEN,
            [_field("Product", f"[{name}]({product_url})"),
             _field("Found hidden", f"<t:{found}:t>", inline=True),
             _field("Live after", hidden, inline=True)],
        )]
    }
    await send_discord_message(msg)


async def send_discord_blocked(what: str, reason: str):
    """A poller gave up because the site stopped answering (Cloudflare)."""
    msg = {
        "username": "Audi Ticket Bot",
        "embeds": [_embed(
            "⛔ Blocked — stopped to protect the server IP",
            0xDC052D,
            [_field("Stopped", what), _field("Reason", reason),
             _field("Next step", "Check from the server whether requests get through again, then restart.")],
            thumbnail=False,
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
