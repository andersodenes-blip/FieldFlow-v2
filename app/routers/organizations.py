# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import OrganizationResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    auth0_org_id: str
    name: str


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Organization).where(Organization.tenant_id == current_user.tenant_id)
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=201,
    dependencies=[require_role("org:admin")],
)
async def create_organization(
    data: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    # Check for duplicate auth0_org_id
    existing = await db.execute(
        select(Organization).where(Organization.auth0_org_id == data.auth0_org_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization with this auth0_org_id already exists",
        )

    org = Organization(
        id=uuid.uuid4(),
        auth0_org_id=data.auth0_org_id,
        name=data.name,
        tenant_id=current_user.tenant_id,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org
