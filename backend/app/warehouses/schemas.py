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
