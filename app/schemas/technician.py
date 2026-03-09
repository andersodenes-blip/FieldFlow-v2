# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TechnicianCreate(BaseModel):
    region_id: uuid.UUID
    name: str
    email: str
    phone: str


class TechnicianUpdate(BaseModel):
    region_id: uuid.UUID | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class TechnicianResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    region_id: uuid.UUID
    name: str
    email: str
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
