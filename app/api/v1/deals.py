from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.deal import (
    DealCreate,
    DealFilterParams,
    DealHistoryRead,
    DealRead,
    DealTransitionRequest,
)
from app.services import deal_service

router = APIRouter(prefix="/deals", tags=["deals"])


@router.post("", response_model=DealRead, status_code=status.HTTP_201_CREATED)
def create_deal(payload: DealCreate, db: DbSession, user: CurrentUser):
    return deal_service.create_deal(db, payload, user)


@router.get("", response_model=Page[DealRead])
def list_deals(db: DbSession, user: CurrentUser, params: Annotated[DealFilterParams, Query()]):
    return deal_service.list_deals(db, user, params)


@router.get("/{deal_id}", response_model=DealRead)
def get_deal(deal_id: int, db: DbSession, user: CurrentUser):
    return deal_service.get_deal(db, deal_id, user)


@router.post("/{deal_id}/transition", response_model=DealRead)
def transition_deal(deal_id: int, payload: DealTransitionRequest, db: DbSession, user: CurrentUser):
    return deal_service.transition_deal(db, deal_id, payload, user)


@router.get("/{deal_id}/history", response_model=list[DealHistoryRead])
def get_deal_history(deal_id: int, db: DbSession, user: CurrentUser):
    return deal_service.get_history(db, deal_id, user)
