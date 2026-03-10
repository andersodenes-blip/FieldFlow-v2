# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Core route planning algorithms.

Implements: haversine distance, geo-based technician assignment (equal_distribution),
nearest-neighbor route ordering, and capacity overflow fixing.
"""
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.route_config import RegionRouteConfig, get_region_config
from app.models.job import Job, JobStatus
from app.models.location import Location
from app.models.region import Region
from app.models.route import Route, RouteStatus
from app.models.route_visit import RouteVisit
from app.models.scheduled_visit import ScheduledVisit, VisitStatus
from app.models.service_contract import ServiceContract
from app.models.technician import Technician
from app.repositories.route_repository import RouteRepository
from app.repositories.scheduled_visit_repository import ScheduledVisitRepository


@dataclass
class JobWithCoords:
    """In-memory representation of a job with its location coordinates."""
    job_id: uuid.UUID
    title: str
    address: str
    latitude: float
    longitude: float
    work_hours: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_drive_minutes(
    lat1: float, lon1: float, lat2: float, lon2: float, config: RegionRouteConfig
) -> float:
    """Estimate driving time in minutes between two points."""
    km = haversine_km(lat1, lon1, lat2, lon2) * config.haversine_correction_factor
    return (km / config.travel_speed_kmh) * 60 + config.parking_minutes


def nearest_neighbor_order(
    jobs: list[JobWithCoords], start_lat: float, start_lon: float
) -> list[JobWithCoords]:
    """Sort jobs by nearest-neighbor heuristic starting from a given point."""
    if not jobs:
        return []
    remaining = list(jobs)
    ordered = []
    current_lat, current_lon = start_lat, start_lon
    while remaining:
        nearest_idx = min(
            range(len(remaining)),
            key=lambda i: haversine_km(current_lat, current_lon, remaining[i].latitude, remaining[i].longitude),
        )
        nearest = remaining.pop(nearest_idx)
        ordered.append(nearest)
        current_lat, current_lon = nearest.latitude, nearest.longitude
    return ordered


class RoutePlanningService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.route_repo = RouteRepository(db)
        self.visit_repo = ScheduledVisitRepository(db)

    async def plan_routes(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Main entry point: plan routes for a region and date range.

        Steps:
        1. Load region config, technicians, and unscheduled jobs
        2. Filter jobs with valid coordinates
        3. Assign jobs to technicians (equal_distribution with geo weighting)
        4. Distribute across working days
        5. Fix overloaded days (capacity limit)
        6. Build Route + RouteVisit + ScheduledVisit records
        7. Order visits per day using nearest-neighbor
        """
        # Load region
        region = await self._get_region(region_id, tenant_id)
        config = get_region_config(region.name)

        # Load active technicians for this region
        technicians = await self._get_technicians(region_id, tenant_id)
        if not technicians:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": 0,
                "capacity_warnings": ["Ingen aktive teknikere i regionen"],
            }

        # Load unscheduled jobs for this region
        all_jobs = await self._get_unscheduled_jobs(region_id, tenant_id)
        if not all_jobs:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": 0,
                "capacity_warnings": [],
            }

        # Separate jobs with/without coordinates
        jobs_with_coords = [j for j in all_jobs if j.latitude is not None]
        jobs_without_coords = len(all_jobs) - len(jobs_with_coords)

        if not jobs_with_coords:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": jobs_without_coords,
                "capacity_warnings": ["Alle jobber mangler koordinater"],
            }

        # Delete existing draft routes for this period
        deleted = await self.route_repo.delete_routes_for_region_dates(
            tenant_id, region_id, start_date, end_date
        )

        # Step 1: Assign jobs to technicians (geo-weighted equal distribution)
        tech_jobs = await self._assign_jobs_to_technicians(
            jobs_with_coords, technicians, config, start_date
        )

        # Step 2: Distribute across working days
        working_days = self._get_working_days(start_date, end_date)
        if not working_days:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": jobs_without_coords,
                "capacity_warnings": ["Ingen arbeidsdager i perioden"],
            }

        tech_day_jobs = self._distribute_across_days(tech_jobs, working_days, config)

        # Step 3: Fix overloaded days
        capacity_warnings = self._fix_overloaded_days(tech_day_jobs, technicians, config)

        # Step 4: Build routes with nearest-neighbor ordering
        routes_created, visits_assigned = await self._build_routes(
            tenant_id, region_id, tech_day_jobs, technicians, config
        )

        await self.route_repo.commit()

        return {
            "routes_created": routes_created,
            "visits_assigned": visits_assigned,
            "jobs_without_coords": jobs_without_coords,
            "capacity_warnings": capacity_warnings,
        }

    async def _get_region(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> Region:
        result = await self.db.execute(
            select(Region).where(Region.id == region_id, Region.tenant_id == tenant_id)
        )
        region = result.scalar_one_or_none()
        if not region:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region ikke funnet")
        return region

    async def _get_technicians(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> list[Technician]:
        result = await self.db.execute(
            select(Technician).where(
                Technician.region_id == region_id,
                Technician.tenant_id == tenant_id,
                Technician.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def _get_unscheduled_jobs(self, region_id: uuid.UUID, tenant_id: uuid.UUID) -> list[JobWithCoords]:
        """Load unscheduled jobs for a region with their location coordinates."""
        result = await self.db.execute(
            select(Job, Location)
            .join(ServiceContract, Job.service_contract_id == ServiceContract.id)
            .join(Location, ServiceContract.location_id == Location.id)
            .where(
                Job.tenant_id == tenant_id,
                Job.status == JobStatus.unscheduled,
                Location.city == select(Region.name).where(Region.id == region_id).correlate_except(Region).scalar_subquery(),
            )
        )
        jobs = []
        for job, location in result.all():
            work_hours = 4.0  # default
            jobs.append(JobWithCoords(
                job_id=job.id,
                title=job.title,
                address=location.address,
                latitude=location.latitude,
                longitude=location.longitude,
                work_hours=work_hours,
            ))
        return jobs

    async def _assign_jobs_to_technicians(
        self,
        jobs: list[JobWithCoords],
        technicians: list[Technician],
        config: RegionRouteConfig,
        reference_date: date,
    ) -> dict[uuid.UUID, list[JobWithCoords]]:
        """Assign jobs to technicians using weighted scoring.

        equal_distribution mode: each technician gets roughly equal share.
        Scoring weights: geo distance (0.4), monthly balance (0.4), capacity (0.2).
        """
        weights = config.reassign_weights

        # Get existing visit counts per technician for the month
        tech_ids = [t.id for t in technicians]
        month_counts = await self.visit_repo.count_visits_per_technician_month(
            technicians[0].tenant_id, tech_ids, reference_date.year, reference_date.month
        )

        # Calculate centroid of all jobs for geo scoring
        avg_lat = sum(j.latitude for j in jobs) / len(jobs)
        avg_lon = sum(j.longitude for j in jobs) / len(jobs)

        # Track assignment counts during this planning run
        assignment_counts: dict[uuid.UUID, int] = {t.id: 0 for t in technicians}
        tech_jobs: dict[uuid.UUID, list[JobWithCoords]] = {t.id: [] for t in technicians}

        # Sort jobs by distance from centroid (farthest first) for better distribution
        jobs_sorted = sorted(jobs, key=lambda j: haversine_km(avg_lat, avg_lon, j.latitude, j.longitude), reverse=True)

        for job in jobs_sorted:
            best_tech_id = None
            best_score = float("inf")

            for tech in technicians:
                # Geo score: distance from technician home to job
                # Use region centroid as fallback if technician has no home coords
                tech_lat = getattr(tech, "home_latitude", None) or avg_lat
                tech_lon = getattr(tech, "home_longitude", None) or avg_lon
                geo_dist = haversine_km(tech_lat, tech_lon, job.latitude, job.longitude)
                max_dist = 100.0  # normalize to ~100km
                geo_score = min(geo_dist / max_dist, 1.0)

                # Month balance score: prefer technicians with fewer visits this month
                total_month = month_counts.get(tech.id, 0) + assignment_counts[tech.id]
                avg_month = sum(month_counts.get(t.id, 0) + assignment_counts[t.id] for t in technicians) / len(technicians)
                month_score = total_month / max(avg_month, 1.0) if avg_month > 0 else 0.0

                # Capacity score: prefer technicians with fewer assignments in this batch
                avg_assigned = sum(assignment_counts.values()) / len(technicians)
                capacity_score = assignment_counts[tech.id] / max(avg_assigned, 1.0) if avg_assigned > 0 else 0.0

                score = (
                    weights.geo * geo_score
                    + weights.month * month_score
                    + weights.capacity * capacity_score
                )
                if score < best_score:
                    best_score = score
                    best_tech_id = tech.id

            tech_jobs[best_tech_id].append(job)
            assignment_counts[best_tech_id] += 1

        return tech_jobs

    def _get_working_days(self, start_date: date, end_date: date) -> list[date]:
        """Get working days (Mon-Fri) in the date range."""
        days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday=0, Friday=4
                days.append(current)
            current += timedelta(days=1)
        return days

    def _distribute_across_days(
        self,
        tech_jobs: dict[uuid.UUID, list[JobWithCoords]],
        working_days: list[date],
        config: RegionRouteConfig,
    ) -> dict[uuid.UUID, dict[date, list[JobWithCoords]]]:
        """Distribute each technician's jobs evenly across working days."""
        result: dict[uuid.UUID, dict[date, list[JobWithCoords]]] = {}

        for tech_id, jobs in tech_jobs.items():
            result[tech_id] = {d: [] for d in working_days}
            if not jobs:
                continue

            # Calculate max jobs per day based on capacity
            max_jobs_per_day = max(1, int(config.max_hours_per_day / config.default_work_hours))

            # Round-robin distribute
            for i, job in enumerate(jobs):
                day_idx = i % len(working_days)
                result[tech_id][working_days[day_idx]].append(job)

        return result

    def _fix_overloaded_days(
        self,
        tech_day_jobs: dict[uuid.UUID, dict[date, list[JobWithCoords]]],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> list[str]:
        """Move jobs from overloaded days to days with capacity."""
        warnings = []
        max_hours = config.max_hours_per_day

        for tech_id, day_jobs in tech_day_jobs.items():
            tech_name = next((t.name for t in technicians if t.id == tech_id), "Ukjent")
            iterations = 0

            while iterations < config.max_capacity_fix_iterations:
                iterations += 1
                moved = False

                for day, jobs in sorted(day_jobs.items()):
                    total_hours = sum(j.work_hours for j in jobs)
                    if total_hours <= max_hours:
                        continue

                    # Find a day with capacity
                    for target_day in sorted(day_jobs.keys()):
                        if target_day == day:
                            continue
                        target_hours = sum(j.work_hours for j in day_jobs[target_day])
                        if target_hours + jobs[-1].work_hours <= max_hours:
                            moved_job = jobs.pop()
                            day_jobs[target_day].append(moved_job)
                            moved = True
                            break

                    if moved:
                        break

                if not moved:
                    # Check if any days are still overloaded
                    for day, jobs in day_jobs.items():
                        total = sum(j.work_hours for j in jobs)
                        if total > max_hours:
                            warnings.append(
                                f"{tech_name}: {day.isoformat()} har {total:.1f}t (maks {max_hours:.1f}t)"
                            )
                    break

        return warnings

    async def _build_routes(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID,
        tech_day_jobs: dict[uuid.UUID, dict[date, list[JobWithCoords]]],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> tuple[int, int]:
        """Build Route, ScheduledVisit, and RouteVisit records."""
        routes_created = 0
        visits_assigned = 0

        for tech_id, day_jobs in tech_day_jobs.items():
            tech = next((t for t in technicians if t.id == tech_id), None)
            if not tech:
                continue

            # Technician start location (fallback to first job)
            start_lat = getattr(tech, "home_latitude", None)
            start_lon = getattr(tech, "home_longitude", None)

            for route_date, jobs in sorted(day_jobs.items()):
                if not jobs:
                    continue

                # Use first job as start if no home coordinates
                if start_lat is None:
                    start_lat = jobs[0].latitude
                    start_lon = jobs[0].longitude

                # Order jobs using nearest-neighbor
                ordered_jobs = nearest_neighbor_order(jobs, start_lat, start_lon)

                # Create Route
                route = Route(
                    tenant_id=tenant_id,
                    region_id=region_id,
                    route_date=route_date,
                    technician_id=tech_id,
                    status=RouteStatus.draft,
                )
                route = await self.route_repo.create(route)
                routes_created += 1

                # Create ScheduledVisit + RouteVisit for each job
                prev_lat, prev_lon = start_lat, start_lon
                route_visits = []
                for seq, job in enumerate(ordered_jobs, 1):
                    # Create ScheduledVisit
                    sv = ScheduledVisit(
                        tenant_id=tenant_id,
                        job_id=job.job_id,
                        technician_id=tech_id,
                        scheduled_date=route_date,
                        status=VisitStatus.planned,
                    )
                    sv = await self.visit_repo.create(sv)

                    # Calculate drive time from previous point
                    drive_min = int(estimate_drive_minutes(
                        prev_lat, prev_lon, job.latitude, job.longitude, config
                    ))

                    # Create RouteVisit
                    rv = RouteVisit(
                        tenant_id=tenant_id,
                        route_id=route.id,
                        scheduled_visit_id=sv.id,
                        sequence_order=seq,
                        estimated_drive_minutes=drive_min,
                    )
                    route_visits.append(rv)
                    prev_lat, prev_lon = job.latitude, job.longitude
                    visits_assigned += 1

                await self.route_repo.bulk_create_visits(route_visits)

                # Update job status to scheduled
                job_ids = [j.job_id for j in ordered_jobs]
                for job_id in job_ids:
                    result = await self.db.execute(
                        select(Job).where(Job.id == job_id)
                    )
                    job_model = result.scalar_one_or_none()
                    if job_model:
                        job_model.status = JobStatus.scheduled

        return routes_created, visits_assigned
