# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import json
import uuid

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.dependencies import get_db
from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.location import Location
from app.models.region import Region
from app.models.route import Route
from app.models.route_visit import RouteVisit
from app.models.scheduled_visit import ScheduledVisit
from app.models.service_contract import ServiceContract
from app.models.technician import Technician
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.route_planning_service import get_norwegian_holidays

router = APIRouter(prefix="/app", tags=["frontend"])
templates = Jinja2Templates(directory="app/templates")


async def _get_user_from_cookie(request: Request, db: AsyncSession) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        repo = UserRepository(db)
        return await repo.get_by_id(uuid.UUID(user_id))
    except (JWTError, ValueError):
        return None


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "auth0_enabled": settings.auth0_enabled,
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/app/login")
    response.delete_cookie("access_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    region_id: str | None = Query(None),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    tid = user.tenant_id

    # Load all regions
    result = await db.execute(
        select(Region).where(Region.tenant_id == tid).order_by(Region.name)
    )
    regions = list(result.scalars().all())

    selected_region = None
    if regions:
        if region_id:
            selected_region = next((r for r in regions if str(r.id) == region_id), regions[0])
        else:
            selected_region = regions[0]

    # ── Job counts by status (filtered by region) ──
    region_filter = []
    if selected_region:
        region_filter = [
            Job.service_contract_id == ServiceContract.id,
            ServiceContract.location_id == Location.id,
            Location.city == selected_region.name,
        ]

    status_counts = {}
    for s in [JobStatus.unscheduled, JobStatus.scheduled, JobStatus.in_progress, JobStatus.completed, JobStatus.cancelled]:
        q = select(func.count(Job.id)).where(Job.tenant_id == tid, Job.status == s)
        if region_filter:
            q = q.join(ServiceContract, Job.service_contract_id == ServiceContract.id).join(
                Location, ServiceContract.location_id == Location.id
            ).where(Location.city == selected_region.name)
        count = (await db.execute(q)).scalar() or 0
        status_counts[s.value] = count

    total_jobs = sum(status_counts.values())
    completed = status_counts["completed"]
    scheduled = status_counts["scheduled"] + status_counts["in_progress"]
    unscheduled = status_counts["unscheduled"]
    pct = round(completed / total_jobs * 100) if total_jobs else 0
    sched_pct = round(scheduled / total_jobs * 100) if total_jobs else 0
    unsched_pct = round(unscheduled / total_jobs * 100) if total_jobs else 0

    # Year progress
    today = date.today()
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    year_days = (year_end - year_start).days + 1
    days_passed = (today - year_start).days
    year_pct = round(days_passed / year_days * 100)

    if pct >= year_pct:
        status_klasse = "good"
        status_tekst = "I rute"
    elif pct >= year_pct - 10:
        status_klasse = "ok"
        status_tekst = "Nesten i rute"
    else:
        status_klasse = "behind"
        status_tekst = "Pa etterskudd"

    # ── Total hours (sum of sla_hours for region) ──
    hours_q = select(func.sum(ServiceContract.sla_hours)).join(
        Job, Job.service_contract_id == ServiceContract.id
    ).join(Location, ServiceContract.location_id == Location.id).where(
        Job.tenant_id == tid,
    )
    if selected_region:
        hours_q = hours_q.where(Location.city == selected_region.name)
    total_hours = (await db.execute(hours_q)).scalar() or 0.0

    # ── Per-technician stats ──
    tech_query = (
        select(Technician)
        .where(Technician.tenant_id == tid, Technician.is_active == True)
    )
    if selected_region:
        tech_query = tech_query.where(Technician.region_id == selected_region.id)
    tech_query = tech_query.order_by(Technician.name)

    result = await db.execute(tech_query)
    raw_techs = list(result.scalars().all())

    tech_stats = []
    for tech in raw_techs:
        # Count jobs per status via scheduled_visits -> jobs
        tech_completed = (await db.execute(
            select(func.count(func.distinct(ScheduledVisit.job_id)))
            .join(Job, ScheduledVisit.job_id == Job.id)
            .where(ScheduledVisit.technician_id == tech.id, ScheduledVisit.tenant_id == tid, Job.status == JobStatus.completed)
        )).scalar() or 0

        tech_scheduled = (await db.execute(
            select(func.count(func.distinct(ScheduledVisit.job_id)))
            .join(Job, ScheduledVisit.job_id == Job.id)
            .where(ScheduledVisit.technician_id == tech.id, ScheduledVisit.tenant_id == tid,
                   Job.status.in_([JobStatus.scheduled, JobStatus.in_progress]))
        )).scalar() or 0

        tech_total = tech_completed + tech_scheduled

        # Sum work hours + drive hours from route_visits
        rv_result = await db.execute(
            select(
                func.coalesce(func.sum(RouteVisit.estimated_work_hours), 0.0),
                func.coalesce(func.sum(RouteVisit.estimated_drive_minutes), 0.0),
            )
            .join(Route, RouteVisit.route_id == Route.id)
            .where(Route.technician_id == tech.id, Route.tenant_id == tid)
        )
        rv_row = rv_result.one()
        tech_work_hours = float(rv_row[0])
        tech_drive_minutes = float(rv_row[1])
        tech_drive_hours = round(tech_drive_minutes / 60.0, 1)

        tech_pct = round(tech_completed / tech_total * 100) if tech_total else 0
        share_pct = round(tech_total / total_jobs * 100) if total_jobs else 0

        tech_stats.append({
            "name": tech.name,
            "total": tech_total,
            "completed": tech_completed,
            "scheduled": tech_scheduled,
            "completed_pct": tech_pct,
            "share_pct": share_pct,
            "work_hours": round(tech_work_hours, 1),
            "drive_hours": tech_drive_hours,
        })

    # ── Calendar data: jobs per date for the selected region ──
    # Gather all scheduled_visits with route dates for region techs
    cal_data = {}
    if selected_region:
        cal_result = await db.execute(
            select(
                Route.route_date,
                Technician.name.label("tech_name"),
                func.count(RouteVisit.id).label("visit_count"),
                func.coalesce(func.sum(RouteVisit.estimated_work_hours), 0.0).label("work_h"),
                func.coalesce(func.sum(RouteVisit.estimated_drive_minutes), 0.0).label("drive_min"),
            )
            .join(Route, RouteVisit.route_id == Route.id)
            .join(Technician, Route.technician_id == Technician.id)
            .where(Route.tenant_id == tid, Route.region_id == selected_region.id)
            .group_by(Route.route_date, Technician.name)
            .order_by(Route.route_date)
        )
        for row in cal_result.all():
            dt_key = row.route_date.isoformat()
            if dt_key not in cal_data:
                cal_data[dt_key] = {"visits": 0, "work_h": 0.0, "drive_h": 0.0, "techs": []}
            cal_data[dt_key]["visits"] += row.visit_count
            cal_data[dt_key]["work_h"] += float(row.work_h)
            cal_data[dt_key]["drive_h"] += float(row.drive_min) / 60.0
            cal_data[dt_key]["techs"].append({
                "name": row.tech_name,
                "visits": row.visit_count,
                "hours": round(float(row.work_h) + float(row.drive_min) / 60.0, 1),
            })

    # ── Norwegian holidays ──
    holidays = {}
    for year in range(today.year, today.year + 2):
        for h in get_norwegian_holidays(year):
            holidays[h.isoformat()] = True

    import json

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "dashboard",
        "regions": regions,
        "selected_region": selected_region,
        "stats": {
            "total": total_jobs,
            "completed": completed,
            "completed_pct": pct,
            "scheduled": scheduled,
            "scheduled_pct": sched_pct,
            "unscheduled": unscheduled,
            "unscheduled_pct": unsched_pct,
            "total_hours": round(float(total_hours), 1),
        },
        "year_pct": year_pct,
        "status_klasse": status_klasse,
        "status_tekst": status_tekst,
        "tech_stats": tech_stats,
        "cal_data_json": json.dumps(cal_data),
        "holidays_json": json.dumps(holidays),
    })


