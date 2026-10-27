from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Currency, Incoterm, OfferStatus

Tonnes = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3, examples=["120.5"])]
Price = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2, examples=["310.00"])]

OfferSort = Literal[
    "created_at",
    "-created_at",
    "price_per_tonne",
    "-price_per_tonne",
    "quantity_tonnes",
    "-quantity_tonnes",
]


class OfferCreate(BaseModel):
    supplier_id: int
    material: str = Field(min_length=1, max_length=100, examples=["aluminium dross"])
    quantity_tonnes: Tonnes
    price_per_tonne: Price
    currency: Currency
    incoterm: Incoterm


class OfferUpdate(BaseModel):
    material: str | None = Field(default=None, min_length=1, max_length=100)
    quantity_tonnes: Tonnes | None = None
    price_per_tonne: Price | None = None
    currency: Currency | None = None
    incoterm: Incoterm | None = None
    status: OfferStatus | None = None


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    material: str
    quantity_tonnes: Decimal
    price_per_tonne: Decimal
    currency: Currency
    incoterm: Incoterm
    status: OfferStatus
    created_by: int
    created_at: datetime


class OfferFilterParams(BaseModel):
    """Query parameters for GET /offers."""

    material: str | None = Field(default=None, description="Case-insensitive substring match")
    status: OfferStatus | None = None
    currency: Currency | None = None
    supplier_id: int | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    sort: OfferSort = "-created_at"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_price_range(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must be less than or equal to max_price")
        return self
