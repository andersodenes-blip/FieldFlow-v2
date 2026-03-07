# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class Customer(TenantBase):
    __tablename__ = "customers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_number: Mapped[str] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
