# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    org_number: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    org_number: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    org_number: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    created_at: datetime
    updated_at: datetime
    location_count: int = 0