@router.get("/dashboard/week-data")
async def dashboard_week_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    region_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """Return job visit data for a week, grouped by date."""
    user = await _get_user_from_cookie(request, db)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    tid = user.tenant_id

    if not region_id or not date_from or not date_to:
        return {"days": {}}

    rid = uuid.UUID(region_id)
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)

    # Query route_visits with joins to get all needed data
    result = await db.execute(
        select(
            Route.route_date,
            Technician.name.label("tech_name"),
            Job.id.label("job_id"),
            Job.title,
            Job.status,
            Job.external_id,
            Location.address,
            Location.postal_code,
            ServiceContract.sla_hours,
            RouteVisit.estimated_work_hours,
            RouteVisit.estimated_drive_minutes,
            RouteVisit.sequence_order,
            ScheduledVisit.scheduled_date,
            Job.updated_at.label("job_updated_at"),
        )
        .select_from(RouteVisit)
        .join(Route, RouteVisit.route_id == Route.id)
        .join(Technician, Route.technician_id == Technician.id)
        .join(ScheduledVisit, RouteVisit.scheduled_visit_id == ScheduledVisit.id)
        .join(Job, ScheduledVisit.job_id == Job.id)
        .join(ServiceContract, Job.service_contract_id == ServiceContract.id)
        .join(Location, ServiceContract.location_id == Location.id)
        .where(
            Route.tenant_id == tid,
            Route.region_id == rid,
            Route.route_date >= d_from,
            Route.route_date <= d_to,
        )
        .order_by(Route.route_date, RouteVisit.sequence_order)
    )

    rows = result.all()
    today_iso = date.today().isoformat()

    days: dict = {}
    for row in rows:
        dt_key = row.route_date.isoformat()
        if dt_key not in days:
            days[dt_key] = {"jobs": [], "techs": {}}

        # Determine status label
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        is_delayed = (
            status_val == "scheduled"
            and row.route_date.isoformat() < today_iso
        )

        days[dt_key]["jobs"].append({
            "id": str(row.job_id),
            "title": row.title,
            "external_id": row.external_id,
            "address": row.address,
            "postal_code": row.postal_code,
            "status": status_val,
            "is_delayed": is_delayed,
            "technician": row.tech_name,
            "sla_hours": float(row.sla_hours) if row.sla_hours else 0,
            "work_hours": float(row.estimated_work_hours) if row.estimated_work_hours else 0,
            "drive_minutes": int(row.estimated_drive_minutes) if row.estimated_drive_minutes else 0,
            "scheduled_date": row.route_date.isoformat(),
            "updated_at": row.job_updated_at.isoformat() if row.job_updated_at else None,
        })

        # Accumulate per-tech hours
        tech = row.tech_name
        if tech not in days[dt_key]["techs"]:
            days[dt_key]["techs"][tech] = {"work_h": 0.0, "drive_h": 0.0, "visits": 0}
        days[dt_key]["techs"][tech]["work_h"] += float(row.estimated_work_hours) if row.estimated_work_hours else 0
        days[dt_key]["techs"][tech]["drive_h"] += (float(row.estimated_drive_minutes) / 60.0) if row.estimated_drive_minutes else 0
        days[dt_key]["techs"][tech]["visits"] += 1

    return {"days": days}


