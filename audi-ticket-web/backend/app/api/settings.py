"""Runtime app settings the UI can flip without a restart."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import AppSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class ShopMode(BaseModel):
    shop_via_origin: bool


def _row(db: Session) -> AppSettings:
    row = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if not row:
        row = AppSettings(id=1, shop_via_origin=get_settings().shop_via_origin)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=ShopMode)
async def read_settings(db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    return ShopMode(shop_via_origin=_row(db).shop_via_origin)


@router.put("", response_model=ShopMode)
async def update_settings(data: ShopMode, db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    row = _row(db)
    row.shop_via_origin = data.shop_via_origin
    db.commit()
    logger.info(f"[Settings] shop_via_origin set to {data.shop_via_origin}")
    return ShopMode(shop_via_origin=row.shop_via_origin)
