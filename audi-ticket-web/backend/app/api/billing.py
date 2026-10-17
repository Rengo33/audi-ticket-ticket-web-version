"""
Billing profile management API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import BillingProfile, CartSession
from ..crypto import encrypt, decrypt

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingProfileCreate(BaseModel):
    name: str
    firstname: str
    lastname: str
    email: str
    telephone: str
    stammnummer: str
    department: str = ""
    invoice_recipient: str = ""
    invoice_company: str = ""
    invoice_tax_id: str = ""
    invoice_street: str = ""
    invoice_postcode: str = ""
    invoice_city: str = ""
    invoice_country: str = "DE"
    card_number: str = ""
    card_exp_month: str = ""
    card_exp_year: str = ""
    card_cvc: str = ""


class BillingProfileResponse(BaseModel):
    id: int
    name: str
    firstname: str
    lastname: str
    email: str
    telephone: str
    stammnummer: str
    department: str
    invoice_recipient: str
    invoice_company: str
    invoice_tax_id: str
    invoice_street: str
    invoice_postcode: str
    invoice_city: str
    invoice_country: str
    card_last4: str
    has_card: bool

    class Config:
        from_attributes = True


def _to_response(profile: BillingProfile) -> BillingProfileResponse:
    return BillingProfileResponse(
        id=profile.id,
        name=profile.name,
        firstname=profile.firstname,
        lastname=profile.lastname,
        email=profile.email,
        telephone=profile.telephone,
        stammnummer=profile.stammnummer,
        department=profile.department or "",
        invoice_recipient=profile.invoice_recipient or "",
        invoice_company=profile.invoice_company or "",
        invoice_tax_id=profile.invoice_tax_id or "",
        invoice_street=profile.invoice_street or "",
        invoice_postcode=profile.invoice_postcode or "",
        invoice_city=profile.invoice_city or "",
        invoice_country=profile.invoice_country or "DE",
        card_last4=profile.card_last4 or "",
        has_card=bool(profile.card_number_enc),
    )


@router.get("/profiles", response_model=List[BillingProfileResponse])
async def list_profiles(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    profiles = db.query(BillingProfile).order_by(BillingProfile.name).all()
    return [_to_response(p) for p in profiles]


@router.post("/profiles", response_model=BillingProfileResponse)
async def create_profile(
    data: BillingProfileCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    profile = BillingProfile(
        name=data.name,
        firstname=data.firstname,
        lastname=data.lastname,
        email=data.email,
        telephone=data.telephone,
        stammnummer=data.stammnummer,
        department=data.department,
        invoice_recipient=data.invoice_recipient,
        invoice_company=data.invoice_company,
        invoice_tax_id=data.invoice_tax_id,
        invoice_street=data.invoice_street,
        invoice_postcode=data.invoice_postcode,
        invoice_city=data.invoice_city,
        invoice_country=data.invoice_country,
        card_number_enc=encrypt(data.card_number),
        card_exp_month_enc=encrypt(data.card_exp_month),
        card_exp_year_enc=encrypt(data.card_exp_year),
        card_cvc_enc=encrypt(data.card_cvc),
        card_last4=data.card_number[-4:] if len(data.card_number) >= 4 else "",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_response(profile)


@router.put("/profiles/{profile_id}", response_model=BillingProfileResponse)
async def update_profile(
    profile_id: int,
    data: BillingProfileCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    profile = db.query(BillingProfile).filter(BillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    profile.name = data.name
    profile.firstname = data.firstname
    profile.lastname = data.lastname
    profile.email = data.email
    profile.telephone = data.telephone
    profile.stammnummer = data.stammnummer
    profile.department = data.department
    profile.invoice_recipient = data.invoice_recipient
    profile.invoice_company = data.invoice_company
    profile.invoice_tax_id = data.invoice_tax_id
    profile.invoice_street = data.invoice_street
    profile.invoice_postcode = data.invoice_postcode
    profile.invoice_city = data.invoice_city
    profile.invoice_country = data.invoice_country

    # Only update card if new card provided
    if data.card_number:
        profile.card_number_enc = encrypt(data.card_number)
        profile.card_exp_month_enc = encrypt(data.card_exp_month)
        profile.card_exp_year_enc = encrypt(data.card_exp_year)
        profile.card_cvc_enc = encrypt(data.card_cvc)
        profile.card_last4 = data.card_number[-4:] if len(data.card_number) >= 4 else ""

    db.commit()
    db.refresh(profile)
    return _to_response(profile)


class ProfileUsageEntry(BaseModel):
    profile_id: int
    used: bool
    used_cart_id: Optional[int] = None


@router.get("/profiles/usage", response_model=List[ProfileUsageEntry])
async def profile_usage(
    event_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user),
):
    """Per-profile usage for a given event.

    Profiles become 'used' the moment a CartSession with their ID transitions
    to `completed` for this event_id. Reset happens implicitly when the event
    changes.
    """
    profiles = db.query(BillingProfile.id).all()
    used_map: dict[int, int] = {}
    if event_id:
        rows = (
            db.query(CartSession.billing_profile_id, CartSession.id)
            .filter(
                CartSession.event_id == event_id,
                CartSession.checkout_status == "completed",
                CartSession.billing_profile_id.isnot(None),
            )
            .all()
        )
        for pid, cart_id in rows:
            used_map.setdefault(pid, cart_id)
    return [
        ProfileUsageEntry(
            profile_id=p.id,
            used=p.id in used_map,
            used_cart_id=used_map.get(p.id),
        )
        for p in profiles
    ]


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    profile = db.query(BillingProfile).filter(BillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()
    return {"success": True}
