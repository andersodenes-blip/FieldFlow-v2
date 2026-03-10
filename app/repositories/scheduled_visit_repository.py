# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_visit import ScheduledVisit, VisitStatus


class ScheduledVisitRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, visit: ScheduledVisit) -> ScheduledVisit:
        self.db.add(visit)
        await self.db.flush()
        return visit

    async def bulk_create(self, visits: list[ScheduledVisit]) -> list[ScheduledVisit]:
        self.db.add_all(visits)
        await self.db.flush()
        return visits

    async def get_by_id(self, visit_id: uuid.UUID, tenant_id: uuid.UUID) -> ScheduledVisit | None:
        result = await self.db.execute(
            select(ScheduledVisit).where(
                ScheduledVisit.id == visit_id,
                ScheduledVisit.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_visits_for_technician_date_range(
        self, technician_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[ScheduledVisit]:
        result = await self.db.execute(
            select(ScheduledVisit).where(
                ScheduledVisit.technician_id == technician_id,
                ScheduledVisit.scheduled_date >= start_date,
                ScheduledVisit.scheduled_date <= end_date,
            )
        )
        return list(result.scalars().all())

    async def count_visits_per_technician_month(
        self, tenant_id: uuid.UUID, technician_ids: list[uuid.UUID], year: int, month: int,
    ) -> dict[uuid.UUID, int]:
        """Count scheduled visits per technician for a given month."""
        from sqlalchemy import extract
        result = await self.db.execute(
            select(
                ScheduledVisit.technician_id,
                func.count(ScheduledVisit.id),
            )
            .where(
                ScheduledVisit.tenant_id == tenant_id,
                ScheduledVisit.technician_id.in_(technician_ids),
                extract("year", ScheduledVisit.scheduled_date) == year,
                extract("month", ScheduledVisit.scheduled_date) == month,
            )
            .group_by(ScheduledVisit.technician_id)
        )
        return {row[0]: row[1] for row in result.all()}
