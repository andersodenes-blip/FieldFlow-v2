# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ImportJob(TenantBase):
    __tablename__ = "import_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), default=ImportStatus.pending)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)
