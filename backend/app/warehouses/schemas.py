"""
Pydantic-схеми для API складів.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class WarehouseBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        examples=["Основний склад"],
    )
    address: str | None = Field(
        default=None,
        max_length=500,
        examples=["м. Шаблонна, вул. Шевченка, 12"],
    )
    total_area: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        examples=["1500.00"],
        description="Загальна площа складу (м²), має бути > 0",
    )

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Назва складу не може бути порожньою або складатися лише з пробілів")
        return v.strip()

    @field_validator("address")
    @classmethod
    def address_strip(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped or None
        return v


class WarehouseCreate(WarehouseBase):
    """Тіло запиту для створення нового складу."""


class WarehouseUpdate(BaseModel):
    """Тіло запиту для часткового оновлення складу (всі поля необов'язкові)."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
        examples=["Склад №2"],
    )
    address: str | None = Field(
        default=None,
        max_length=500,
        examples=["м. Шаблонна, вул. Шевченка, 12"],
    )
    total_area: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
        examples=["800.50"],
        description="Нова площа складу (м²), має бути > 0",
    )

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError(
                    "Назва складу не може бути порожньою або складатися лише з пробілів"
                )
            return stripped
        return v

    @field_validator("address")
    @classmethod
    def address_strip(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped or None
        return v


class WarehouseResponse(BaseModel):
    """Відповідь з даними складу."""

    warehouse_id: int
    warehouse_name: str
    warehouse_address: str | None
    total_warehouse_area: Decimal

    model_config = {"from_attributes": True}


# ── Rack ──────────────────────────────────────────────────────────────────────

class RackSummaryResponse(BaseModel):
    """Коротка інформація про стелаж у списку."""

    rack_id: int
    rack_code: str
    shelves_count: int
    fill_percent: float


class ShelfInfoResponse(BaseModel):
    """Інформація про полицю у деталях стелажа."""

    shelf_id: int
    shelf_code: str
    product_name: str | None  # завжди null — товари ще не реалізовані
    occupied: int             # 1 if is_occupied else 0
    capacity: int             # завжди 1
    shelf_status: str


class RackDetailsResponse(BaseModel):
    """Детальна інформація про стелаж разом із полицями."""

    rack_id: int
    rack_code: str
    zone_name: str | None     # завжди null
    updated_at: str | None    # None (поле відсутнє в моделі)
    shelves: list[ShelfInfoResponse]


# ── Shelf CRUD ────────────────────────────────────────────────────────────────

from decimal import Decimal as _Decimal  # noqa: E402  (вже імпортовано вгорі)
from app.core.enums import ShelfStatus, InactiveReason  # noqa: E402


class ShelfCreate(BaseModel):
    """Тіло запиту для створення нової полиці."""

    code: str = Field(..., max_length=50, description="Код полиці (унікальний у стелажі)")
    width: _Decimal = Field(..., gt=0, decimal_places=2)
    length: _Decimal = Field(..., gt=0, decimal_places=2)
    height: _Decimal = Field(..., gt=0, decimal_places=2)
    max_weight: _Decimal = Field(..., gt=0, decimal_places=3)
    status: ShelfStatus = ShelfStatus.ACTIVE
    inactive_reason: InactiveReason | None = None

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Код полиці не може бути порожнім або складатися лише з пробілів")
        return stripped


class ShelfUpdate(BaseModel):
    """Тіло запиту для часткового оновлення полиці (всі поля необов'язкові)."""

    width: _Decimal | None = Field(default=None, gt=0)
    length: _Decimal | None = Field(default=None, gt=0)
    height: _Decimal | None = Field(default=None, gt=0)
    max_weight: _Decimal | None = Field(default=None, gt=0)
    status: ShelfStatus | None = None
    inactive_reason: InactiveReason | None = None


class ShelfResponse(BaseModel):
    """Відповідь з повними даними полиці."""

    shelf_id: int
    shelf_code: str
    qr: str
    rack_id: int
    width: _Decimal
    length: _Decimal
    height: _Decimal
    max_weight: _Decimal
    is_occupied: bool
    status: str
    inactive_reason: str | None
    volume_m3: float
