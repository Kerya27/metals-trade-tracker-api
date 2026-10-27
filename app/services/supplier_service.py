from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Offer, Supplier
from app.schemas.common import Page, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate


def list_suppliers(db: Session, params: PaginationParams) -> Page[SupplierRead]:
    total = db.scalar(select(func.count()).select_from(Supplier)) or 0
    rows = db.scalars(
        select(Supplier)
        .order_by(Supplier.name, Supplier.id)
        .limit(params.limit)
        .offset(params.offset)
    ).all()
    return Page[SupplierRead](
        items=[SupplierRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return supplier


def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> Supplier:
    supplier = get_supplier(db, supplier_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


def delete_supplier(db: Session, supplier_id: int) -> None:
    supplier = get_supplier(db, supplier_id)
    if db.scalar(select(exists().where(Offer.supplier_id == supplier_id))):
        raise ConflictError("Supplier has offers and cannot be deleted", code="supplier_has_offers")
    db.delete(supplier)
    db.commit()
