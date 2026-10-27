from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, str_enum
from app.models.enums import DealStatus


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="RESTRICT"), index=True)
    buyer_name: Mapped[str] = mapped_column(String(200))
    agreed_price_per_tonne: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    quantity_tonnes: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    status: Mapped[DealStatus] = mapped_column(
        str_enum(DealStatus), default=DealStatus.DRAFT, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DealStatusHistory(Base):
    """Append-only audit log. UPDATE/DELETE are blocked by a DB trigger (see migration)."""

    __tablename__ = "deal_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), index=True)
    from_status: Mapped[DealStatus | None] = mapped_column(str_enum(DealStatus), nullable=True)
    to_status: Mapped[DealStatus] = mapped_column(str_enum(DealStatus))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
