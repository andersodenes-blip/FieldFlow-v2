# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.repositories.customer_repository import CustomerRepository
from app.repositories.location_repository import LocationRepository
from app.schemas.location import LocationCreate, LocationUpdate
from app.services.audit_service import AuditService


class LocationService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.repo = LocationRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def create_location(
        self, customer_id: uuid.UUID, tenant_id: uuid.UUID, data: LocationCreate
    ) -> Location:
        # Validate customer belongs to tenant
        customer = await self.customer_repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )
        location = Location(
            tenant_id=tenant_id,
            customer_id=customer_id,
            address=data.address,
            city=data.city,
            postal_code=data.postal_code,
            latitude=data.latitude,
            longitude=data.longitude,
        )
        location = await self.repo.create(location)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "create", "location", str(location.id), data.model_dump())
        return location

    async def list_locations(
        self,
        customer_id: uuid.UUID,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Location], int]:
        # Validate customer belongs to tenant
        customer = await self.customer_repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
            )
        return await self.repo.get_by_customer(
            customer_id, tenant_id, page=page, page_size=page_size,
            sort_by=sort_by, sort_order=sort_order,
        )

    async def get_location(self, location_id: uuid.UUID, tenant_id: uuid.UUID) -> Location:
        location = await self.repo.get_by_id(location_id, tenant_id)
        if not location:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
        return location

    async def update_location(
        self, location_id: uuid.UUID, tenant_id: uuid.UUID, data: LocationUpdate
    ) -> Location:
        location = await self.get_location(location_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(location, field, value)
        location = await self.repo.update(location)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "location", str(location.id), data.model_dump(exclude_unset=True))
        return location

    async def delete_location(self, location_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        location = await self.get_location(location_id, tenant_id)
        if await self.repo.has_active_contracts(location.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete location with active contracts",
            )
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "delete", "location", str(location.id))
        await self.repo.delete(location)
