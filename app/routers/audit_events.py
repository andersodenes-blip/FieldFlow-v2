# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.audit_event import AuditEventResponse
from app.schemas.pagination import PaginatedResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-events", tags=["audit-events"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditEventResponse],
    dependencies=[require_role("org:admin")],
)
async def list_audit_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    resource_type: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    service = AuditService(db)
    items, total = await service.list_events(
        current_user.tenant_id,
        resource_type=resource_type,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)
