# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.repositories.job_repository import JobRepository
from app.repositories.service_contract_repository import ServiceContractRepository
from app.schemas.job import JobCreate, JobUpdate, JobStatusUpdate
from app.services.audit_service import AuditService


# Valid status transitions
VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.unscheduled: {JobStatus.scheduled, JobStatus.cancelled},
    JobStatus.scheduled: {JobStatus.in_progress, JobStatus.unscheduled, JobStatus.cancelled},
    JobStatus.in_progress: {JobStatus.completed, JobStatus.unscheduled, JobStatus.cancelled},
    JobStatus.completed: set(),
    JobStatus.cancelled: set(),
}


class JobService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.repo = JobRepository(db)
        self.contract_repo = ServiceContractRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def create_job(self, tenant_id: uuid.UUID, data: JobCreate) -> Job:
        # Validate contract belongs to tenant
        contract = await self.contract_repo.get_by_id(data.service_contract_id, tenant_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service contract not found",
            )
        job = Job(
            tenant_id=tenant_id,
            service_contract_id=data.service_contract_id,
            title=data.title,
            description=data.description,
            status=JobStatus.unscheduled,
        )
        job = await self.repo.create(job)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "create", "job", str(job.id), data.model_dump(mode="json"))
        return job

    async def list_jobs(
        self,
        tenant_id: uuid.UUID,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
        region_id: uuid.UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> tuple[list[Job], int]:
        return await self.repo.get_all(
            tenant_id, status=status, customer_id=customer_id,
            region_id=region_id, search=search,
            page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
        )

    async def get_job(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> Job:
        job = await self.repo.get_by_id(job_id, tenant_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        return job

    async def update_job(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID, data: JobUpdate
    ) -> Job:
        job = await self.get_job(job_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(job, field, value)
        job = await self.repo.update(job)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "job", str(job.id), data.model_dump(exclude_unset=True))
        return job

    async def update_status(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID, data: JobStatusUpdate
    ) -> Job:
        job = await self.get_job(job_id, tenant_id)
        try:
            new_status = JobStatus(data.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {data.status}",
            )

        current_status = job.status
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot transition from {current_status.value} to {new_status.value}",
            )

        job.status = new_status
        job = await self.repo.update(job)
        if self.user_id:
            await self.audit.log(tenant_id, self.user_id, "update", "job", str(job.id), {"status": new_status.value})
        return job
