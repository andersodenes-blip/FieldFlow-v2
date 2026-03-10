# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.route import (
    RouteListResponse,
    RoutePlanRequest,
    RoutePlanResponse,
    RouteResponse,
    RouteStatusUpdate,
)
from app.services.route_planning_service import RoutePlanningService
from app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post(
    "/plan",
    response_model=RoutePlanResponse,
    dependencies=[require_role("org:admin")],
)
async def plan_routes(
    data: RoutePlanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate route plans for a region and date range."""
    service = RoutePlanningService(db)
    result = await service.plan_routes(
        current_user.tenant_id, data.region_id, data.start_date, data.end_date
    )
    return RoutePlanResponse(**result)


@router.get("", response_model=PaginatedResponse[RouteListResponse])
async def list_routes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    region_id: uuid.UUID | None = Query(None),
    route_date: date | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = RouteService(db, user_id=current_user.id)
    items, total = await service.list_routes(
        current_user.tenant_id,
        region_id=region_id,
        route_date=route_date,
        technician_id=technician_id,
        route_status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RouteService(db, user_id=current_user.id)
    return await service.get_route(route_id, current_user.tenant_id)


@router.patch(
    "/{route_id}/status",
    response_model=RouteResponse,
    dependencies=[require_role("org:admin")],
)
async def update_route_status(
    route_id: uuid.UUID,
    data: RouteStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = RouteService(db, user_id=current_user.id)
    return await service.update_status(route_id, current_user.tenant_id, data.status)
