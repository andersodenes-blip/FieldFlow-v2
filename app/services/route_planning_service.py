# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Core route planning algorithms.

Implements: haversine distance with correction factor, geo-based technician
assignment (equal_distribution), travel-aware daily capacity (7.5h), nearest-
neighbor route ordering during distribution, multi-day job splitting with
pending_work priority, and Norwegian holiday exclusion.

7.5h rule: work_hours + inter-job travel counts. Home→first_job and
last_job→home travel is logged but NOT counted against the limit.
"""
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.route_config import RegionRouteConfig, get_region_config


@dataclass
class JobWithCoords:
    """In-memory representation of a job with its location coordinates."""
    job_id: uuid.UUID
    title: str
    address: str
    latitude: float
    longitude: float
    work_hours: float
    part: int = 1
    total_parts: int = 1
    drive_minutes: int = 0  # estimated drive time from previous stop


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
    """Estimate driving time in minutes between two points.

    Formula from v1:
      travel_hours = (distance_km * correction_factor) / travel_speed_kmh
                   + parking_minutes / 60
    Returns minutes.
    """
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


# ── Norwegian holidays ──────────────────────────────────────────────────


def _easter_date(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_norwegian_holidays(year: int) -> set[date]:
    """Return all Norwegian public holidays for a given year."""
    easter = _easter_date(year)
    return {
        date(year, 1, 1),                    # Nyttarsdag
        easter - timedelta(days=3),           # Skjaertorsdag
        easter - timedelta(days=2),           # Langfredag
        easter,                               # 1. paskedag
        easter + timedelta(days=1),           # 2. paskedag
        date(year, 5, 1),                     # Arbeidernes dag
        date(year, 5, 17),                    # Grunnlovsdag
        easter + timedelta(days=39),          # Kristi himmelfartsdag
        easter + timedelta(days=49),          # 1. pinsedag
        easter + timedelta(days=50),          # 2. pinsedag
        date(year, 12, 25),                   # 1. juledag
        date(year, 12, 26),                   # 2. juledag
    }


# ── Service ─────────────────────────────────────────────────────────────


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
        4. Distribute across working days (travel-aware, 7.5h incl. travel)
        5. Build Route + RouteVisit + ScheduledVisit records
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

        # Load all unscheduled jobs for the region
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
        await self.route_repo.delete_routes_for_region_dates(
            tenant_id, region_id, start_date, end_date
        )

        # Step 1: Assign jobs to technicians (geo-weighted equal distribution)
        tech_jobs = await self._assign_jobs_to_technicians(
            jobs_with_coords, technicians, config, start_date
        )

        # Step 2: Distribute across working days (travel-aware capacity)
        working_days = self._get_working_days(start_date, end_date)
        if not working_days:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": jobs_without_coords,
                "capacity_warnings": ["Ingen arbeidsdager i perioden"],
            }

        tech_day_jobs, capacity_warnings = self._distribute_across_days(
            tech_jobs, working_days, technicians, config
        )

        # Step 3: Build routes (jobs already ordered by nearest-neighbor)
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

    async def _get_unscheduled_jobs(
        self, region_id: uuid.UUID, tenant_id: uuid.UUID,
    ) -> list[JobWithCoords]:
        """Load ALL unscheduled jobs for a region.

        Work hours come from service_contract.sla_hours:
        - NULL or 0 -> default 1.0 hour
        """
        region_name_sq = (
            select(Region.name)
            .where(Region.id == region_id)
            .correlate_except(Region)
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(Job, Location, ServiceContract.sla_hours)
            .join(ServiceContract, Job.service_contract_id == ServiceContract.id)
            .join(Location, ServiceContract.location_id == Location.id)
            .where(
                Job.tenant_id == tenant_id,
                Job.status == JobStatus.unscheduled,
                Location.city == region_name_sq,
            )
            .order_by(Job.created_at.asc())
        )
        jobs = []
        for job, location, sla_hours in result.all():
            if not sla_hours or sla_hours <= 0:
                work_hours = 1.0
            else:
                work_hours = float(sla_hours)
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
                tech_lat = tech.home_latitude or avg_lat
                tech_lon = tech.home_longitude or avg_lon
                geo_dist = haversine_km(tech_lat, tech_lon, job.latitude, job.longitude)
                max_dist = 100.0
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
        """Get working days (Mon-Fri, excluding Norwegian holidays) in the date range."""
        # Collect holidays for all years in the range
        holidays: set[date] = set()
        for year in range(start_date.year, end_date.year + 1):
            holidays |= get_norwegian_holidays(year)

        days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5 and current not in holidays:
                days.append(current)
            current += timedelta(days=1)
        return days

    def _place_job(
        self,
        job: JobWithCoords,
        hours_today: float,
        cur_lat: float,
        cur_lon: float,
        max_hours: float,
        config: RegionRouteConfig,
        day_jobs: list[JobWithCoords],
        pending_work: list[JobWithCoords],
        count_travel: bool = True,
    ) -> tuple[float, float, float, bool]:
        """Place a single job on the current day.

        Travel from home to first job is stored in drive_minutes but does NOT
        count against the 7.5h capacity limit (count_travel=False).
        Travel between jobs DOES count (count_travel=True).

        Returns (new_hours_today, new_cur_lat, new_cur_lon, placed).
        placed=False means the job was pushed to pending_work unchanged.
        """
        travel_min = estimate_drive_minutes(cur_lat, cur_lon, job.latitude, job.longitude, config)
        # Home→first job travel is logged but not counted against capacity
        capacity_travel_hours = (travel_min / 60.0) if count_travel else 0.0
        capacity_cost = capacity_travel_hours + job.work_hours
        space_left = max_hours - hours_today

        if space_left <= 0:
            # Day already full — push entire job to pending
            pending_work.insert(0, job)
            return hours_today, cur_lat, cur_lon, False

        if capacity_cost <= space_left:
            # Whole job fits today
            job.drive_minutes = int(travel_min)
            day_jobs.append(job)
            return hours_today + capacity_cost, job.latitude, job.longitude, True

        # Job doesn't fit whole today.
        # Only split genuinely large jobs (> max_hours). Small jobs that
        # don't fit are pushed whole to the next day. This avoids
        # pathological cascading splits where a 2h job gets split into
        # 3+ parts, each non-final part wasting an exclusive day.
        if job.work_hours <= max_hours:
            pending_work.insert(0, job)
            return hours_today, cur_lat, cur_lon, False

        # Large job (> 7.5h) — partial fit, split the job
        work_today = round(space_left - capacity_travel_hours, 2)
        if work_today <= 0:
            # Not even travel fits — push to next day
            pending_work.insert(0, job)
            return hours_today, cur_lat, cur_lon, False

        leftover_hours = round(job.work_hours - work_today, 2)

        # Ensure total_parts reflects the actual split (even for jobs < 7.5h
        # that are split due to space constraints on the current day)
        actual_total = max(job.total_parts, job.part + 1)

        today_part = JobWithCoords(
            job_id=job.job_id, title=job.title, address=job.address,
            latitude=job.latitude, longitude=job.longitude,
            work_hours=work_today,
            part=job.part, total_parts=actual_total,
            drive_minutes=int(travel_min),
        )
        day_jobs.append(today_part)

        if leftover_hours > 0:
            leftover = JobWithCoords(
                job_id=job.job_id, title=job.title, address=job.address,
                latitude=job.latitude, longitude=job.longitude,
                work_hours=leftover_hours,
                part=job.part + 1, total_parts=actual_total,
            )
            pending_work.insert(0, leftover)

        return max_hours, job.latitude, job.longitude, True

    def _distribute_across_days(
        self,
        tech_jobs: dict[uuid.UUID, list[JobWithCoords]],
        working_days: list[date],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> tuple[dict[uuid.UUID, dict[date, list[JobWithCoords]]], list[str]]:
        """Distribute jobs across working days with travel-aware capacity.

        Daily capacity: 7.5h of work_hours + inter-job travel.
        Travel from home to first job is logged but NOT counted against 7.5h.
        Travel from last job back home is also NOT counted.
        Uses nearest-neighbor to pick next job during distribution.
        Handles multi-day jobs via pending_work (processed before new jobs).
        Respects technician start_date.

        Multi-day job rule: non-final parts of multi-day jobs get the day
        exclusively (no other jobs). Only the LAST part (e.g., Dag 2 av 2)
        can be combined with new jobs if time allows. If a new job is split
        during placement, no more jobs are added that day.
        """
        result: dict[uuid.UUID, dict[date, list[JobWithCoords]]] = {}
        warnings: list[str] = []
        max_hours = config.max_hours_per_day

        for tech_id, jobs in tech_jobs.items():
            tech = next((t for t in technicians if t.id == tech_id), None)
            if not tech:
                continue

            result[tech_id] = {}

            # Pre-calculate total_parts for multi-day jobs
            for job in jobs:
                if job.work_hours > max_hours:
                    job.total_parts = math.ceil(job.work_hours / max_hours)

            # Filter working days by technician start_date
            tech_start = getattr(tech, "start_date", None)
            tech_days = [d for d in working_days if not tech_start or d >= tech_start]

            if not tech_days:
                if jobs:
                    warnings.append(f"{tech.name}: ingen arbeidsdager (start_date={tech_start})")
                continue

            # Tech home position (fallback to first job)
            home_lat = tech.home_latitude or (jobs[0].latitude if jobs else 59.91)
            home_lon = tech.home_longitude or (jobs[0].longitude if jobs else 10.75)

            pending_work: list[JobWithCoords] = []
            remaining_jobs = list(jobs)
            day_idx = 0

            while (pending_work or remaining_jobs) and day_idx < len(tech_days):
                day = tech_days[day_idx]
                day_idx += 1
                hours_today = 0.0
                cur_lat, cur_lon = home_lat, home_lon
                day_jobs: list[JobWithCoords] = []
                first_placed = False  # Track if first job of day has been placed
                multi_day_exclusive = False  # Day reserved for multi-day job

                # ── Process pending_work FIRST (leftover from multi-day splits) ──
                while pending_work and hours_today < max_hours:
                    pw = pending_work.pop(0)
                    is_nonfinal = pw.total_parts > 1 and pw.part < pw.total_parts
                    pending_len = len(pending_work)

                    hours_today, cur_lat, cur_lon, placed = self._place_job(
                        pw, hours_today, cur_lat, cur_lon, max_hours, config,
                        day_jobs, pending_work,
                        count_travel=first_placed,
                    )
                    if placed:
                        first_placed = True
                        # Non-final part of multi-day job → no other jobs today
                        if is_nonfinal:
                            multi_day_exclusive = True
                        # Job was split (new leftover) → no other jobs today
                        if len(pending_work) > pending_len:
                            multi_day_exclusive = True
                    if not placed:
                        break  # day full — pending stays for next day

                # ── Process new jobs only if day isn't reserved ──
                if not multi_day_exclusive:
                    while remaining_jobs and hours_today < max_hours:
                        nearest_idx = min(
                            range(len(remaining_jobs)),
                            key=lambda i: haversine_km(cur_lat, cur_lon, remaining_jobs[i].latitude, remaining_jobs[i].longitude),
                        )
                        job = remaining_jobs.pop(nearest_idx)
                        pending_len = len(pending_work)

                        hours_today, cur_lat, cur_lon, placed = self._place_job(
                            job, hours_today, cur_lat, cur_lon, max_hours, config,
                            day_jobs, pending_work,
                            count_travel=first_placed,
                        )
                        if placed:
                            first_placed = True
                            # Job was split → multi-day start, stop adding more
                            if len(pending_work) > pending_len:
                                break
                        if not placed:
                            break  # day full

                # ── Post-check: enforce multi-day exclusivity ──
                # If any job on this day is a non-final multi-day part,
                # remove all OTHER jobs and push them back to remaining_jobs.
                if len(day_jobs) > 1:
                    nonfinal_idx = None
                    for idx, dj in enumerate(day_jobs):
                        is_nonfinal = dj.total_parts > 1 and dj.part < dj.total_parts
                        if is_nonfinal:
                            nonfinal_idx = idx
                            break
                    if nonfinal_idx is not None:
                        # Keep only the multi-day part
                        kept = day_jobs[nonfinal_idx]
                        evicted = [dj for i, dj in enumerate(day_jobs) if i != nonfinal_idx]
                        day_jobs = [kept]
                        # Push evicted jobs back (they'll be re-placed on future days)
                        remaining_jobs = evicted + remaining_jobs

                if day_jobs:
                    result[tech_id][day] = day_jobs

            # Report unplaced jobs
            unplaced = len(remaining_jobs) + len(pending_work)
            if unplaced > 0:
                warnings.append(
                    f"{tech.name}: {unplaced} jobber fikk ikke plass i perioden"
                )

        return result, warnings

    async def _build_routes(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID,
        tech_day_jobs: dict[uuid.UUID, dict[date, list[JobWithCoords]]],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> tuple[int, int]:
        """Build Route, ScheduledVisit, and RouteVisit records.

        Jobs are already ordered by nearest-neighbor from distribution.
        Checks for existing routes to prevent duplicates per (tech, date).
        """
        routes_created = 0
        visits_assigned = 0
        # Track all job_ids we've seen — mark scheduled after all days processed
        all_job_ids: set[uuid.UUID] = set()

        for tech_id, day_jobs in tech_day_jobs.items():
            tech = next((t for t in technicians if t.id == tech_id), None)
            if not tech:
                continue

            for route_date, jobs in sorted(day_jobs.items()):
                if not jobs:
                    continue

                # Check for existing route to prevent duplicates
                existing = await self.db.execute(
                    select(Route).where(
                        Route.tenant_id == tenant_id,
                        Route.technician_id == tech_id,
                        Route.route_date == route_date,
                    )
                )
                route = existing.scalar_one_or_none()
                if route:
                    # Reuse existing route — delete old visits first
                    await self.db.execute(
                        delete(RouteVisit).where(RouteVisit.route_id == route.id)
                    )
                else:
                    route = Route(
                        tenant_id=tenant_id,
                        region_id=region_id,
                        route_date=route_date,
                        technician_id=tech_id,
                        status=RouteStatus.draft,
                    )
                    route = await self.route_repo.create(route)
                routes_created += 1

                route_visits = []
                for seq, job in enumerate(jobs, 1):
                    notes = None
                    if job.total_parts > 1:
                        notes = f"Del {job.part}/{job.total_parts} ({job.work_hours:.1f}t)"

                    sv = ScheduledVisit(
                        tenant_id=tenant_id,
                        job_id=job.job_id,
                        technician_id=tech_id,
                        scheduled_date=route_date,
                        status=VisitStatus.planned,
                        notes=notes,
                    )
                    sv = await self.visit_repo.create(sv)

                    rv = RouteVisit(
                        tenant_id=tenant_id,
                        route_id=route.id,
                        scheduled_visit_id=sv.id,
                        sequence_order=seq,
                        estimated_drive_minutes=job.drive_minutes,
                        estimated_work_hours=job.work_hours,
                    )
                    route_visits.append(rv)
                    visits_assigned += 1
                    all_job_ids.add(job.job_id)

                await self.route_repo.bulk_create_visits(route_visits)

        scheduled_job_ids = all_job_ids

        # Mark fully scheduled jobs
        for job_id in scheduled_job_ids:
            result = await self.db.execute(
                select(Job).where(Job.id == job_id)
            )
            job_model = result.scalar_one_or_none()
            if job_model:
                job_model.status = JobStatus.scheduled

        return routes_created, visits_assigned
