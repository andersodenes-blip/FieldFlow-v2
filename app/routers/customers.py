# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.pagination import PaginatedResponse
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_customer(
    data: CustomerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = CustomerService(db, user_id=current_user.id)
    customer = await service.create_customer(current_user.tenant_id, data)
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    service = CustomerService(db, user_id=current_user.id)
    customers, total = await service.list_customers(
        current_user.tenant_id, search=search, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order,
    )
    return PaginatedResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = CustomerService(db, user_id=current_user.id)
    result = await service.get_customer_with_count(customer_id, current_user.tenant_id)
    resp = CustomerResponse.model_validate(result["customer"])
    resp.location_count = result["location_count"]
    return resp


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[require_role("org:admin")],
)
async def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = CustomerService(db, user_id=current_user.id)
    customer = await service.update_customer(customer_id, current_user.tenant_id, data)
    return CustomerResponse.model_validate(customer)


@router.delete(
    "/{customer_id}",
    status_code=204,
    dependencies=[require_role("org:admin")],
)
async def delete_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = CustomerService(db, user_id=current_user.id)
    await service.delete_customer(customer_id, current_user.tenant_id)
