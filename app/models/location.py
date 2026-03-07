# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class Location(TenantBase):
    __tablename__ = "locations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
