# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.region import Region
from app.repositories.region_repository import RegionRepository
from app.schemas.region import RegionCreate, RegionUpdate
from app.services.audit_service import AuditService


class RegionService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.repo = RegionRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def create_region(self, tenant_id: uuid.UUID, data: RegionCreate) -> Region:
        region = Region(tenant_id=tenant_id, name=data.name, city=data.city)
        region = await self.repo.create(region)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "create", "region", str(region.id), data.model_dump())
        return region

    async def list_regions(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Region], int]:
        return await self.repo.get_all(
            tenant_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
        )

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
        region = await self.repo.update(region)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "region", str(region.id), data.model_dump(exclude_unset=True))
        return region

    async def delete_region(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        region = await self.get_region(region_id, tenant_id)
        if await self.repo.has_technicians(region.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete region with assigned technicians",
            )
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "delete", "region", str(region.id))
        await self.repo.delete(region)
