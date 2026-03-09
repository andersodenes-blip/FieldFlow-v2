# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.location import Location


class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, customer: Customer) -> Customer:
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Customer], int]:
        query = select(Customer).where(Customer.tenant_id == tenant_id)
        count_query = select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)

        if search:
            query = query.where(Customer.name.ilike(f"%{search}%"))
            count_query = count_query.where(Customer.name.ilike(f"%{search}%"))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        order_col = getattr(Customer, sort_by, Customer.created_at)
        query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_org_number(self, org_number: str, tenant_id: uuid.UUID) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(
                Customer.org_number == org_number, Customer.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, customer_id: uuid.UUID, tenant_id: uuid.UUID) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update(self, customer: Customer) -> Customer:
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete(self, customer: Customer) -> None:
        await self.db.delete(customer)
        await self.db.commit()

    async def location_count(self, customer_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Location.id)).where(Location.customer_id == customer_id)
        )
        return result.scalar() or 0

    async def has_active_contracts(self, customer_id: uuid.UUID) -> bool:
        from app.models.service_contract import ServiceContract

        result = await self.db.execute(
            select(ServiceContract.id)
            .join(Location, ServiceContract.location_id == Location.id)
            .where(Location.customer_id == customer_id, ServiceContract.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
