# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.pagination import PaginatedResponse
from app.services.location_service import LocationService

router = APIRouter(tags=["locations"])


@router.post(
    "/customers/{customer_id}/locations",
    response_model=LocationResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_location(
    customer_id: uuid.UUID,
    data: LocationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = LocationService(db, user_id=current_user.id)
    return await service.create_location(customer_id, current_user.tenant_id, data)


@router.get(
    "/customers/{customer_id}/locations",
    response_model=PaginatedResponse[LocationResponse],
)
async def list_locations(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    service = LocationService(db, user_id=current_user.id)
    items, total = await service.list_locations(
        customer_id, current_user.tenant_id, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = LocationService(db, user_id=current_user.id)
    return await service.get_location(location_id, current_user.tenant_id)


@router.put(
    "/locations/{location_id}",
    response_model=LocationResponse,
    dependencies=[require_role("org:admin")],
)
async def update_location(
    location_id: uuid.UUID,
    data: LocationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = LocationService(db, user_id=current_user.id)
    return await service.update_location(location_id, current_user.tenant_id, data)


@router.delete(
    "/locations/{location_id}",
    status_code=204,
    dependencies=[require_role("org:admin")],
)
async def delete_location(
    location_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = LocationService(db, user_id=current_user.id)
    await service.delete_location(location_id, current_user.tenant_id)
