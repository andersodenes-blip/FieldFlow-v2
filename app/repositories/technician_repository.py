# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import select
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
        self, tenant_id: uuid.UUID, region_id: uuid.UUID | None = None
    ) -> list[Technician]:
        query = select(Technician).where(Technician.tenant_id == tenant_id)
        if region_id:
            query = query.where(Technician.region_id == region_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

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
