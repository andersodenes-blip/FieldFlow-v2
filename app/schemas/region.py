# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegionCreate(BaseModel):
    name: str
    city: str


class RegionUpdate(BaseModel):
    name: str | None = None
    city: str | None = None


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    city: str
    created_at: datetime
    updated_at: datetime
