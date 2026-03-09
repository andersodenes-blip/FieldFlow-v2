# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob


class ImportJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, import_job: ImportJob) -> ImportJob:
        self.db.add(import_job)
        await self.db.commit()
        await self.db.refresh(import_job)
        return import_job

    async def get_by_id(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> ImportJob | None:
        result = await self.db.execute(
            select(ImportJob).where(
                ImportJob.id == job_id, ImportJob.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update(self, import_job: ImportJob) -> ImportJob:
        await self.db.commit()
        await self.db.refresh(import_job)
        return import_job
