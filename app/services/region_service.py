# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.region import Region
from app.repositories.region_repository import RegionRepository
from app.schemas.region import RegionCreate, RegionUpdate


class RegionService:
    def __init__(self, db: AsyncSession):
        self.repo = RegionRepository(db)

    async def create_region(self, tenant_id: uuid.UUID, data: RegionCreate) -> Region:
        region = Region(tenant_id=tenant_id, name=data.name, city=data.city)
        return await self.repo.create(region)

    async def list_regions(self, tenant_id: uuid.UUID) -> list[Region]:
        return await self.repo.get_all(tenant_id)

    async def get_region(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> Region:
        region = await self.repo.get_by_id(region_id, tenant_id)
        if not region:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
        return region

    async def update_region(self, region_id: uuid.UUID, tenant_id: uuid.UUID, data: RegionUpdate) -> Region:
        region = await self.get_region(region_id, tenant_id)
        if data.name is not None:
            region.name = data.name
        if data.city is not None:
            region.city = data.city
        return await self.repo.update(region)

    async def delete_region(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        region = await self.get_region(region_id, tenant_id)
        if await self.repo.has_technicians(region.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete region with assigned technicians",
            )
        await self.repo.delete(region)
