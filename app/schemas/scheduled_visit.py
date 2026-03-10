# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date, time

from pydantic import BaseModel, ConfigDict


class ScheduledVisitCreate(BaseModel):
    job_id: uuid.UUID
    technician_id: uuid.UUID
    scheduled_date: date
    scheduled_start: time | None = None
    scheduled_end: time | None = None
    notes: str | None = None


class ScheduledVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    technician_id: uuid.UUID
    scheduled_date: date
    scheduled_start: time | None = None
    scheduled_end: time | None = None
    status: str
    notes: str | None = None
