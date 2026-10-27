from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.common import Page, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services import supplier_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=Page[SupplierRead])
def list_suppliers(db: DbSession, _: CurrentUser, params: Annotated[PaginationParams, Query()]):
    return supplier_service.list_suppliers(db, params)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, db: DbSession, _: CurrentUser):
    return supplier_service.get_supplier(db, supplier_id)


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: DbSession, _: AdminUser):
    return supplier_service.create_supplier(db, payload)


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(supplier_id: int, payload: SupplierUpdate, db: DbSession, _: AdminUser):
    return supplier_service.update_supplier(db, supplier_id, payload)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int, db: DbSession, _: AdminUser):
    supplier_service.delete_supplier(db, supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
