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


STATUS_LABELS = {
    "unscheduled": "Uplanlagt",
    "scheduled": "Planlagt",
    "in_progress": "Under arbeid",
    "completed": "Fullført",
    "cancelled": "Kansellert",
}

ACTION_LABELS = {
    "create": "Opprettet",
    "update": "Oppdatert",
    "delete": "Slettet",
}


def _format_audit_detail(action: str, metadata: dict | None) -> str:
    if not metadata:
        return ACTION_LABELS.get(action, action.capitalize())
    if "status" in metadata:
        label = STATUS_LABELS.get(metadata["status"], metadata["status"])
        return f"Status endret til {label}"
    parts = []
    for key, value in metadata.items():
        parts.append(f"{key}: {value}")
    return ", ".join(parts) if parts else ACTION_LABELS.get(action, action.capitalize())


@router.get("/{job_id}/detail")
async def get_job_detail(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return enriched job detail for modal."""
    from sqlalchemy import select, desc
    from app.models.scheduled_visit import ScheduledVisit
    from app.models.technician import Technician

    service = JobService(db)
    job = await service.get_job(job_id, current_user.tenant_id)
    loc = None
    stype = None
    if job.service_contract:
        stype = job.service_contract.service_type
        if job.service_contract.location:
            loc = job.service_contract.location

    # Find assigned technician via latest scheduled_visit
    technician_name = None
    result = await db.execute(
        select(Technician.name)
        .join(ScheduledVisit, ScheduledVisit.technician_id == Technician.id)
        .where(ScheduledVisit.job_id == job_id)
        .order_by(desc(ScheduledVisit.created_at))
        .limit(1)
    )
    tech_name = result.scalar_one_or_none()
    if tech_name:
        technician_name = tech_name

    return {
        "id": str(job.id),
        "title": job.title,
        "description": job.description,
        "status": job.status.value,
        "external_id": job.external_id,
        "address": loc.address if loc else None,
        "postal_code": loc.postal_code if loc else None,
        "service_type": stype,
        "technician_name": technician_name,
        "created_at": job.created_at.strftime("%d.%m.%Y %H:%M") if job.created_at else None,
    }


@router.get("/{job_id}/history")
async def get_job_history(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return audit events for a specific job."""
    from sqlalchemy import select, desc
    from app.models.audit_event import AuditEvent

    result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.tenant_id == current_user.tenant_id,
            AuditEvent.resource_type == "job",
            AuditEvent.resource_id == str(job_id),
        )
        .order_by(desc(AuditEvent.created_at))
        .limit(20)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "action": ACTION_LABELS.get(e.action, e.action.capitalize()),
            "detail": _format_audit_detail(e.action, e.metadata_),
            "created_at": e.created_at.strftime("%d.%m.%Y %H:%M") if e.created_at else "",
        }
        for e in events
    ]


@router.post("/{job_id}/complete", response_model=JobResponse)
async def complete_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(
        job_id, current_user.tenant_id, JobStatusUpdate(status="completed")
    )


@router.post("/{job_id}/schedule", response_model=JobResponse)
async def schedule_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(
        job_id, current_user.tenant_id, JobStatusUpdate(status="scheduled")
    )


@router.post("/{job_id}/start", response_model=JobResponse)
async def start_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(
        job_id, current_user.tenant_id, JobStatusUpdate(status="in_progress")
    )


@router.post("/{job_id}/unschedule", response_model=JobResponse)
async def unschedule_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(
        job_id, current_user.tenant_id, JobStatusUpdate(status="unscheduled")
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = JobService(db, user_id=current_user.id)
    return await service.update_status(
        job_id, current_user.tenant_id, JobStatusUpdate(status="cancelled")
    )
