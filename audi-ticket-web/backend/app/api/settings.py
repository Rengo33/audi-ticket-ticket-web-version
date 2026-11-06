"""Runtime app settings the UI can flip without a restart."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..bot.core import set_shop_via_origin, set_cart_via_regiondo
from ..database import get_db
from ..models import AppSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class ShopMode(BaseModel):
    shop_via_origin: bool
    cart_via_regiondo: bool = False


@router.get("", response_model=ShopMode)
async def read_settings(db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    row = AppSettings.get(db)
    return ShopMode(shop_via_origin=row.shop_via_origin,
                    cart_via_regiondo=bool(row.cart_via_regiondo))


@router.put("", response_model=ShopMode)
async def update_settings(data: ShopMode, db: Session = Depends(get_db), _: bool = Depends(get_current_user)):
    row = AppSettings.get(db)
    row.shop_via_origin = data.shop_via_origin
    row.cart_via_regiondo = data.cart_via_regiondo
    db.commit()
    # long-lived sessions rebuild on their next request
    set_shop_via_origin(data.shop_via_origin)
    set_cart_via_regiondo(data.cart_via_regiondo)
    logger.info(f"[Settings] shop_via_origin={data.shop_via_origin} cart_via_regiondo={data.cart_via_regiondo}")
    return data
