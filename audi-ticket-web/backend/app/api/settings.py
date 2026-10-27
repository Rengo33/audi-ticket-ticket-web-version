"""Runtime app settings the UI can flip without a restart."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..bot.core import set_shop_via_origin
from ..database import get_db
from ..models import AppSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class ShopMode(BaseModel):
    shop_via_origin: bool


@router.get("", response_model=ShopMode)
async def read_settings(db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    return ShopMode(shop_via_origin=AppSettings.get(db).shop_via_origin)


@router.put("", response_model=ShopMode)
async def update_settings(data: ShopMode, db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    row = AppSettings.get(db)
    row.shop_via_origin = data.shop_via_origin
    db.commit()
    set_shop_via_origin(data.shop_via_origin)  # long-lived sessions rebuild on their next request
    logger.info(f"[Settings] shop_via_origin set to {data.shop_via_origin}")
    return data
