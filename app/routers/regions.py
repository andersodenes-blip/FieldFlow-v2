# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.region import RegionCreate, RegionResponse, RegionUpdate
from app.services.region_service import RegionService

router = APIRouter(prefix="/regions", tags=["regions"])


@router.post(
    "",
    response_model=RegionResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_region(
    data: RegionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db)
    region = await service.create_region(current_user.tenant_id, data)
    return region


@router.get("", response_model=list[RegionResponse])
async def list_regions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db)
    return await service.list_regions(current_user.tenant_id)


@router.get("/{region_id}", response_model=RegionResponse)
async def get_region(
    region_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db)
    return await service.get_region(region_id, current_user.tenant_id)


@router.put(
    "/{region_id}",
    response_model=RegionResponse,
    dependencies=[require_role("org:admin")],
)
async def update_region(
    region_id: uuid.UUID,
    data: RegionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db)
    return await service.update_region(region_id, current_user.tenant_id, data)


@router.delete(
    "/{region_id}",
    status_code=204,
    dependencies=[require_role("org:admin")],
)
async def delete_region(
    region_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db)
    await service.delete_region(region_id, current_user.tenant_id)
