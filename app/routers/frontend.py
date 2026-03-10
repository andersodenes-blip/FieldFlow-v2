# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.region import Region
from app.models.technician import Technician
from app.models.user import User
from app.repositories.user_repository import UserRepository

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

    # Determine selected region (default to first)
    selected_region = None
    if regions:
        if region_id:
            selected_region = next((r for r in regions if str(r.id) == region_id), regions[0])
        else:
            selected_region = regions[0]

    # Job counts by status (tenant-wide)
    status_counts = {}
    for s in [JobStatus.unscheduled, JobStatus.scheduled, JobStatus.in_progress, JobStatus.completed, JobStatus.cancelled]:
        count = (await db.execute(
            select(func.count(Job.id)).where(Job.tenant_id == tid, Job.status == s)
        )).scalar() or 0
        status_counts[s.value] = count

    total_jobs = sum(status_counts.values())
    completed = status_counts["completed"]
    pct = round(completed / total_jobs * 100) if total_jobs else 0

    if pct >= 70:
        pct_label = "God"
    elif pct >= 40:
        pct_label = "OK"
    else:
        pct_label = "På etterskudd"

    # Technicians filtered by selected region
    tech_query = (
        select(Technician, Region.name.label("region_name"))
        .join(Region, Technician.region_id == Region.id)
        .where(Technician.tenant_id == tid, Technician.is_active == True)
    )
    if selected_region:
        tech_query = tech_query.where(Technician.region_id == selected_region.id)
    tech_query = tech_query.order_by(Technician.name)

    result = await db.execute(tech_query)
    technicians = [{"tech": row.Technician, "region_name": row.region_name} for row in result.all()]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "dashboard",
        "regions": regions,
        "selected_region": selected_region,
        "stats": {
            "total": total_jobs,
            "completed": completed,
            "scheduled": status_counts["scheduled"] + status_counts["in_progress"],
            "unscheduled": status_counts["unscheduled"],
        },
        "pct": pct,
        "pct_label": pct_label,
        "technicians": technicians,
    })


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
