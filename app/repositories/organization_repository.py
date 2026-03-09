# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_auth0_org_id(self, auth0_org_id: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.auth0_org_id == auth0_org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
