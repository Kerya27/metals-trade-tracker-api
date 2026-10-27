from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DealStatus
from app.schemas.offer import Price, Tonnes


class DealCreate(BaseModel):
    offer_id: int
    buyer_name: str = Field(min_length=1, max_length=200, examples=["Brno Foundry s.r.o."])
    agreed_price_per_tonne: Price
    quantity_tonnes: Tonnes


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    buyer_name: str
    agreed_price_per_tonne: Decimal
    quantity_tonnes: Decimal
    status: DealStatus
    created_by: int
    created_at: datetime


class DealTransitionRequest(BaseModel):
    status: DealStatus = Field(examples=["NEGOTIATION"])
    comment: str | None = Field(default=None, max_length=1000)


class DealFilterParams(BaseModel):
    status: DealStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class DealHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: int
    from_status: DealStatus | None
    to_status: DealStatus
    changed_by: int
    changed_at: datetime
    comment: str | None
