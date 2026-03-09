# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    status: str
    row_count: int | None = None
    error_log: dict | None = None
    created_at: datetime
    updated_at: datetime
