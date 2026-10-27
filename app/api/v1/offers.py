from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.offer import OfferCreate, OfferFilterParams, OfferRead, OfferUpdate
from app.services import offer_service

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=Page[OfferRead])
def list_offers(db: DbSession, _: CurrentUser, params: Annotated[OfferFilterParams, Query()]):
    return offer_service.list_offers(db, params)


@router.get("/{offer_id}", response_model=OfferRead)
def get_offer(offer_id: int, db: DbSession, _: CurrentUser):
    return offer_service.get_offer(db, offer_id)


@router.post("", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
def create_offer(payload: OfferCreate, db: DbSession, user: CurrentUser):
    return offer_service.create_offer(db, payload, user)


@router.patch("/{offer_id}", response_model=OfferRead)
def update_offer(offer_id: int, payload: OfferUpdate, db: DbSession, user: CurrentUser):
    return offer_service.update_offer(db, offer_id, payload, user)


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer(offer_id: int, db: DbSession, user: CurrentUser):
    offer_service.delete_offer(db, offer_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
