"""
Web Push sender — fire-and-forget queue, mirrors discord.py's pattern.

Call sites do `await send_push(title=..., body=...)`; the actual HTTP fans out
on a background worker. Dead subscriptions (404/410 from the push service) are
deleted so the table stays clean.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from pywebpush import webpush, WebPushException

from ..config import get_settings
from ..database import SessionLocal
from ..models import PushSubscription

logger = logging.getLogger(__name__)
settings = get_settings()

_message_queue: Optional[asyncio.Queue] = None
_worker_task: Optional[asyncio.Task] = None


def _get_queue() -> asyncio.Queue:
    global _message_queue
    if _message_queue is None:
        _message_queue = asyncio.Queue(maxsize=200)
    return _message_queue


async def _ensure_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_queue_worker())


def _vapid_claims() -> dict:
    # `aud` is derived from the endpoint by pywebpush — do NOT set it here,
    # or Android (FCM) and iOS (APNs) will both reject the JWT.
    email = settings.vapid_contact_email or "admin@example.com"
    sub = email if email.startswith("mailto:") else f"mailto:{email}"
    return {"sub": sub}


def _send_sync(endpoint: str, p256dh: str, auth: str, payload_bytes: bytes) -> int:
    """Blocking pywebpush call. Returns HTTP status; raises WebPushException on failure."""
    response = webpush(
        subscription_info={
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth},
        },
        data=payload_bytes,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims=_vapid_claims(),
    )
    return getattr(response, "status_code", 201)


async def _deliver(payload: dict):
    """Fan out one payload to every stored subscription."""
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.debug("Web push skipped: VAPID keys not configured")
        return

    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).all()
    finally:
        db.close()

    if not subs:
        return

    payload_bytes = json.dumps(payload).encode("utf-8")
    dead_endpoints: list[str] = []

    for sub in subs:
        try:
            await asyncio.to_thread(
                _send_sync, sub.endpoint, sub.p256dh, sub.auth, payload_bytes
            )
            # Touch last_sent_at in a short-lived session so the next failure
            # doesn't leave the row looking untouched forever.
            db2 = SessionLocal()
            try:
                db2.query(PushSubscription).filter(
                    PushSubscription.endpoint == sub.endpoint
                ).update({"last_sent_at": datetime.utcnow()})
                db2.commit()
            finally:
                db2.close()
        except WebPushException as e:
            status = getattr(e.response, "status_code", None) if e.response else None
            if status in (404, 410):
                dead_endpoints.append(sub.endpoint)
            else:
                logger.warning(f"Web push failed ({status}) for {sub.endpoint[:60]}…: {e}")
        except Exception as e:
            logger.error(f"Web push unexpected error: {e}")

    if dead_endpoints:
        db3 = SessionLocal()
        try:
            db3.query(PushSubscription).filter(
                PushSubscription.endpoint.in_(dead_endpoints)
            ).delete(synchronize_session=False)
            db3.commit()
            logger.info(f"Pruned {len(dead_endpoints)} dead push subscription(s)")
        finally:
            db3.close()


async def _queue_worker():
    queue = _get_queue()
    while True:
        payload = await queue.get()
        try:
            await _deliver(payload)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Web push queue worker error: {e}")
        finally:
            queue.task_done()


async def send_push(
    title: str,
    body: str = "",
    url: str = "/",
    tag: Optional[str] = None,
):
    """Enqueue a push for every stored subscription (fire-and-forget)."""
    await _ensure_worker()
    queue = _get_queue()
    if queue.full():
        logger.warning("Web push queue full, dropping message")
        return
    payload = {"title": title, "body": body, "url": url}
    if tag:
        payload["tag"] = tag
    queue.put_nowait(payload)


async def stop_worker():
    """Cancel the background worker on shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    _worker_task = None
