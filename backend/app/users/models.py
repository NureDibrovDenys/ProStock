from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
    CheckConstraint
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.core.enums import RoleName, UserStatus
from app.core.db import Base

if TYPE_CHECKING:
    from app.warehouses.models import Warehouse


class Role(Base):
    __tablename__ = 'role'
    
    id: Mapped[int] = mapped_column(
        "role_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    name: Mapped[RoleName] = mapped_column(
        "role_name",
        Enum(
            RoleName,
            name="role_name",
            native_enum=False
        ),
        nullable=False,
        unique=True
    )
    
    users: Mapped[list["User"]] = relationship(back_populates="role")
    
    def __repr__(self) -> str:
        return f"Role(id={self.id!r}, name={self.name!r})"

class User(Base):
    __tablename__ = 'user'
    
    id: Mapped[int] = mapped_column(
        "user_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    email: Mapped[str] = mapped_column(
        "user_email",
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "role.role_id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=False
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    role: Mapped["Role"] = relationship(back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    warehouse: Mapped["Warehouse | None"] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
        lazy="select",
    )
    
    __table_args__ = (
        CheckConstraint(
            "role_id > 0",
            name="check_role_id_positive"
        ),
    )
    
    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"


class RefreshToken(Base):
    """Refresh-токен сесії.

    Зберігається лише SHA-256 хеш самого токена: навіть при витоку БД сирі
    токени відновити неможливо. Кожен refresh ротується — старий запис
    позначається відкликаним (`revoked_at`).
    """

    __tablename__ = 'refresh_token'

    id: Mapped[int] = mapped_column(
        "refresh_token_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        "user_id",
        BigInteger,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash: Mapped[str] = mapped_column(
        "token_hash",
        String(64),
        unique=True,
        nullable=False,
        index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        "issued_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        "expires_at",
        DateTime(timezone=True),
        nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        "revoked_at",
        DateTime(timezone=True),
        nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        "user_agent",
        String(255),
        nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        "ip_address",
        String(45),
        nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"RefreshToken(id={self.id!r}, user_id={self.user_id!r})"