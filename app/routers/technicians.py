# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.technician import TechnicianCreate, TechnicianResponse, TechnicianUpdate
from app.services.technician_service import TechnicianService

router = APIRouter(prefix="/technicians", tags=["technicians"])


@router.post(
    "",
    response_model=TechnicianResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_technician(
    data: TechnicianCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = TechnicianService(db)
    return await service.create_technician(current_user.tenant_id, data)


@router.get("", response_model=list[TechnicianResponse])
async def list_technicians(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    region_id: uuid.UUID | None = Query(None),
):
    service = TechnicianService(db)
    return await service.list_technicians(current_user.tenant_id, region_id=region_id)


@router.get("/{technician_id}", response_model=TechnicianResponse)
async def get_technician(
    technician_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = TechnicianService(db)
    return await service.get_technician(technician_id, current_user.tenant_id)


@router.put(
    "/{technician_id}",
    response_model=TechnicianResponse,
    dependencies=[require_role("org:admin")],
)
async def update_technician(
    technician_id: uuid.UUID,
    data: TechnicianUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = TechnicianService(db)
    return await service.update_technician(technician_id, current_user.tenant_id, data)


@router.delete(
    "/{technician_id}",
    response_model=TechnicianResponse,
    dependencies=[require_role("org:admin")],
)
async def delete_technician(
    technician_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = TechnicianService(db)
    return await service.delete_technician(technician_id, current_user.tenant_id)
