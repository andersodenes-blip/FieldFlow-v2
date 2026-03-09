# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location


class LocationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, location: Location) -> Location:
        self.db.add(location)
        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def get_by_customer(
        self,
        customer_id: uuid.UUID,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Location], int]:
        base = [Location.customer_id == customer_id, Location.tenant_id == tenant_id]
        count_query = select(func.count(Location.id)).where(*base)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = select(Location).where(*base)
        order_col = getattr(Location, sort_by, Location.created_at)
        query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, location_id: uuid.UUID, tenant_id: uuid.UUID) -> Location | None:
        result = await self.db.execute(
            select(Location).where(
                Location.id == location_id, Location.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update(self, location: Location) -> Location:
        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def delete(self, location: Location) -> None:
        await self.db.delete(location)
        await self.db.commit()

    async def has_active_contracts(self, location_id: uuid.UUID) -> bool:
        from app.models.service_contract import ServiceContract

        result = await self.db.execute(
            select(ServiceContract.id)
            .where(ServiceContract.location_id == location_id, ServiceContract.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
