from datetime import datetime
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator
)
import re
from app.core.enums import RoleName, UserStatus

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


class RoleBase(BaseModel):
    name: RoleName

class RoleCreate(RoleBase):
    pass

class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    
def validate_and_normalize_email(value: str) -> str:
    """
    Convert email to lowercase.
    Check for the presence of '@' (at) character.
    Check for basic email structure: name@domain
    Domain check (PUBLIC and BANNED domains).
    Check for business email struct.
    """
    value = value.lower().strip()
    
    if "@" not in value:
        raise ValueError(
            "The email must contain the '@' symbol"
        )
    
    email_parts = value.split("@")
    if len(email_parts) != 2:
        raise ValueError(
            "Invalid email format (too many or too few '@' symbols)"
        )
    
    local_part, domain = email_parts
    
    if not local_part:
        raise ValueError(
            "The email name cannot be empty"
        )
    if not domain or "." not in domain:
        raise ValueError(
            "The email domain must be valid and contain a dot. For example, domain.com"
        )
    
    if domain in BANNED_DOMAINS:
        raise ValueError(
            "This email is temporary or banned"
        )
    
    if domain not in PUBLIC_DOMAINS:
        tld = domain.split(".")[-1]
        if len(tld) < 2:
            raise ValueError(
                "The zone of the corporate domain is incorrect"
            )
    
    return value

class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User name"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User lastname",
    )
    role_id: int = Field(
        ...,
        gt=0,
        description="Role ID must be positive number",
    )
    status: UserStatus | None = UserStatus.ACTIVE
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validate_and_normalize_email(value)

class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password between 8 and 128 characters long",
    )
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Check password complexity"""
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )
        if not re.search(r"[0-9]", value):
            raise ValueError(
                "Password must contain at least one digit"
            )
        return value

class UserUpdate(BaseModel):
    email: EmailStr | None = None
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
    status: UserStatus | None = UserStatus.ACTIVE
    password: str | None = Field(
        None,
        min_length=8,
        max_length=128
    )
    
    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str) -> str | None:
        if value is not None:
            return validate_and_normalize_email(value)
        return value

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    role: RoleRead | None = None