# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    service_contract_id: uuid.UUID
    title: str
    description: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class JobStatusUpdate(BaseModel):
    status: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    service_contract_id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class JobGenerateRequest(BaseModel):
    horizon_days: int = 30


class JobGenerateResponse(BaseModel):
    generated_count: int
    job_ids: list[uuid.UUID]