@router.get("/customers", response_class=HTMLResponse)
async def customers_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    from app.services.customer_service import CustomerService

    service = CustomerService(db)
    customers, total = await service.list_customers(user.tenant_id, page=1, page_size=20)

    return templates.TemplateResponse("customers/list.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
        "customers": customers,
        "total": total,
        "page": 1,
        "page_size": 20,
        "search": "",
    })


@router.get("/customers/table", response_class=HTMLResponse)
async def customers_table(
    request: Request,
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return HTMLResponse(status_code=401, content="Unauthorized")

    from app.services.customer_service import CustomerService

    service = CustomerService(db)
    customers, total = await service.list_customers(
        user.tenant_id, search=search, page=page, page_size=page_size
    )

    return templates.TemplateResponse("customers/_table.html", {
        "request": request,
        "user": user,
        "customers": customers,
        "total": total,
        "page": page,
        "page_size": page_size,
        "search": search or "",
    })


# ── Regions ──────────────────────────────────────────────────────────────


@router.get("/regions", response_class=HTMLResponse)
async def regions_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    from app.services.region_service import RegionService

    service = RegionService(db)
    regions, total = await service.list_regions(user.tenant_id, page=1, page_size=20)

    return templates.TemplateResponse("regions/list.html", {
        "request": request,
        "user": user,
        "active_page": "regions",
        "regions": regions,
        "total": total,
        "page": 1,
        "page_size": 20,
    })


@router.get("/regions/table", response_class=HTMLResponse)
async def regions_table(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return HTMLResponse(status_code=401, content="Unauthorized")

    from app.services.region_service import RegionService

    service = RegionService(db)
    regions, total = await service.list_regions(user.tenant_id, page=page, page_size=page_size)

    return templates.TemplateResponse("regions/_table.html", {
        "request": request,
        "user": user,
        "regions": regions,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


# ── Technicians ──────────────────────────────────────────────────────────


@router.get("/technicians", response_class=HTMLResponse)
async def technicians_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    from app.services.region_service import RegionService
    from app.services.technician_service import TechnicianService

    region_service = RegionService(db)
    regions, _ = await region_service.list_regions(user.tenant_id, page=1, page_size=100)

    tech_service = TechnicianService(db)
    technicians, total = await tech_service.list_technicians(user.tenant_id, page=1, page_size=20)

    region_map = {r.id: r.name for r in regions}

    return templates.TemplateResponse("technicians/list.html", {
        "request": request,
        "user": user,
        "active_page": "technicians",
        "regions": regions,
        "technicians": technicians,
        "region_map": region_map,
        "total": total,
        "page": 1,
        "page_size": 20,
        "region_id": "",
    })


@router.get("/technicians/table", response_class=HTMLResponse)
async def technicians_table(
    request: Request,
    db: AsyncSession = Depends(get_db),
    region_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return HTMLResponse(status_code=401, content="Unauthorized")

    from app.services.region_service import RegionService
    from app.services.technician_service import TechnicianService

    rid = uuid.UUID(region_id) if region_id else None

    tech_service = TechnicianService(db)
    technicians, total = await tech_service.list_technicians(
        user.tenant_id, region_id=rid, page=page, page_size=page_size
    )

    region_service = RegionService(db)
    regions, _ = await region_service.list_regions(user.tenant_id, page=1, page_size=100)
    region_map = {r.id: r.name for r in regions}

    return templates.TemplateResponse("technicians/_table.html", {
        "request": request,
        "user": user,
        "technicians": technicians,
        "region_map": region_map,
        "total": total,
        "page": page,
        "page_size": page_size,
        "region_id": region_id or "",
    })


# ── Jobs ─────────────────────────────────────────────────────────────────


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    region_id: str | None = Query(None),
    search: str | None = Query(None),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    from app.services.job_service import JobService

    tid = user.tenant_id

    # Load regions
    result = await db.execute(
        select(Region).where(Region.tenant_id == tid).order_by(Region.name)
    )
    regions = list(result.scalars().all())
    selected_region = None
    if regions:
        if region_id:
            selected_region = next((r for r in regions if str(r.id) == region_id), regions[0])
        else:
            selected_region = regions[0]

    # Job stats (tenant-wide)
    status_counts = {}
    for s in [JobStatus.unscheduled, JobStatus.scheduled, JobStatus.in_progress, JobStatus.completed, JobStatus.cancelled]:
        count = (await db.execute(
            select(func.count(Job.id)).where(Job.tenant_id == tid, Job.status == s)
        )).scalar() or 0
        status_counts[s.value] = count

    service = JobService(db)
    rid = uuid.UUID(region_id) if region_id else (selected_region.id if selected_region else None)
    jobs, total = await service.list_jobs(
        tid, status=status, search=search, region_id=rid, page=1, page_size=20
    )

    return templates.TemplateResponse("jobs/list.html", {
        "request": request,
        "user": user,
        "active_page": "jobs",
        "regions": regions,
        "selected_region": selected_region,
        "stats": {
            "total": sum(status_counts.values()),
            "completed": status_counts["completed"],
            "unscheduled": status_counts["unscheduled"],
        },
        "jobs": jobs,
        "total": total,
        "page": 1,
        "page_size": 20,
        "status_filter": status or "",
        "search": search or "",
        "sort_by": "created_at",
        "sort_order": "asc",
        "region_id": str(selected_region.id) if selected_region else "",
    })


@router.get("/jobs/table", response_class=HTMLResponse)
async def jobs_table(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    search: str | None = Query(None),
    region_id: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return HTMLResponse(status_code=401, content="Unauthorized")

    from app.services.job_service import JobService

    rid = uuid.UUID(region_id) if region_id else None
    service = JobService(db)
    jobs, total = await service.list_jobs(
        user.tenant_id, status=status, search=search, region_id=rid,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
    )

    return templates.TemplateResponse("jobs/_table.html", {
        "request": request,
        "user": user,
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_filter": status or "",
        "search": search or "",
        "sort_by": sort_by,
        "sort_order": sort_order,
        "region_id": region_id or "",
    })


# ── Routes ──────────────────────────────────────────────────────────────


@router.get("/routes", response_class=HTMLResponse)
async def routes_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    region_id: str | None = Query(None),
):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    tid = user.tenant_id

    # Load regions
    result = await db.execute(
        select(Region).where(Region.tenant_id == tid).order_by(Region.name)
    )
    regions = list(result.scalars().all())
    selected_region = None
    if regions:
        if region_id:
            selected_region = next((r for r in regions if str(r.id) == region_id), regions[0])
        else:
            selected_region = regions[0]

    # Pre-load routes for ALL regions (enables instant region switching)
    all_routes_by_region: dict[str, dict] = {}
    if regions:
        from app.services.route_service import RouteService

        route_svc = RouteService(db, user_id=user.id)
        for region in regions:
            rid = str(region.id)
            items, total = await route_svc.list_routes(
                tid, region_id=region.id, page=1, page_size=500,
            )
            all_routes_by_region[rid] = {
                "items": [
                    {
                        "id": str(item.id),
                        "route_date": item.route_date.isoformat(),
                        "technician_id": str(item.technician_id),
                        "technician_name": item.technician_name,
                        "status": item.status,
                        "visit_count": item.visit_count,
                        "total_hours": item.total_hours,
                    }
                    for item in items
                ],
                "total": total,
            }

    return templates.TemplateResponse("routes/dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "routes",
        "regions": regions,
        "selected_region": selected_region,
        "start_date": "2027-01-01",
        "end_date": "2027-12-31",
        "all_routes_json": json.dumps(all_routes_by_region),
    })


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    from app.services.job_service import JobService

    service = JobService(db)
    job = await service.get_job(job_id, user.tenant_id)

    return templates.TemplateResponse("jobs/detail.html", {
        "request": request,
        "user": user,
        "active_page": "jobs",
        "job": job,
    })
