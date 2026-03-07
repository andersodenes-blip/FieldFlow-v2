# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class ServiceContract(TenantBase):
    __tablename__ = "service_contracts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("locations.id"), nullable=False)
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)
    interval_months: Mapped[int] = mapped_column(Integer, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
