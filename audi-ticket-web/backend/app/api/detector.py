"""
Release detector API — start/stop/configure the new-release auto-detector.
"""
import json
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import ReleaseDetector
from ..bot.release_detector import release_detector

router = APIRouter(prefix="/detector", tags=["detector"])


class DetectorConfig(BaseModel):
    poll_interval: float = 10.0
    keyword: str = "fc-bayern"
    quantity: int = 1
    num_threads: int = 1
    price_category: int = 0
    auto_checkout: bool = False
    billing_profile_id: Optional[str] = None
    reseed: bool = False  # clear the seen-set so the next scan re-seeds from scratch


class DetectorStatus(BaseModel):
    active: bool
    running: bool
    poll_interval: float
    keyword: str
    quantity: int
    num_threads: int
    price_category: int
    auto_checkout: bool
    billing_profile_id: Optional[str]
    scan_count: int
    last_scan_at: Optional[str]
    last_new_found_at: Optional[str]
    error_message: Optional[str]
    events_log: List[Any]
    frontier_id: Optional[int]
    launched: Dict[str, str]  # Audi products found via the widget {id: name}


def _row(db: Session) -> ReleaseDetector:
    cfg = db.query(ReleaseDetector).filter(ReleaseDetector.id == 1).first()
    if not cfg:
        cfg = ReleaseDetector(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _status(cfg: ReleaseDetector) -> DetectorStatus:
    return DetectorStatus(
        active=bool(cfg.active),
        running=release_detector.is_running(),
        poll_interval=cfg.poll_interval or 10.0,
        keyword=cfg.keyword or "",
        quantity=cfg.quantity or 1,
        num_threads=cfg.num_threads or 1,
        price_category=cfg.price_category or 0,
        auto_checkout=bool(cfg.auto_checkout),
        billing_profile_id=str(cfg.billing_profile_id) if cfg.billing_profile_id is not None else None,
        scan_count=cfg.scan_count or 0,
        last_scan_at=cfg.last_scan_at.isoformat() if cfg.last_scan_at else None,
        last_new_found_at=cfg.last_new_found_at.isoformat() if cfg.last_new_found_at else None,
        error_message=cfg.error_message,
        events_log=json.loads(cfg.events_log or "[]"),
        frontier_id=cfg.frontier_id,
        launched=json.loads(cfg.launched_ids or "{}"),
    )


@router.get("", response_model=DetectorStatus)
async def get_detector(db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    return _status(_row(db))


@router.post("/start", response_model=DetectorStatus)
async def start_detector(
    data: DetectorConfig,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    cfg = _row(db)
    cfg.poll_interval = max(150.0, data.poll_interval)  # Cloudflare
    cfg.keyword = data.keyword.strip()
    cfg.quantity = data.quantity
    cfg.num_threads = data.num_threads
    cfg.price_category = data.price_category
    cfg.auto_checkout = data.auto_checkout
    cfg.billing_profile_id = data.billing_profile_id
    if data.reseed:
        cfg.frontier_id = None  # next scan re-seeds from the newest listed product
        cfg.scan_count = 0
    db.commit()
    await release_detector.start(db)
    db.refresh(cfg)
    return _status(cfg)


@router.post("/stop", response_model=DetectorStatus)
async def stop_detector(db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    await release_detector.stop(db)
    return _status(_row(db))
