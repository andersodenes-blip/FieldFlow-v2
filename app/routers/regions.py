# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
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
    service = RegionService(db, user_id=current_user.id)
    region = await service.create_region(current_user.tenant_id, data)
    return region


@router.get("", response_model=PaginatedResponse[RegionResponse])
async def list_regions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    service = RegionService(db, user_id=current_user.id)
    items, total = await service.list_regions(
        current_user.tenant_id, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{region_id}", response_model=RegionResponse)
async def get_region(
    region_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RegionService(db, user_id=current_user.id)
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
    service = RegionService(db, user_id=current_user.id)
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
    service = RegionService(db, user_id=current_user.id)
    await service.delete_region(region_id, current_user.tenant_id)
