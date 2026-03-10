# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.route import Route, RouteStatus
from app.models.route_visit import RouteVisit
from app.models.scheduled_visit import ScheduledVisit


class RouteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, route: Route) -> Route:
        self.db.add(route)
        await self.db.flush()
        return route

    async def bulk_create_visits(self, visits: list[RouteVisit]) -> None:
        self.db.add_all(visits)
        await self.db.flush()

    async def get_by_id(self, route_id: uuid.UUID, tenant_id: uuid.UUID) -> Route | None:
        result = await self.db.execute(
            select(Route)
            .where(Route.id == route_id, Route.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID | None = None,
        route_date: date | None = None,
        technician_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Route], int]:
        query = select(Route).where(Route.tenant_id == tenant_id)
        count_query = select(func.count(Route.id)).where(Route.tenant_id == tenant_id)

        if region_id:
            query = query.where(Route.region_id == region_id)
            count_query = count_query.where(Route.region_id == region_id)
        if route_date:
            query = query.where(Route.route_date == route_date)
            count_query = count_query.where(Route.route_date == route_date)
        if technician_id:
            query = query.where(Route.technician_id == technician_id)
            count_query = count_query.where(Route.technician_id == technician_id)
        if status:
            query = query.where(Route.status == RouteStatus(status))
            count_query = count_query.where(Route.status == RouteStatus(status))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Route.route_date, Route.created_at)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_visits_for_route(self, route_id: uuid.UUID) -> list[RouteVisit]:
        result = await self.db.execute(
            select(RouteVisit)
            .where(RouteVisit.route_id == route_id)
            .order_by(RouteVisit.sequence_order)
        )
        return list(result.scalars().all())

    async def delete_routes_for_region_dates(
        self, tenant_id: uuid.UUID, region_id: uuid.UUID, start_date: date, end_date: date
    ) -> int:
        """Delete existing draft routes for a region/date range before replanning.

        Also resets associated jobs to 'unscheduled' and deletes scheduled_visits.
        """
        # Find route IDs to delete
        result = await self.db.execute(
            select(Route.id).where(
                Route.tenant_id == tenant_id,
                Route.region_id == region_id,
                Route.route_date >= start_date,
                Route.route_date <= end_date,
                Route.status == RouteStatus.draft,
            )
        )
        route_ids = [r for r in result.scalars().all()]
        if not route_ids:
            return 0

        # Find scheduled_visit IDs linked to these routes
        sv_result = await self.db.execute(
            select(RouteVisit.scheduled_visit_id).where(
                RouteVisit.route_id.in_(route_ids)
            )
        )
        sv_ids = [r for r in sv_result.scalars().all()]

        # Find job IDs linked to these scheduled_visits → reset to unscheduled
        if sv_ids:
            job_result = await self.db.execute(
                select(ScheduledVisit.job_id).where(
                    ScheduledVisit.id.in_(sv_ids)
                )
            )
            job_ids = [r for r in job_result.scalars().all()]
            if job_ids:
                await self.db.execute(
                    update(Job)
                    .where(Job.id.in_(job_ids), Job.status == JobStatus.scheduled)
                    .values(status=JobStatus.unscheduled)
                )

        # Delete route_visits
        await self.db.execute(
            delete(RouteVisit).where(RouteVisit.route_id.in_(route_ids))
        )
        # Delete scheduled_visits
        if sv_ids:
            await self.db.execute(
                delete(ScheduledVisit).where(ScheduledVisit.id.in_(sv_ids))
            )
        # Delete routes
        await self.db.execute(
            delete(Route).where(Route.id.in_(route_ids))
        )
        return len(route_ids)

    async def update(self, route: Route) -> Route:
        await self.db.flush()
        return route

    async def commit(self) -> None:
        await self.db.commit()
