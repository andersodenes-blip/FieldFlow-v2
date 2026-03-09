# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str
    metadata: dict = Field(alias="metadata_")
    created_at: datetime
