# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.region import Region


class RegionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, region: Region) -> Region:
        self.db.add(region)
        await self.db.commit()
        await self.db.refresh(region)
        return region

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Region], int]:
        query = select(Region).where(Region.tenant_id == tenant_id)
        count_query = select(func.count(Region.id)).where(Region.tenant_id == tenant_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        order_col = getattr(Region, sort_by, Region.created_at)
        query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> Region | None:
        result = await self.db.execute(
            select(Region).where(Region.id == region_id, Region.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update(self, region: Region) -> Region:
        await self.db.commit()
        await self.db.refresh(region)
        return region

    async def delete(self, region: Region) -> None:
        await self.db.delete(region)
        await self.db.commit()

    async def has_technicians(self, region_id: uuid.UUID) -> bool:
        from app.models.technician import Technician

        result = await self.db.execute(
            select(Technician.id).where(Technician.region_id == region_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
