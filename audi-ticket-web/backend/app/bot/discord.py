"""
Discord webhook notifications.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from curl_cffi.requests import AsyncSession

from ..config import get_settings
from .core import CookieData

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_discord_message(message_data: dict) -> bool:
    """Send a message to Discord webhook."""
    if not settings.discord_webhook_url:
        logger.debug("Discord webhook URL not configured")
        return False
    
    try:
        async with AsyncSession() as session:
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


async def send_discord_cart_success(
    product_url: str,
    cookie: CookieData,
    quantity: int,
    total_time: float,
    checkout_token: str
):
    """Send cart success notification with checkout link."""
    # Get the base URL from settings or use default
    checkout_link = f"https://your-domain.com/checkout/{checkout_token}"
    
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
                f"**Speed**\n{total_time:.2f}s\n\n"
                f"**Cookie**\n`{cookie.name}`\n\n"
                f"**📱 Mobile Checkout**\n[Click here to checkout]({checkout_link})"
            ),
            "footer": {
                "text": f"Token: {checkout_token[:8]}..."
            }
        }]
    }
    
    await send_discord_message(message)
