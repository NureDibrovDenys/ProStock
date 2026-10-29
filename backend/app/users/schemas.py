from datetime import datetime
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.core.enums import RoleName, UserStatus
from app.core.password_policy import (
    MIN_PASSWORD_LENGTH,
    validate_password_strength
)
from app.core.validators import (
    normalize_and_validate_email,
    trim_names
)

class RoleBase(BaseModel):
    name: RoleName

class RoleCreate(RoleBase):
    pass

class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class UserBase(BaseModel):
    email: EmailStr = Field(
        ...,
        examples=["user@example.com"]
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User first name"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User last name"
    )
    role_id: int = Field(
        ...,
        gt=0,
        description="Role identifier"
    )
    status: UserStatus | None = UserStatus.ACTIVE
    
    @field_validator(
        "first_name",
        "last_name",
        mode="before"
    )
    @classmethod
    def trim_first_and_last_names(cls, value: Any) -> Any:
        return trim_names(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_and_validate_email(value)

class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

class UserUpdate(BaseModel):
    email: EmailStr | None = Field(
        None,
        examples=["user@example.com"]
    )
    first_name: str | None = Field(
        None,
        min_length=1,
        max_length=100
    )
    last_name: str | None = Field(
        None,
        min_length=1,
        max_length=100
    )
    role_id: int | None = Field(
        None,
        gt=0
    )
    status: UserStatus | None = None
    password: str | None = Field(
        None,
        min_length=MIN_PASSWORD_LENGTH
    )
    
    @field_validator(
        "first_name",
        "last_name",
        mode="before"
    )
    @classmethod
    def trim_first_and_last_names(cls, value: Any) -> Any:
        return trim_names(value)

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_and_validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_password_strength(value)

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    role: RoleRead | None = None


class UserListItem(BaseModel):
    """
    The user in the format expected by the frontend (frontend/API.md).
    """
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
    """
    Creating a user from the web panel (role is specified by name).
    """
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100
    )
    user_email: EmailStr = Field(
        ...,
        validation_alias=AliasChoices(
            "user_email",
            "email"
        ),
        serialization_alias="user_email",
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH
    )
    role: RoleName = RoleName.WORKER
    status: UserStatus = UserStatus.ACTIVE
    warehouse_id: int | None = Field(
        None,
        gt=0
    )
    
    @field_validator(
        "first_name",
        "last_name",
        mode="before"
    )
    @classmethod
    def trim_first_and_last_names(cls, value: Any) -> Any:
        return trim_names(value)

    @field_validator("user_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_and_validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

class UserUpdatePayload(BaseModel):
    first_name: str | None = Field(
        None,
        min_length=1,
        max_length=100
    )
    last_name: str | None = Field(
        None,
        min_length=1,
        max_length=100
    )
    user_email: EmailStr | None = Field(
        None,
        validation_alias=AliasChoices(
            "user_email",
            "email"
        ),
        serialization_alias="user_email",
    )
    password: str | None = Field(
        None,
        min_length=MIN_PASSWORD_LENGTH
    )
    role: RoleName | None = None
    status: UserStatus | None = None
    
    @field_validator(
        "first_name",
        "last_name",
        mode="before"
    )
    @classmethod
    def trim_first_and_last_names(cls, value: Any) -> Any:
        return trim_names(value)

    @field_validator("user_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_and_validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_password_strength(value)

class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int
    pages: int
