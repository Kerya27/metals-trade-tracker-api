from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models import Deal, Offer, User
from app.schemas.common import Page
from app.schemas.offer import OfferCreate, OfferFilterParams, OfferRead, OfferUpdate
from app.services.supplier_service import get_supplier

_SORT_COLUMNS = {
    "created_at": Offer.created_at,
    "price_per_tonne": Offer.price_per_tonne,
    "quantity_tonnes": Offer.quantity_tonnes,
}


def list_offers(db: Session, params: OfferFilterParams) -> Page[OfferRead]:
    stmt = select(Offer)
    if params.material:
        stmt = stmt.where(Offer.material.ilike(f"%{params.material.strip()}%"))
    if params.status:
        stmt = stmt.where(Offer.status == params.status)
    if params.currency:
        stmt = stmt.where(Offer.currency == params.currency)
    if params.supplier_id is not None:
        stmt = stmt.where(Offer.supplier_id == params.supplier_id)
    if params.min_price is not None:
        stmt = stmt.where(Offer.price_per_tonne >= params.min_price)
    if params.max_price is not None:
        stmt = stmt.where(Offer.price_per_tonne <= params.max_price)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    descending = params.sort.startswith("-")
    column = _SORT_COLUMNS[params.sort.lstrip("-")]
    order = column.desc() if descending else column.asc()
    # Secondary sort by id keeps pagination stable when values are equal.
    tie_breaker = Offer.id.desc() if descending else Offer.id.asc()
    rows = db.scalars(stmt.order_by(order, tie_breaker).limit(params.limit).offset(params.offset))

    return Page[OfferRead](
        items=[OfferRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def get_offer(db: Session, offer_id: int) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise NotFoundError(f"Offer {offer_id} not found")
    return offer


def _ensure_can_modify(offer: Offer, user: User) -> None:
    if not user.is_admin and offer.created_by != user.id:
        raise PermissionDeniedError("Only the offer's creator or an admin can modify it")


def create_offer(db: Session, data: OfferCreate, user: User) -> Offer:
    get_supplier(db, data.supplier_id)  # 404 if supplier does not exist
    offer = Offer(**data.model_dump(), created_by=user.id)
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def update_offer(db: Session, offer_id: int, data: OfferUpdate, user: User) -> Offer:
    offer = get_offer(db, offer_id)
    _ensure_can_modify(offer, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(offer, field, value)
    db.commit()
    db.refresh(offer)
    return offer


def delete_offer(db: Session, offer_id: int, user: User) -> None:
    offer = get_offer(db, offer_id)
    _ensure_can_modify(offer, user)
    if db.scalar(select(exists().where(Deal.offer_id == offer_id))):
        raise ConflictError(
            "Offer has deals and cannot be deleted; close it instead", code="offer_has_deals"
        )
    db.delete(offer)
    db.commit()
