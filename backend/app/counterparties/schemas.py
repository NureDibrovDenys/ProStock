import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import SupplierStatus, RecipientStatus
from app.core.validators import normalize_and_validate_email


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def check_tax_id(value: str | None) -> str | None:
    value = clean_text(value)
    if value is None:
        return None
    if not re.fullmatch(r"\d{8}|\d{10}", value):
        raise ValueError("ЄДРПОУ має містити 8 цифр, ІПН — 10 цифр")
    return value


def check_phone(value: str | None) -> str | None:
    value = clean_text(value)
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"\+?[\d\s\-()]+", value) or not 7 <= len(digits) <= 15:
        raise ValueError("Некоректний номер телефону")
    return value


def check_email(value: str | None) -> str | None:
    value = clean_text(value)
    if value is None:
        return None
    return normalize_and_validate_email(value)


# Постачальники ──────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):

    company_name: str = Field(..., max_length=255)
    tax_id: str | None = Field(None, max_length=20)
    contact_person: str | None = Field(None, max_length=150)
    phone_number: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=1000)
    status: SupplierStatus = SupplierStatus.ACTIVE

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str | None) -> str:
        value = clean_text(value)
        if value is None:
            raise ValueError("Назва компанії обов'язкова")
        return value

    @field_validator("contact_person", "address")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, value: str | None) -> str | None:
        return check_tax_id(value)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return check_phone(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return check_email(value)


class SupplierUpdate(SupplierCreate):

    company_name: str | None = Field(None, max_length=255)
    status: SupplierStatus | None = None

    @model_validator(mode="after")
    def check_not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Потрібно передати хоча б одне поле")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Статус не можна очистити")
        return self


class SupplierRead(BaseModel):

    supplier_id: int
    company_name: str
    tax_id: str | None
    contact_person: str | None
    phone_number: str | None
    email: str | None
    address: str | None
    status: SupplierStatus
    created_at: datetime


class SupplierListResponse(BaseModel):

    items: list[SupplierRead]
    total: int
    page: int
    page_size: int
    pages: int



# Одержувачі ──────────────────────────────────────────────────────────

class RecipientCreate(BaseModel):

    company_name: str = Field(..., max_length=255)
    tax_id: str | None = Field(None, max_length=20)
    contact_person: str | None = Field(None, max_length=150)
    phone_number: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=100)
    address: str = Field(..., max_length=1000)
    status: RecipientStatus = RecipientStatus.ACTIVE

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str | None) -> str:
        value = clean_text(value)
        if value is None:
            raise ValueError("Назва одержувача обов'язкова")
        return value

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str:
        value = clean_text(value)
        if value is None:
            raise ValueError("Адреса доставки обов'язкова")
        return value

    @field_validator("contact_person")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, value: str | None) -> str | None:
        return check_tax_id(value)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return check_phone(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return check_email(value)


class RecipientUpdate(RecipientCreate):

    company_name: str | None = Field(None, max_length=255)
    address: str | None = Field(None, max_length=1000)
    status: RecipientStatus | None = None

    @model_validator(mode="after")
    def check_not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Потрібно передати хоча б одне поле")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Статус не можна очистити")
        return self


class RecipientRead(BaseModel):

    recipient_id: int
    company_name: str
    tax_id: str | None
    contact_person: str | None
    phone_number: str | None
    email: str | None
    address: str
    status: RecipientStatus
    created_at: datetime


class RecipientListResponse(BaseModel):
    items: list[RecipientRead]
    total: int
    page: int
    page_size: int
    pages: int