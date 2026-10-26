"""REST-ендпоінти товарів: CRUD, імпорт та експорт."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_async_session
from app.core.enums import UnitOfMeasure
from app.core.rbac import PRODUCT_DELETE_ROLES, PRODUCT_WRITE_ROLES
from app.products import crud, transfer
from app.products.schemas import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    ImportReport,
    ProductCreate,
    ProductListResponse,
    ProductRead,
    ProductUpdate,
)
from app.utils.security import get_current_user, require_roles

# ── Товари ─────────────────────────────────────────────────────────────────

router = APIRouter(
    prefix="/api/v1/products",
    tags=["Products"],
    dependencies=[Depends(get_current_user)],
)

write_guard = Depends(require_roles(*PRODUCT_WRITE_ROLES))
delete_guard = Depends(require_roles(*PRODUCT_DELETE_ROLES))


def _product_read(product) -> ProductRead:
    return ProductRead(
        product_id=product.id,
        sku_code=product.sku_code,
        name=product.name,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        unit_of_measure=product.unit_of_measure,
        width=product.width,
        length=product.length,
        height=product.height,
        weight=product.weight,
        min_stock_level=product.min_stock_level,
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    search: str | None = Query(None, max_length=100, description="Пошук за артикулом або назвою"),
    category_id: int | None = Query(None, gt=0),
    unit_of_measure: UnitOfMeasure | None = Query(None),
    sort_by: str = Query("product_id", pattern="^(product_id|sku_code|name|weight|min_stock_level)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    products, total = await crud.list_products(
        session,
        search=search,
        category_id=category_id,
        unit_of_measure=unit_of_measure,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return ProductListResponse(
        items=[_product_read(product) for product in products],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


# ── Імпорт / експорт (статичні шляхи — до /{product_id}) ───────────────────

@router.get("/export")
async def export_products(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    search: str | None = Query(None, max_length=100),
    category_id: int | None = Query(None, gt=0),
    unit_of_measure: UnitOfMeasure | None = Query(None),
    sort_by: str = Query("product_id", pattern="^(product_id|sku_code|name|weight|min_stock_level)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_async_session),
):
    """Експорт каталогу товарів у CSV або Excel."""
    products = await crud.iter_products(
        session,
        search=search,
        category_id=category_id,
        unit_of_measure=unit_of_measure,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    if format == "xlsx":
        content = transfer.build_xlsx(products)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = transfer.build_csv(products)
        media_type = "text/csv; charset=utf-8"

    filename = transfer.export_filename(format)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Total-Count": str(len(products)),
        },
    )


@router.get("/import/template")
async def download_import_template(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    """Шаблон файлу для імпорту товарів."""
    content = transfer.build_template(format)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if format == "xlsx"
        else "text/csv; charset=utf-8"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="products_template.{format}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/import",
    response_model=ImportReport,
    dependencies=[write_guard],
    responses={
        200: {"description": "Файл оброблено; помилки окремих рядків — у звіті"},
        413: {"description": "Файл завеликий"},
        422: {"description": "Некоректна структура файлу"},
    },
)
async def import_products(
    file: UploadFile = File(..., description="Файл .csv або .xlsx"),
    session: AsyncSession = Depends(get_async_session),
):
    """Імпорт товарів із CSV/XLSX зі звітом про помилки по рядках.

    Коректні рядки зберігаються, некоректні — потрапляють у `errors`
    (номер рядка, артикул, поле, причина).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Не вказано імʼя файлу",
        )

    content = await file.read()
    if len(content) > transfer.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл завеликий: максимум {settings.IMPORT_MAX_FILE_MB} МБ",
        )

    try:
        report = await transfer.import_products(session, file.filename, content)
    except transfer.ImportFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return report


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    product = await crud.get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не знайдено")
    return _product_read(product)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_guard],
)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        product = await crud.create_product(session, payload)
    except crud.SkuAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Товар з артикулом {exc.args[0]} вже існує",
        ) from exc
    except crud.CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Вказаної категорії не існує",
        ) from exc
    return _product_read(product)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    dependencies=[write_guard],
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    product = await crud.get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не знайдено")

    try:
        updated = await crud.update_product(session, product, payload)
    except crud.SkuAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Товар з артикулом {exc.args[0]} вже існує",
        ) from exc
    except crud.CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Вказаної категорії не існує",
        ) from exc
    return _product_read(updated)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[delete_guard],
)
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    product = await crud.get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не знайдено")
    await crud.delete_product(session, product)
    return None


# ── Категорії ──────────────────────────────────────────────────────────────

categories_router = APIRouter(
    prefix="/api/v1/categories",
    tags=["Categories"],
    dependencies=[Depends(get_current_user)],
)


@categories_router.get("", response_model=list[CategoryRead])
async def list_categories(session: AsyncSession = Depends(get_async_session)):
    rows = await crud.list_categories(session)
    return [
        CategoryRead(
            category_id=category.id,
            name=category.name,
            description=category.description,
            products_count=count,
        )
        for category, count in rows
    ]


@categories_router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_guard],
)
async def create_category(
    payload: CategoryCreate,
    session: AsyncSession = Depends(get_async_session),
):
    existing = await crud.find_category_by_name(session, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Категорія з такою назвою вже існує",
        )
    category = await crud.create_category(session, payload)
    return CategoryRead(
        category_id=category.id,
        name=category.name,
        description=category.description,
        products_count=0,
    )


@categories_router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    dependencies=[write_guard],
)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    category = await crud.get_category(session, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категорію не знайдено")

    if payload.name and payload.name.lower() != category.name.lower():
        duplicate = await crud.find_category_by_name(session, payload.name)
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Категорія з такою назвою вже існує",
            )

    updated = await crud.update_category(session, category, payload)
    count = await crud.count_products_in_category(session, updated.id)
    return CategoryRead(
        category_id=updated.id,
        name=updated.name,
        description=updated.description,
        products_count=count,
    )


@categories_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[delete_guard],
)
async def delete_category(
    category_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    category = await crud.get_category(session, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категорію не знайдено")

    if await crud.count_products_in_category(session, category_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не можна видалити категорію, у якій є товари",
        )

    await crud.delete_category(session, category)
    return None
