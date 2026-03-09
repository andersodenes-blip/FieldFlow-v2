# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event: AuditEvent) -> AuditEvent:
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        resource_type: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[AuditEvent], int]:
        query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        count_query = select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == tenant_id)

        if resource_type:
            query = query.where(AuditEvent.resource_type == resource_type)
            count_query = count_query.where(AuditEvent.resource_type == resource_type)
        if user_id:
            query = query.where(AuditEvent.user_id == user_id)
            count_query = count_query.where(AuditEvent.user_id == user_id)
        if date_from:
            query = query.where(func.date(AuditEvent.created_at) >= date_from)
            count_query = count_query.where(func.date(AuditEvent.created_at) >= date_from)
        if date_to:
            query = query.where(func.date(AuditEvent.created_at) <= date_to)
            count_query = count_query.where(func.date(AuditEvent.created_at) <= date_to)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        order_col = getattr(AuditEvent, sort_by, AuditEvent.created_at)
        query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
