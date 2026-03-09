# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.repositories.audit_event_repository import AuditEventRepository


class AuditService:
    def __init__(self, db: AsyncSession):
        self.repo = AuditEventRepository(db)

    async def log(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            metadata_=metadata or {},
        )
        return await self.repo.create(event)

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        resource_type: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from=None,
        date_to=None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[AuditEvent], int]:
        return await self.repo.get_all(
            tenant_id,
            resource_type=resource_type,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
