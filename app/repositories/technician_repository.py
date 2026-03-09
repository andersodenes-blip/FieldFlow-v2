# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.technician import Technician


class TechnicianRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, technician: Technician) -> Technician:
        self.db.add(technician)
        await self.db.commit()
        await self.db.refresh(technician)
        return technician

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Technician], int]:
        query = select(Technician).where(Technician.tenant_id == tenant_id)
        count_query = select(func.count(Technician.id)).where(Technician.tenant_id == tenant_id)

        if region_id:
            query = query.where(Technician.region_id == region_id)
            count_query = count_query.where(Technician.region_id == region_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        order_col = getattr(Technician, sort_by, Technician.created_at)
        query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, technician_id: uuid.UUID, tenant_id: uuid.UUID) -> Technician | None:
        result = await self.db.execute(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update(self, technician: Technician) -> Technician:
        await self.db.commit()
        await self.db.refresh(technician)
        return technician

    async def soft_delete(self, technician: Technician) -> Technician:
        technician.is_active = False
        await self.db.commit()
        await self.db.refresh(technician)
        return technician
