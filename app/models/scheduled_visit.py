# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import enum
import uuid
from datetime import date, time

from sqlalchemy import Date, Enum, ForeignKey, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class VisitStatus(str, enum.Enum):
    planned = "planned"
    confirmed = "confirmed"
    completed = "completed"
    missed = "missed"


class ScheduledVisit(TenantBase):
    __tablename__ = "scheduled_visits"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id"), nullable=False)
    technician_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("technicians.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus), default=VisitStatus.planned)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
