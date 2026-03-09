# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.technician import Technician
from app.repositories.region_repository import RegionRepository
from app.repositories.technician_repository import TechnicianRepository
from app.schemas.technician import TechnicianCreate, TechnicianUpdate


class TechnicianService:
    def __init__(self, db: AsyncSession):
        self.repo = TechnicianRepository(db)
        self.region_repo = RegionRepository(db)

    async def create_technician(self, tenant_id: uuid.UUID, data: TechnicianCreate) -> Technician:
        # Validate region belongs to same tenant
        region = await self.region_repo.get_by_id(data.region_id, tenant_id)
        if not region:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Region not found or does not belong to your tenant",
            )
        technician = Technician(
            tenant_id=tenant_id,
            region_id=data.region_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
        )
        return await self.repo.create(technician)

    async def list_technicians(
        self, tenant_id: uuid.UUID, region_id: uuid.UUID | None = None
    ) -> list[Technician]:
        return await self.repo.get_all(tenant_id, region_id=region_id)

    async def get_technician(self, technician_id: uuid.UUID, tenant_id: uuid.UUID) -> Technician:
        technician = await self.repo.get_by_id(technician_id, tenant_id)
        if not technician:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
        return technician

    async def update_technician(
        self, technician_id: uuid.UUID, tenant_id: uuid.UUID, data: TechnicianUpdate
    ) -> Technician:
        technician = await self.get_technician(technician_id, tenant_id)
        update_data = data.model_dump(exclude_unset=True)
        if "region_id" in update_data:
            region = await self.region_repo.get_by_id(update_data["region_id"], tenant_id)
            if not region:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Region not found or does not belong to your tenant",
                )
        for field, value in update_data.items():
            setattr(technician, field, value)
        return await self.repo.update(technician)

    async def delete_technician(self, technician_id: uuid.UUID, tenant_id: uuid.UUID) -> Technician:
        technician = await self.get_technician(technician_id, tenant_id)
        return await self.repo.soft_delete(technician)
