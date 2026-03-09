# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantBase


class JobStatus(str, enum.Enum):
    unscheduled = "unscheduled"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Job(TenantBase):
    __tablename__ = "jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    service_contract_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("service_contracts.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.unscheduled)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    service_contract = relationship("ServiceContract", lazy="noload")
