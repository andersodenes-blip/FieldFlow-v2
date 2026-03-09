# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, job: Job) -> Job:
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> list[Job]:
        query = select(Job).where(Job.tenant_id == tenant_id)

        if status:
            query = query.where(Job.status == JobStatus(status))
        if customer_id:
            from app.models.service_contract import ServiceContract
            from app.models.location import Location

            query = (
                query.join(ServiceContract, Job.service_contract_id == ServiceContract.id)
                .join(Location, ServiceContract.location_id == Location.id)
                .where(Location.customer_id == customer_id)
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> Job | None:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update(self, job: Job) -> Job:
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def has_pending_job_for_contract(self, contract_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Job.id)
            .where(
                Job.service_contract_id == contract_id,
                Job.tenant_id == tenant_id,
                Job.status.in_([JobStatus.unscheduled, JobStatus.scheduled]),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
