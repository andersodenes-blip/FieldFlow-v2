# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Route planning engine — v1-style FIFO distribution.

Ported from v1 geo_plan_stavanger.py core logic, adapted to SQLAlchemy async.

Distribution: weighted scoring (geo 0.4, month 0.4, capacity 0.2).
Day scheduling: simple FIFO with nearest-neighbor job selection.
Splitting: only jobs > 7.5h get split across days.

7.5h rule:
  - home → first_job travel: NOT counted against 7.5h (but stored in drive_minutes)
  - inter-job travel: COUNTED against 7.5h
  - last_job → home travel: NOT counted against 7.5h
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
        3. Assign jobs to technicians (weighted scoring)
        4. Distribute across working days (v1-style FIFO)
        5. Build Route + RouteVisit + ScheduledVisit records
        """
        region = await self._get_region(region_id, tenant_id)
        config = get_region_config(region.name)

        technicians = await self._get_technicians(region_id, tenant_id)
        if not technicians:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": 0,
                "capacity_warnings": ["Ingen aktive teknikere i regionen"],
            }

        all_jobs = await self._get_unscheduled_jobs(region_id, tenant_id)
        if not all_jobs:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": 0,
                "capacity_warnings": [],
            }

        jobs_with_coords = [j for j in all_jobs if j.latitude is not None]
        jobs_without_coords = len(all_jobs) - len(jobs_with_coords)

        if not jobs_with_coords:
            return {
                "routes_created": 0,
                "visits_assigned": 0,
                "jobs_without_coords": jobs_without_coords,
                "capacity_warnings": ["Alle jobber mangler koordinater"],
            }

        await self.route_repo.delete_routes_for_region_dates(
            tenant_id, region_id, start_date, end_date
        )

        tech_jobs = await self._assign_jobs_to_technicians(
            jobs_with_coords, technicians, config, start_date
        )

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

    # ── Data loading ────────────────────────────────────────────────

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
        """Load unscheduled jobs for a region. sla_hours NULL/0 → default 1.0h."""
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
            work_hours = float(sla_hours) if sla_hours and sla_hours > 0 else 1.0
            jobs.append(JobWithCoords(
                job_id=job.id,
                title=job.title,
                address=location.address,
                latitude=location.latitude,
                longitude=location.longitude,
                work_hours=work_hours,
            ))
        return jobs

    # ── Job assignment (weighted scoring) ───────────────────────────

    async def _assign_jobs_to_technicians(
        self,
        jobs: list[JobWithCoords],
        technicians: list[Technician],
        config: RegionRouteConfig,
        reference_date: date,
    ) -> dict[uuid.UUID, list[JobWithCoords]]:
        """Assign jobs to technicians using weighted scoring.

        Scoring: geo distance (0.4), monthly balance (0.4), capacity (0.2).
        Jobs sorted farthest-from-centroid first for better distribution.
        """
        weights = config.reassign_weights

        tech_ids = [t.id for t in technicians]
        month_counts = await self.visit_repo.count_visits_per_technician_month(
            technicians[0].tenant_id, tech_ids, reference_date.year, reference_date.month
        )

        avg_lat = sum(j.latitude for j in jobs) / len(jobs)
        avg_lon = sum(j.longitude for j in jobs) / len(jobs)

        assignment_counts: dict[uuid.UUID, int] = {t.id: 0 for t in technicians}
        tech_jobs: dict[uuid.UUID, list[JobWithCoords]] = {t.id: [] for t in technicians}

        jobs_sorted = sorted(
            jobs,
            key=lambda j: haversine_km(avg_lat, avg_lon, j.latitude, j.longitude),
            reverse=True,
        )

        for job in jobs_sorted:
            best_tech_id = None
            best_score = float("inf")

            for tech in technicians:
                tech_lat = tech.home_latitude or avg_lat
                tech_lon = tech.home_longitude or avg_lon
                geo_dist = haversine_km(tech_lat, tech_lon, job.latitude, job.longitude)
                geo_score = min(geo_dist / 100.0, 1.0)

                total_month = month_counts.get(tech.id, 0) + assignment_counts[tech.id]
                avg_month = sum(month_counts.get(t.id, 0) + assignment_counts[t.id] for t in technicians) / len(technicians)
                month_score = total_month / max(avg_month, 1.0) if avg_month > 0 else 0.0

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

    # ── Working days ────────────────────────────────────────────────

    def _get_working_days(self, start_date: date, end_date: date) -> list[date]:
        """Mon-Fri excluding Norwegian holidays."""
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

    # ── Day distribution (v1-style FIFO) ────────────────────────────

    def _distribute_across_days(
        self,
        tech_jobs: dict[uuid.UUID, list[JobWithCoords]],
        working_days: list[date],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> tuple[dict[uuid.UUID, dict[date, list[JobWithCoords]]], list[str]]:
        """Distribute jobs across working days — v1-style simple FIFO.

        For each technician, iterate over working days. On each day:
        1. Process pending work (leftover from large job splits) first
        2. Pick nearest unplaced job, check if it fits
        3. If whole job fits → place it, continue
        4. If job is large (> max_hours) → split, place what fits, rest to pending
        5. If small job doesn't fit → stop this day, try next day

        7.5h rule:
        - First job of day: only work_hours counted (home→job travel excluded)
        - Subsequent jobs: work_hours + inter-job travel counted
        """
        result: dict[uuid.UUID, dict[date, list[JobWithCoords]]] = {}
        warnings: list[str] = []
        max_hours = config.max_hours_per_day

        for tech_id, jobs in tech_jobs.items():
            tech = next((t for t in technicians if t.id == tech_id), None)
            if not tech:
                continue

            result[tech_id] = {}

            tech_start = getattr(tech, "start_date", None)
            tech_days = [d for d in working_days if not tech_start or d >= tech_start]

            if not tech_days:
                if jobs:
                    warnings.append(f"{tech.name}: ingen arbeidsdager (start_date={tech_start})")
                continue

            home_lat = tech.home_latitude or (jobs[0].latitude if jobs else 59.91)
            home_lon = tech.home_longitude or (jobs[0].longitude if jobs else 10.75)

            pending_work: list[JobWithCoords] = []
            remaining_jobs = list(jobs)
            day_idx = 0

            while (pending_work or remaining_jobs) and day_idx < len(tech_days):
                day = tech_days[day_idx]
                day_idx += 1
                daily_hours = 0.0
                cur_lat, cur_lon = home_lat, home_lon
                day_jobs: list[JobWithCoords] = []
                is_first = True

                # ── 1. Process pending work (multi-day split leftovers) ──
                while pending_work and daily_hours < max_hours:
                    pw = pending_work.pop(0)
                    travel_min = estimate_drive_minutes(
                        cur_lat, cur_lon, pw.latitude, pw.longitude, config
                    )
                    travel_h = 0.0 if is_first else travel_min / 60.0
                    space = max_hours - daily_hours - travel_h

                    if space <= 0:
                        pending_work.insert(0, pw)
                        break

                    work_today = min(pw.work_hours, space)
                    placed = JobWithCoords(
                        job_id=pw.job_id, title=pw.title, address=pw.address,
                        latitude=pw.latitude, longitude=pw.longitude,
                        work_hours=round(work_today, 2),
                        drive_minutes=int(travel_min),
                    )
                    day_jobs.append(placed)
                    daily_hours += travel_h + work_today
                    cur_lat, cur_lon = pw.latitude, pw.longitude
                    is_first = False

                    leftover = round(pw.work_hours - work_today, 2)
                    if leftover > 0.01:
                        pending_work.insert(0, JobWithCoords(
                            job_id=pw.job_id, title=pw.title, address=pw.address,
                            latitude=pw.latitude, longitude=pw.longitude,
                            work_hours=leftover,
                        ))
                        break  # After split, no more jobs today

                # ── 2. Process new jobs (nearest-neighbor selection) ──
                while remaining_jobs and daily_hours < max_hours and not pending_work:
                    nearest_idx = min(
                        range(len(remaining_jobs)),
                        key=lambda i: haversine_km(
                            cur_lat, cur_lon,
                            remaining_jobs[i].latitude, remaining_jobs[i].longitude,
                        ),
                    )
                    job = remaining_jobs[nearest_idx]

                    travel_min = estimate_drive_minutes(
                        cur_lat, cur_lon, job.latitude, job.longitude, config
                    )
                    travel_h = 0.0 if is_first else travel_min / 60.0
                    capacity_cost = travel_h + job.work_hours
                    space = max_hours - daily_hours

                    if capacity_cost <= space:
                        # Whole job fits
                        remaining_jobs.pop(nearest_idx)
                        job.drive_minutes = int(travel_min)
                        day_jobs.append(job)
                        daily_hours += capacity_cost
                        cur_lat, cur_lon = job.latitude, job.longitude
                        is_first = False
                    elif job.work_hours > max_hours:
                        # Large job (> 7.5h) — split: place what fits today
                        remaining_jobs.pop(nearest_idx)
                        work_today = round(space - travel_h, 2)
                        if work_today <= 0:
                            remaining_jobs.insert(0, job)
                            break

                        placed = JobWithCoords(
                            job_id=job.job_id, title=job.title, address=job.address,
                            latitude=job.latitude, longitude=job.longitude,
                            work_hours=work_today,
                            drive_minutes=int(travel_min),
                        )
                        day_jobs.append(placed)
                        daily_hours = max_hours

                        leftover = round(job.work_hours - work_today, 2)
                        if leftover > 0.01:
                            pending_work.insert(0, JobWithCoords(
                                job_id=job.job_id, title=job.title, address=job.address,
                                latitude=job.latitude, longitude=job.longitude,
                                work_hours=leftover,
                            ))
                        break  # After split, no more jobs today
                    else:
                        # Small job doesn't fit → stop, try next day
                        break

                if day_jobs:
                    result[tech_id][day] = day_jobs

            unplaced = len(remaining_jobs) + len(pending_work)
            if unplaced > 0:
                warnings.append(
                    f"{tech.name}: {unplaced} jobber fikk ikke plass i perioden"
                )

        return result, warnings

    # ── Build DB records ────────────────────────────────────────────

    async def _build_routes(
        self,
        tenant_id: uuid.UUID,
        region_id: uuid.UUID,
        tech_day_jobs: dict[uuid.UUID, dict[date, list[JobWithCoords]]],
        technicians: list[Technician],
        config: RegionRouteConfig,
    ) -> tuple[int, int]:
        """Build Route, ScheduledVisit, and RouteVisit records.

        Pre-computes chronological part numbers for multi-day jobs.
        Checks for existing routes to prevent duplicates per (tech, date).
        """
        routes_created = 0
        visits_assigned = 0
        all_job_ids: set[uuid.UUID] = set()

        # Pre-compute chronological part numbers from actual dates
        job_dates: dict[uuid.UUID, list[date]] = defaultdict(list)
        for _tid, day_jobs_inner in tech_day_jobs.items():
            for rd, jlist in day_jobs_inner.items():
                for j in jlist:
                    if rd not in job_dates[j.job_id]:
                        job_dates[j.job_id].append(rd)
        for jid in job_dates:
            job_dates[jid].sort()

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
                    dates_for_job = job_dates.get(job.job_id, [route_date])
                    total_parts_actual = len(dates_for_job)
                    part_actual = dates_for_job.index(route_date) + 1 if route_date in dates_for_job else 1

                    notes = None
                    if total_parts_actual > 1:
                        notes = f"Del {part_actual}/{total_parts_actual} ({job.work_hours:.1f}t)"

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

        # Mark scheduled jobs
        for job_id in all_job_ids:
            result = await self.db.execute(
                select(Job).where(Job.id == job_id)
            )
            job_model = result.scalar_one_or_none()
            if job_model:
                job_model.status = JobStatus.scheduled

        return routes_created, visits_assigned
