# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_contract import ServiceContract
from app.repositories.location_repository import LocationRepository
from app.repositories.service_contract_repository import ServiceContractRepository
from app.schemas.service_contract import ServiceContractCreate, ServiceContractUpdate


class ServiceContractService:
    def __init__(self, db: AsyncSession):
        self.repo = ServiceContractRepository(db)
        self.location_repo = LocationRepository(db)

    async def create_contract(
        self, tenant_id: uuid.UUID, data: ServiceContractCreate
    ) -> ServiceContract:
        # Validate location belongs to tenant
        location = await self.location_repo.get_by_id(data.location_id, tenant_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )
        contract = ServiceContract(
            tenant_id=tenant_id,
            location_id=data.location_id,
            service_type=data.service_type,
            interval_months=data.interval_months,
            next_due_date=data.next_due_date,
            sla_hours=data.sla_hours,
        )
        return await self.repo.create(contract)

    async def list_contracts(
        self,
        tenant_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> list[ServiceContract]:
        return await self.repo.get_all(
            tenant_id, location_id=location_id, customer_id=customer_id, is_active=is_active
        )

    async def get_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ServiceContract:
        contract = await self.repo.get_by_id(contract_id, tenant_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service contract not found",
            )
        return contract

    async def update_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID, data: ServiceContractUpdate
    ) -> ServiceContract:
        contract = await self.get_contract(contract_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(contract, field, value)
        return await self.repo.update(contract)

    async def delete_contract(
        self, contract_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        contract = await self.get_contract(contract_id, tenant_id)
        await self.repo.soft_delete(contract)
