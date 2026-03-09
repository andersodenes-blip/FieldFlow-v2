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
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    # Fetch stats
    regions_count = (await db.execute(
        select(func.count(Region.id)).where(Region.tenant_id == user.tenant_id)
    )).scalar() or 0

    technicians_count = (await db.execute(
        select(func.count(Technician.id)).where(Technician.tenant_id == user.tenant_id)
    )).scalar() or 0

    customers_count = (await db.execute(
        select(func.count(Customer.id)).where(Customer.tenant_id == user.tenant_id)
    )).scalar() or 0

    active_jobs_count = (await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == user.tenant_id,
            Job.status.in_([JobStatus.unscheduled, JobStatus.scheduled, JobStatus.in_progress]),
        )
    )).scalar() or 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "dashboard",
        "stats": {
            "regions": regions_count,
            "technicians": technicians_count,
            "customers": customers_count,
            "active_jobs": active_jobs_count,
        },
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
