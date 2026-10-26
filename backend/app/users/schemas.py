from datetime import datetime
import re

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)
from app.core.enums import RoleName, UserStatus
from app.core.password_policy import validate_password_strength

# Allowed domains
PUBLIC_DOMAINS: set[str] = {
    "gmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "hotmail.com",
}

# Prohibited domains (e.g. spam)
BANNED_DOMAINS: set[str] | None = {
    "tempmail.com",
    "maximail.vip",
    "freeml.net",
}

# Проста, але строга перевірка формату email (для швидкого 422 без DNS)
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(value: str) -> str:
    """Приводить email до нижнього регістру й перевіряє базову структуру."""
    value = value.strip().lower()

    if not EMAIL_PATTERN.match(value):
        raise ValueError("Некоректна адреса електронної пошти")

    local_part, domain = value.rsplit("@", 1)
    if len(local_part) > 64:
        raise ValueError("Локальна частина email занадто довга")
    if len(value) > 255:
        raise ValueError("Email занадто довгий")

    if domain in BANNED_DOMAINS:
        raise ValueError("Ця пошта тимчасова або заблокована")

    if domain not in PUBLIC_DOMAINS:
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) < 2:
            raise ValueError("Некоректна зона корпоративного домену")

    return value


class RoleBase(BaseModel):
    name: RoleName


class RoleCreate(RoleBase):
    pass


class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100, description="Ім'я")
    last_name: str = Field(..., min_length=1, max_length=100, description="Прізвище")
    role_id: int = Field(..., gt=0, description="Ідентифікатор ролі")
    status: UserStatus | None = UserStatus.ACTIVE

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    role_id: int | None = Field(None, gt=0)
    status: UserStatus | None = None
    password: str | None = Field(None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else value

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: str | None) -> str | None:
        return validate_password_strength(value) if value is not None else value


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    role: RoleRead | None = None


# ── Контракт із веб-панеллю ────────────────────────────────────────────────

class UserListItem(BaseModel):
    """Користувач у форматі, який очікує фронтенд (frontend/API.md)."""

    user_id: int
    user_email: str
    first_name: str
    last_name: str
    role: RoleName
    status: UserStatus
    position: str | None = None
    on_shift: bool = False
    created_at: datetime


class UserCreatePayload(BaseModel):
    """Створення користувача з веб-панелі (роль задається назвою)."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    user_email: EmailStr = Field(
        ...,
        validation_alias=AliasChoices("user_email", "email"),
        serialization_alias="user_email",
    )
    password: str = Field(..., min_length=8, max_length=128)
    role: RoleName = RoleName.WORKER
    status: UserStatus = UserStatus.ACTIVE
    # Поки що не зберігається в моделі, але приймається для сумісності з UI
    warehouse_id: int | None = Field(None, gt=0)

    @field_validator("user_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserUpdatePayload(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    user_email: EmailStr | None = Field(
        None,
        validation_alias=AliasChoices("user_email", "email"),
        serialization_alias="user_email",
    )
    password: str | None = Field(None, min_length=8, max_length=128)
    role: RoleName | None = None
    status: UserStatus | None = None

    @field_validator("user_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        return validate_password_strength(value) if value is not None else value


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int
    pages: int


def serialize_user(user) -> UserListItem:
    """ORM User → елемент списку для фронтенду."""
    return UserListItem(
        user_id=user.id,
        user_email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name if user.role else RoleName.GUEST,
        status=user.status,
        position=None,
        on_shift=False,
        created_at=user.created_at,
    )
