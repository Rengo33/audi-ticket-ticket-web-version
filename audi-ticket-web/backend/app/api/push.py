"""
Web Push subscription management.

Single-user dashboard → subscriptions are stored flat, not scoped to any user.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import PushSubscription
from ..bot.web_push import send_push

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionBody(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=300)


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
async def vapid_public_key():
    """Public VAPID key — needed client-side before subscribe()."""
    if not settings.vapid_public_key:
        raise HTTPException(503, "Push not configured")
    return {"key": settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe(
    body: SubscriptionBody,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint
    ).first()
    if existing:
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        if body.user_agent:
            existing.user_agent = body.user_agent
    else:
        db.add(PushSubscription(
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            user_agent=body.user_agent,
        ))
    db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(
    body: UnsubscribeBody,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/test")
async def send_test_push(_: bool = Depends(get_current_user)):
    """Fire a canned notification at every stored subscription."""
    if not settings.debug:
        # Still allowed in prod — it's a single-user admin dashboard — but
        # labelled as a test so the click-through makes sense.
        pass
    await send_push(
        title="Audi Ticket Ops",
        body="Push is wired up — tap to open the app.",
        url="/",
        tag="test",
    )
    return {"ok": True}
