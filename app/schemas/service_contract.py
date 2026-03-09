# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ServiceContractCreate(BaseModel):
    location_id: uuid.UUID
    service_type: str
    interval_months: int
    next_due_date: date
    sla_hours: int | None = None


class ServiceContractUpdate(BaseModel):
    service_type: str | None = None
    interval_months: int | None = None
    next_due_date: date | None = None
    sla_hours: int | None = None
    is_active: bool | None = None


class ServiceContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    location_id: uuid.UUID
    service_type: str
    interval_months: int
    next_due_date: date
    sla_hours: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
