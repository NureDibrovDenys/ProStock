"""Схеми товарів, категорій та звіту імпорту."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import UnitOfMeasure


def _clean_str(value: str) -> str:
    return " ".join(value.split()).strip()


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Назва категорії")
    description: str | None = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = _clean_str(value)
        if not cleaned:
            raise ValueError("Назва категорії не може бути порожньою")
        return cleaned


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = _clean_str(value)
        if not cleaned:
            raise ValueError("Назва категорії не може бути порожньою")
        return cleaned


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    name: str
    description: str | None = None
    products_count: int = 0


class ProductBase(BaseModel):
    sku_code: str = Field(..., min_length=1, max_length=100, description="Унікальний артикул")
    name: str = Field(..., min_length=1, max_length=255, description="Назва товару")
    category_id: int = Field(..., gt=0)
    unit_of_measure: UnitOfMeasure
    width: Decimal = Field(..., gt=0, max_digits=8, decimal_places=2, description="Ширина, м")
    length: Decimal = Field(..., gt=0, max_digits=8, decimal_places=2, description="Довжина, м")
    height: Decimal = Field(..., gt=0, max_digits=8, decimal_places=2, description="Висота, м")
    weight: Decimal = Field(..., gt=0, max_digits=10, decimal_places=3, description="Вага, кг")
    min_stock_level: Decimal | None = Field(
        None, ge=0, max_digits=8, decimal_places=2, description="Мінімальний залишок"
    )

    @field_validator("sku_code", "name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = _clean_str(value)
        if not cleaned:
            raise ValueError("Поле не може бути порожнім")
        return cleaned

    @field_validator("sku_code")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        forbidden = set('"\'\\;')
        if any(char in forbidden for char in value):
            raise ValueError('Артикул не може містити лапки, ";" або "\\"')
        return value

    @field_validator("width", "length", "height", "weight", "min_stock_level", mode="before")
    @classmethod
    def parse_decimal(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().replace(",", ".").replace(" ", "")
        return value


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku_code: str | None = Field(None, min_length=1, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=255)
    category_id: int | None = Field(None, gt=0)
    unit_of_measure: UnitOfMeasure | None = None
    width: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    length: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    height: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    weight: Decimal | None = Field(None, gt=0, max_digits=10, decimal_places=3)
    min_stock_level: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)

    @field_validator("sku_code", "name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = _clean_str(value)
        if not cleaned:
            raise ValueError("Поле не може бути порожнім")
        return cleaned

    @field_validator("width", "length", "height", "weight", "min_stock_level", mode="before")
    @classmethod
    def parse_optional_decimal(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().replace(",", ".").replace(" ", "")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("Потрібно передати хоча б одне поле для оновлення")
        return self


class ProductRead(BaseModel):
    product_id: int
    sku_code: str
    name: str
    category_id: int
    category_name: str | None = None
    unit_of_measure: UnitOfMeasure
    width: Decimal
    length: Decimal
    height: Decimal
    weight: Decimal
    min_stock_level: Decimal | None = None


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int
    pages: int


# ── Імпорт ─────────────────────────────────────────────────────────────────

class ImportRowError(BaseModel):
    row: int = Field(..., description="Номер рядка у файлі (заголовок — 1)")
    sku_code: str | None = None
    field: str | None = None
    message: str


class ImportReport(BaseModel):
    filename: str
    total: int
    created: int
    updated: int
    failed: int
    categories_created: int = 0
    errors: list[ImportRowError] = Field(default_factory=list)


class ProductImportRow(BaseModel):
    """Один рядок файлу після нормалізації заголовків."""

    sku_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category: str | None = None
    unit_of_measure: UnitOfMeasure
    width: Decimal = Field(..., gt=0)
    length: Decimal = Field(..., gt=0)
    height: Decimal = Field(..., gt=0)
    weight: Decimal = Field(..., gt=0)
    min_stock_level: Decimal | None = Field(None, ge=0)

    @field_validator("sku_code", "name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = _clean_str(value)
        if not cleaned:
            raise ValueError("Поле не може бути порожнім")
        return cleaned

    @field_validator("width", "length", "height", "weight", "min_stock_level", mode="before")
    @classmethod
    def parse_decimal(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().replace(",", ".").replace(" ", "")
        return value

    @field_validator("unit_of_measure", mode="before")
    @classmethod
    def normalize_unit(cls, value):
        if isinstance(value, UnitOfMeasure):
            return value
        if value is None:
            raise ValueError("Одиниця виміру обовʼязкова")

        aliases = {
            "pcs": UnitOfMeasure.PCS, "pc": UnitOfMeasure.PCS, "шт": UnitOfMeasure.PCS,
            "шт.": UnitOfMeasure.PCS, "штук": UnitOfMeasure.PCS,
            "kg": UnitOfMeasure.KG, "кг": UnitOfMeasure.KG, "kilogram": UnitOfMeasure.KG,
            "pound": UnitOfMeasure.POUND, "lb": UnitOfMeasure.POUND, "фунт": UnitOfMeasure.POUND,
            "box": UnitOfMeasure.BOX, "кор": UnitOfMeasure.BOX, "коробка": UnitOfMeasure.BOX,
            "pallet": UnitOfMeasure.PALLET, "пал": UnitOfMeasure.PALLET, "палета": UnitOfMeasure.PALLET,
            "other": UnitOfMeasure.OTHER, "інше": UnitOfMeasure.OTHER,
        }
        normalized = _clean_str(str(value)).lower()
        if normalized in {unit.value for unit in UnitOfMeasure}:
            return UnitOfMeasure(normalized)
        if normalized in aliases:
            return aliases[normalized]
        raise ValueError(
            "Невідома одиниця виміру. Допустимо: pcs, kg, pound, box, pallet, other"
        )
