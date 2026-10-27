from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, str_enum
from app.models.enums import Currency, Incoterm, OfferStatus


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    material: Mapped[str] = mapped_column(String(100), index=True)
    quantity_tonnes: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    price_per_tonne: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[Currency] = mapped_column(str_enum(Currency))
    incoterm: Mapped[Incoterm] = mapped_column(str_enum(Incoterm))
    status: Mapped[OfferStatus] = mapped_column(
        str_enum(OfferStatus), default=OfferStatus.ACTIVE, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
