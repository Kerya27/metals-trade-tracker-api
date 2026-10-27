from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Deal, DealStatus, DealStatusHistory, OfferStatus, User
from app.schemas.common import Page
from app.schemas.deal import DealCreate, DealFilterParams, DealRead, DealTransitionRequest
from app.services.deal_state_machine import assert_transition
from app.services.offer_service import get_offer


def _visible_deals(user: User) -> Select[tuple[Deal]]:
    """Admins see every deal; traders only their own."""
    stmt = select(Deal)
    if not user.is_admin:
        stmt = stmt.where(Deal.created_by == user.id)
    return stmt


def _record_history(
    db: Session,
    deal: Deal,
    from_status: DealStatus | None,
    to_status: DealStatus,
    user: User,
    comment: str | None,
) -> None:
    db.add(
        DealStatusHistory(
            deal_id=deal.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=user.id,
            comment=comment,
        )
    )


def get_deal(db: Session, deal_id: int, user: User, *, for_update: bool = False) -> Deal:
    stmt = _visible_deals(user).where(Deal.id == deal_id)
    if for_update:
        stmt = stmt.with_for_update()
    deal = db.scalar(stmt)
    if deal is None:
        # Same 404 for "does not exist" and "belongs to someone else" -> no information leak.
        raise NotFoundError(f"Deal {deal_id} not found")
    return deal


def list_deals(db: Session, user: User, params: DealFilterParams) -> Page[DealRead]:
    stmt = _visible_deals(user)
    if params.status:
        stmt = stmt.where(Deal.status == params.status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Deal.created_at.desc(), Deal.id.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    return Page[DealRead](
        items=[DealRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def create_deal(db: Session, data: DealCreate, user: User) -> Deal:
    offer = get_offer(db, data.offer_id)
    if offer.status != OfferStatus.ACTIVE:
        raise ConflictError(f"Offer {offer.id} is not active", code="offer_not_active")
    if data.quantity_tonnes > offer.quantity_tonnes:
        raise BusinessRuleError(
            f"Deal quantity {data.quantity_tonnes} t exceeds offer quantity "
            f"{offer.quantity_tonnes} t"
        )

    deal = Deal(**data.model_dump(), status=DealStatus.DRAFT, created_by=user.id)
    db.add(deal)
    db.flush()  # assigns deal.id inside the same transaction
    _record_history(db, deal, None, DealStatus.DRAFT, user, "Deal created")
    db.commit()
    db.refresh(deal)
    return deal


def transition_deal(db: Session, deal_id: int, data: DealTransitionRequest, user: User) -> Deal:
    """Change status and write the history row in ONE transaction.

    The deal row is locked (SELECT ... FOR UPDATE) so two concurrent transitions
    cannot both pass validation against the same old status.
    """
    deal = get_deal(db, deal_id, user, for_update=True)
    assert_transition(deal.status, data.status)

    previous = deal.status
    deal.status = data.status
    _record_history(db, deal, previous, data.status, user, data.comment)
    db.commit()  # both changes are committed together, or neither is
    db.refresh(deal)
    return deal


def get_history(db: Session, deal_id: int, user: User) -> list[DealStatusHistory]:
    get_deal(db, deal_id, user)  # visibility check (404 for foreign deals)
    return list(
        db.scalars(
            select(DealStatusHistory)
            .where(DealStatusHistory.deal_id == deal_id)
            .order_by(DealStatusHistory.changed_at, DealStatusHistory.id)
        )
    )
