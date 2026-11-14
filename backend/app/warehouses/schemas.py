
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    pass

class WarehouseUpdate(BaseModel):
    

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

    @model_validator(mode="after")
    def required_fields_not_null(self) -> "WarehouseUpdate":
        for field in ("name", "total_area"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Поле {field} не може бути null")
        return self

class WarehouseResponse(BaseModel):
    

    warehouse_id: int
    warehouse_name: str
    warehouse_address: str | None
    total_warehouse_area: Decimal

    model_config = {"from_attributes": True}

class RackSummaryResponse(BaseModel):
    

    rack_id: int
    rack_code: str
    shelves_count: int
    fill_percent: float
    volume_fill_percent: float = 0.0
    weight_fill_percent: float = 0.0
    used_volume_m3: float = 0.0
    total_volume_m3: float = 0.0
    used_weight_kg: float = 0.0
    total_max_weight_kg: float = 0.0
    shelves_used: int = 0
    overloaded: bool = False

class ShelfInfoResponse(BaseModel):
    

    shelf_id: int
    shelf_code: str
    product_name: str | None  # завжди null — товари ще не реалізовані
    occupied: int             # 1 if is_occupied else 0
    capacity: int             # завжди 1
    shelf_status: str
    volume_fill_percent: float = 0.0
    weight_fill_percent: float = 0.0
    used_volume_m3: float = 0.0
    total_volume_m3: float = 0.0
    used_weight_kg: float = 0.0
    total_max_weight_kg: float = 0.0
    items_count: int = 0
    overloaded: bool = False

class RackDetailsResponse(BaseModel):
    

    rack_id: int
    rack_code: str
    zone_name: str | None     # завжди null
    updated_at: str | None    # None (поле відсутнє в моделі)
    shelves: list[ShelfInfoResponse]
    volume_fill_percent: float = 0.0
    weight_fill_percent: float = 0.0
    used_volume_m3: float = 0.0
    total_volume_m3: float = 0.0
    used_weight_kg: float = 0.0
    total_max_weight_kg: float = 0.0

from decimal import Decimal as _Decimal  # noqa: E402  (вже імпортовано вгорі)
from app.core.enums import ShelfStatus, InactiveReason  # noqa: E402

class ShelfCreate(BaseModel):
    

    code: str = Field(..., max_length=50, description="Код полиці (унікальний у стелажі)")
    width: _Decimal = Field(..., gt=0, max_digits=8, decimal_places=2)
    length: _Decimal = Field(..., gt=0, max_digits=8, decimal_places=2)
    height: _Decimal = Field(..., gt=0, max_digits=8, decimal_places=2)
    max_weight: _Decimal = Field(..., gt=0, max_digits=10, decimal_places=3)
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
    

    width: _Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    length: _Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    height: _Decimal | None = Field(default=None, gt=0,max_digits=8, decimal_places=2)
    max_weight: _Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    status: ShelfStatus | None = None
    inactive_reason: InactiveReason | None = None

class ShelfResponse(BaseModel):
    

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
    used_volume_m3: float = 0.0
    used_weight_kg: float = 0.0
    volume_fill_percent: float = 0.0
    weight_fill_percent: float = 0.0
    free_volume_m3: float = 0.0
    free_weight_kg: float = 0.0
    items_count: int = 0
    overloaded: bool = False
