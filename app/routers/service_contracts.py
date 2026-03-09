# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.service_contract import (
    ServiceContractCreate,
    ServiceContractResponse,
    ServiceContractUpdate,
)
from app.services.service_contract_service import ServiceContractService

router = APIRouter(prefix="/service-contracts", tags=["service-contracts"])


@router.post(
    "",
    response_model=ServiceContractResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_contract(
    data: ServiceContractCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = ServiceContractService(db)
    return await service.create_contract(current_user.tenant_id, data)


@router.get("", response_model=list[ServiceContractResponse])
async def list_contracts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    location_id: uuid.UUID | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
):
    service = ServiceContractService(db)
    return await service.list_contracts(
        current_user.tenant_id,
        location_id=location_id,
        customer_id=customer_id,
        is_active=is_active,
    )


@router.get("/{contract_id}", response_model=ServiceContractResponse)
async def get_contract(
    contract_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = ServiceContractService(db)
    return await service.get_contract(contract_id, current_user.tenant_id)


@router.put(
    "/{contract_id}",
    response_model=ServiceContractResponse,
    dependencies=[require_role("org:admin")],
)
async def update_contract(
    contract_id: uuid.UUID,
    data: ServiceContractUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = ServiceContractService(db)
    return await service.update_contract(contract_id, current_user.tenant_id, data)


@router.delete(
    "/{contract_id}",
    status_code=204,
    dependencies=[require_role("org:admin")],
)
async def delete_contract(
    contract_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = ServiceContractService(db)
    await service.delete_contract(contract_id, current_user.tenant_id)
