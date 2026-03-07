# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantBase


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    planner = "planner"
    dispatcher = "dispatcher"
    viewer = "viewer"


class User(TenantBase):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="users")
