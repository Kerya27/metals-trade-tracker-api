from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    country: Mapped[str] = mapped_column(String(2))  # ISO 3166-1 alpha-2, e.g. "UA", "CZ"
    contact_email: Mapped[str] = mapped_column(String(320))
