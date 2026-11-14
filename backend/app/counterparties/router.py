import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_async_session
from app.core.enums import SupplierStatus, RecipientStatus
from app.core.rbac import DIRECTORY_MANAGE_ROLES
from app.counterparties import crud
from app.counterparties.schemas import (
    SupplierCreate,
    SupplierListResponse,
    SupplierRead,
    SupplierUpdate,
    RecipientCreate,
    RecipientListResponse,
    RecipientRead,
    RecipientUpdate,
)
from app.products.models import Supplier, Recipient
from app.utils.security import require_roles


# Постачальники ──────────────────────────────────────────────────────────

suppliers_router = APIRouter(
    prefix="/api/v1/suppliers",
    tags=["Suppliers"],
    dependencies=[Depends(require_roles(*DIRECTORY_MANAGE_ROLES))],
)


def to_supplier_read(supplier: Supplier) -> SupplierRead:
    return SupplierRead(
        supplier_id=supplier.id,
        company_name=supplier.company_name,
        tax_id=supplier.tax_id,
        contact_person=supplier.contact_person,
        phone_number=supplier.phone_number,
        email=supplier.email,
        address=supplier.address,
        status=supplier.status,
        created_at=supplier.created_at,
    )


async def get_supplier_or_404(session: AsyncSession, supplier_id: int) -> Supplier:
    supplier = await crud.get_supplier(session, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Постачальника не знайдено")
    return supplier

TAX_ID_CONFLICT = "Постачальник з таким ЄДРПОУ / ІПН уже існує"

async def ensure_tax_id_is_free(
    session: AsyncSession, tax_id: str | None, exclude_id: int | None = None
) -> None:
    if tax_id is None:
        return
    if await crud.find_supplier_by_tax_id(session, tax_id, exclude_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=TAX_ID_CONFLICT,
        )


@suppliers_router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    search: str | None = Query(None, max_length=100),
    status_filter: SupplierStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    suppliers, total = await crud.list_suppliers(
        session, search=search, status=status_filter, page=page, page_size=page_size
    )
    return SupplierListResponse(
        items=[to_supplier_read(supplier) for supplier in suppliers],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@suppliers_router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: int, session: AsyncSession = Depends(get_async_session)):
    supplier = await get_supplier_or_404(session, supplier_id)
    return to_supplier_read(supplier)


@suppliers_router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(payload: SupplierCreate, session: AsyncSession = Depends(get_async_session)):
    await ensure_tax_id_is_free(session, payload.tax_id)
    try:
        supplier = await crud.create_supplier(session, payload)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=TAX_ID_CONFLICT)
    return to_supplier_read(supplier)


@suppliers_router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    supplier = await get_supplier_or_404(session, supplier_id)
    if "tax_id" in payload.model_fields_set:
        await ensure_tax_id_is_free(session, payload.tax_id, exclude_id=supplier.id)
    try:
        supplier = await crud.update_supplier(session, supplier, payload)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=TAX_ID_CONFLICT)
    return to_supplier_read(supplier)
    

@suppliers_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: int, session: AsyncSession = Depends(get_async_session)):
    supplier = await get_supplier_or_404(session, supplier_id)
    if await crud.supplier_has_inbound_orders(session, supplier.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Постачальника не можна видалити: на нього посилаються прихідні накладні. "
                "Переведіть його в статус inactive (архів)."
            ),
        )
    await crud.delete_supplier(session, supplier)
    return None



# Одержувачі ──────────────────────────────────────────────────────────

recipients_router = APIRouter(
    prefix="/api/v1/recipients",
    tags=["Recipients"],
    dependencies=[Depends(require_roles(*DIRECTORY_MANAGE_ROLES))],
)


def to_recipient_read(recipient: Recipient) -> RecipientRead:
    return RecipientRead(
        recipient_id=recipient.id,
        company_name=recipient.company_name,
        tax_id=recipient.tax_id,
        contact_person=recipient.contact_person,
        phone_number=recipient.phone_number,
        email=recipient.email,
        address=recipient.address,
        status=recipient.status,
        created_at=recipient.created_at,
    )


async def get_recipient_or_404(session: AsyncSession, recipient_id: int) -> Recipient:
    recipient = await crud.get_recipient(session, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Одержувача не знайдено")
    return recipient


@recipients_router.get("", response_model=RecipientListResponse)
async def list_recipients(
    search: str | None = Query(None, max_length=100),
    status_filter: RecipientStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    recipients, total = await crud.list_recipients(
        session, search=search, status=status_filter, page=page, page_size=page_size
    )
    return RecipientListResponse(
        items=[to_recipient_read(recipient) for recipient in recipients],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@recipients_router.get("/{recipient_id}", response_model=RecipientRead)
async def get_recipient(recipient_id: int, session: AsyncSession = Depends(get_async_session)):
    recipient = await get_recipient_or_404(session, recipient_id)
    return to_recipient_read(recipient)


@recipients_router.post("", response_model=RecipientRead, status_code=status.HTTP_201_CREATED)
async def create_recipient(payload: RecipientCreate, session: AsyncSession = Depends(get_async_session)):
    recipient = await crud.create_recipient(session, payload)
    return to_recipient_read(recipient)


@recipients_router.patch("/{recipient_id}", response_model=RecipientRead)
async def update_recipient(
    recipient_id: int,
    payload: RecipientUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    recipient = await get_recipient_or_404(session, recipient_id)
    recipient = await crud.update_recipient(session, recipient, payload)
    return to_recipient_read(recipient)


@recipients_router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipient(recipient_id: int, session: AsyncSession = Depends(get_async_session)):
    recipient = await get_recipient_or_404(session, recipient_id)
    if await crud.recipient_has_outbound_orders(session, recipient.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Одержувача не можна видалити: на нього посилаються вихідні накладні. "
                "Замість видалення переведіть його в статус inactive (архів)."
            ),
        )
    await crud.delete_recipient(session, recipient)
    return None