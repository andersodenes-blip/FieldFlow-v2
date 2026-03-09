# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_contract import ServiceContract


class ServiceContractRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, contract: ServiceContract) -> ServiceContract:
        self.db.add(contract)
        await self.db.commit()
        await self.db.refresh(contract)
        return contract

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> list[ServiceContract]:
        query = select(ServiceContract).where(ServiceContract.tenant_id == tenant_id)

        if location_id:
            query = query.where(ServiceContract.location_id == location_id)
        if customer_id:
            from app.models.location import Location

            query = query.join(Location, ServiceContract.location_id == Location.id).where(
                Location.customer_id == customer_id
            )
        if is_active is not None:
            query = query.where(ServiceContract.is_active == is_active)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, contract_id: uuid.UUID, tenant_id: uuid.UUID) -> ServiceContract | None:
        result = await self.db.execute(
            select(ServiceContract).where(
                ServiceContract.id == contract_id, ServiceContract.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update(self, contract: ServiceContract) -> ServiceContract:
        await self.db.commit()
        await self.db.refresh(contract)
        return contract

    async def soft_delete(self, contract: ServiceContract) -> ServiceContract:
        contract.is_active = False
        await self.db.commit()
        await self.db.refresh(contract)
        return contract

    async def get_due_contracts(self, tenant_id: uuid.UUID, horizon_date: date) -> list[ServiceContract]:
        result = await self.db.execute(
            select(ServiceContract).where(
                ServiceContract.tenant_id == tenant_id,
                ServiceContract.is_active.is_(True),
                ServiceContract.next_due_date <= horizon_date,
            )
        )
        return list(result.scalars().all())
