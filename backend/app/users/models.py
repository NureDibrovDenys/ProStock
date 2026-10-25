from datetime import datetime
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    role: Mapped["Role"] = relationship(back_populates="users")
    
    __table_args__ = (
        CheckConstraint(
            "role_id > 0",
            name="check_role_id_positive"
        ),
    )
    
    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"