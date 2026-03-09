# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LocationCreate(BaseModel):
    address: str
    city: str
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None


class LocationUpdate(BaseModel):
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    address: str
    city: str
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime
