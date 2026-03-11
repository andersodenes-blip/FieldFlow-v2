# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.location import Location
from app.models.route import Route, RouteStatus
from app.models.route_visit import RouteVisit
from app.models.scheduled_visit import ScheduledVisit
from app.models.service_contract import ServiceContract
from app.models.technician import Technician
from app.repositories.route_repository import RouteRepository
from app.schemas.route import RouteListResponse, RouteResponse, RouteVisitResponse
from app.services.audit_service import AuditService


class RouteService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID | None = None):
        self.db = db
        self.repo = RouteRepository(db)
        self.audit = AuditService(db)
        self.user_id = user_id

    async def list_routes(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID | None = None,
        route_date: date | None = None,
        technician_id: uuid.UUID | None = None,
        route_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RouteListResponse], int]:
        routes, total = await self.repo.get_all(
            tenant_id,
            region_id=region_id,
            route_date=route_date,
            technician_id=technician_id,
            status=route_status,
            page=page,
            page_size=page_size,
        )

        items = []
        for route in routes:
            tech = await self._get_technician(route.technician_id)
            visits = await self.repo.get_visits_for_route(route.id)
            total_hours = await self._calc_total_hours(visits)
            items.append(RouteListResponse(
                id=route.id,
                route_date=route.route_date,
                technician_id=route.technician_id,
                technician_name=tech.name if tech else "Ukjent",
                status=route.status.value,
                visit_count=len(visits),
                total_hours=total_hours,
            ))
        return items, total

    async def get_route(self, route_id: uuid.UUID, tenant_id: uuid.UUID) -> RouteResponse:
        route = await self.repo.get_by_id(route_id, tenant_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rute ikke funnet")

        tech = await self._get_technician(route.technician_id)
        visits = await self.repo.get_visits_for_route(route.id)
        visit_responses = await self._build_visit_responses(visits)
        total_hours = sum(v.estimated_work_hours for v in visit_responses)
        total_km = self._calc_total_km(visit_responses)

        return RouteResponse(
            id=route.id,
            tenant_id=route.tenant_id,
            region_id=route.region_id,
            route_date=route.route_date,
            technician_id=route.technician_id,
            technician_name=tech.name if tech else "Ukjent",
            status=route.status.value,
            total_hours=total_hours,
            total_km=total_km,
            visits=visit_responses,
            created_at=route.created_at,
            updated_at=route.updated_at,
        )

    async def update_status(
        self, route_id: uuid.UUID, tenant_id: uuid.UUID, new_status: str
    ) -> RouteResponse:
        route = await self.repo.get_by_id(route_id, tenant_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rute ikke funnet")

        try:
            route_status = RouteStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ugyldig status: {new_status}",
            )

        route.status = route_status
        await self.repo.update(route)
        await self.repo.commit()

        if self.user_id:
            await self.audit.log(
                tenant_id, self.user_id, "update", "route",
                str(route.id), {"status": new_status},
            )

        return await self.get_route(route_id, tenant_id)

    async def _get_technician(self, technician_id: uuid.UUID) -> Technician | None:
        result = await self.db.execute(
            select(Technician).where(Technician.id == technician_id)
        )
        return result.scalar_one_or_none()

    async def _build_visit_responses(self, visits: list[RouteVisit]) -> list[RouteVisitResponse]:
        responses = []
        for rv in visits:
            sv_result = await self.db.execute(
                select(ScheduledVisit).where(ScheduledVisit.id == rv.scheduled_visit_id)
            )
            sv = sv_result.scalar_one_or_none()
            if not sv:
                continue

            job_result = await self.db.execute(
                select(Job).where(Job.id == sv.job_id)
            )
            job = job_result.scalar_one_or_none()
            if not job:
                continue

            # Use estimated_work_hours from route_visit (allocated portion)
            work_hours = rv.estimated_work_hours if rv.estimated_work_hours else 1.0

            loc_result = await self.db.execute(
                select(Location)
                .join(ServiceContract, ServiceContract.location_id == Location.id)
                .where(ServiceContract.id == job.service_contract_id)
            )
            loc = loc_result.scalar_one_or_none()

            responses.append(RouteVisitResponse(
                id=rv.id,
                sequence_order=rv.sequence_order,
                estimated_drive_minutes=rv.estimated_drive_minutes,
                job_id=job.id,
                job_title=job.title,
                location_address=loc.address if loc else "Ukjent",
                latitude=loc.latitude if loc else None,
                longitude=loc.longitude if loc else None,
                estimated_work_hours=work_hours,
            ))
        return responses

    async def _calc_total_hours(self, visits: list[RouteVisit]) -> float:
        """Calculate total hours from estimated_work_hours on each route_visit."""
        return sum(rv.estimated_work_hours or 1.0 for rv in visits)

    def _calc_total_km(self, visits: list[RouteVisitResponse]) -> float:
        # Approximate from drive minutes (rough conversion)
        return sum((v.estimated_drive_minutes or 0) * 0.5 for v in visits)
