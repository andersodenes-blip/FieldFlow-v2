# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobGenerateRequest,
    JobGenerateResponse,
    JobResponse,
    JobStatusUpdate,
    JobUpdate,
)
from app.schemas.pagination import PaginatedResponse
from app.services.job_generation_service import JobGenerationService
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/generate",
    response_model=JobGenerateResponse,
    dependencies=[require_role("org:admin")],
)
async def generate_jobs(
    data: JobGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobGenerationService(db)
    count, job_ids = await service.generate_jobs(
        current_user.tenant_id, horizon_days=data.horizon_days
    )
    return JobGenerateResponse(generated_count=count, job_ids=job_ids)


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_job(
    data: JobCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.create_job(current_user.tenant_id, data)


@router.get("", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    service = JobService(db, user_id=current_user.id)
    items, total = await service.list_jobs(
        current_user.tenant_id, status=status, customer_id=customer_id,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.get_job(job_id, current_user.tenant_id)


@router.put(
    "/{job_id}",
    response_model=JobResponse,
    dependencies=[require_role("org:admin")],
)
async def update_job(
    job_id: uuid.UUID,
    data: JobUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_job(job_id, current_user.tenant_id, data)


@router.patch(
    "/{job_id}/status",
    response_model=JobResponse,
    dependencies=[require_role("org:admin")],
)
async def update_job_status(
    job_id: uuid.UUID,
    data: JobStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(job_id, current_user.tenant_id, data)
