# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

import pytest

from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.location import Location
from app.models.region import Region
from app.models.service_contract import ServiceContract
from app.models.technician import Technician
from app.services.auth_service import create_access_token
from app.services.route_planning_service import (
    JobWithCoords,
    get_norwegian_holidays,
    haversine_km,
    nearest_neighbor_order,
)


# --- Unit tests for pure functions ---


def test_haversine_oslo_bergen():
    """Oslo (59.91, 10.75) to Bergen (60.39, 5.32) ~305 km."""
    dist = haversine_km(59.91, 10.75, 60.39, 5.32)
    assert 300 < dist < 310


def test_haversine_same_point():
    assert haversine_km(59.91, 10.75, 59.91, 10.75) == 0.0


def test_nearest_neighbor_basic():
    jobs = [
        JobWithCoords(uuid.uuid4(), "A", "Addr A", 59.90, 10.70, 4.0),
        JobWithCoords(uuid.uuid4(), "B", "Addr B", 59.95, 10.80, 4.0),
        JobWithCoords(uuid.uuid4(), "C", "Addr C", 59.92, 10.72, 4.0),
    ]
    ordered = nearest_neighbor_order(jobs, 59.91, 10.71)
    # First should be A or C (closest to start), not B
    assert ordered[0].title in ("A", "C")
    assert len(ordered) == 3


def test_nearest_neighbor_empty():
    assert nearest_neighbor_order([], 59.91, 10.75) == []


def test_norwegian_holidays_2027():
    holidays = get_norwegian_holidays(2027)
    # Fixed holidays
    assert date(2027, 1, 1) in holidays      # Nyttarsdag
    assert date(2027, 5, 1) in holidays      # Arbeidernes dag
    assert date(2027, 5, 17) in holidays     # Grunnlovsdag
    assert date(2027, 12, 25) in holidays    # 1. juledag
    assert date(2027, 12, 26) in holidays    # 2. juledag
    # Easter 2027 is March 28
    assert date(2027, 3, 25) in holidays     # Skjaertorsdag
    assert date(2027, 3, 26) in holidays     # Langfredag
    assert date(2027, 3, 28) in holidays     # 1. paskedag
    assert date(2027, 3, 29) in holidays     # 2. paskedag
    # Ascension = Easter + 39 = May 6
    assert date(2027, 5, 6) in holidays      # Kristi himmelfartsdag
    # Whit Sunday = Easter + 49 = May 16
    assert date(2027, 5, 16) in holidays     # 1. pinsedag
    assert date(2027, 5, 17) in holidays     # 2. pinsedag (= Grunnlovsdag)
    # 2. pinsedag (May 17) overlaps with Grunnlovsdag, so 11 unique dates
    assert len(holidays) == 11


# --- Integration tests via API ---


async def _setup_region_with_jobs(db, tenant, num_jobs=4):
    """Create region, technicians, and unscheduled jobs with coordinates."""
    region = Region(id=uuid.uuid4(), tenant_id=tenant.id, name="Oslo", city="Oslo")
    db.add(region)

    tech1 = Technician(
        id=uuid.uuid4(), tenant_id=tenant.id, region_id=region.id,
        name="Ola Nordmann", email="ola@test.no", phone="12345678",
        home_latitude=59.91, home_longitude=10.75,
    )
    tech2 = Technician(
        id=uuid.uuid4(), tenant_id=tenant.id, region_id=region.id,
        name="Kari Hansen", email="kari@test.no", phone="87654321",
        home_latitude=59.93, home_longitude=10.78,
    )
    db.add_all([tech1, tech2])

    customer = Customer(id=uuid.uuid4(), tenant_id=tenant.id, name="TestKunde")
    db.add(customer)
    await db.flush()

    jobs = []
    for i in range(num_jobs):
        loc = Location(
            id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
            address=f"Testgate {i+1}", city="Oslo", postal_code=f"0{i+1}01",
            latitude=59.90 + i * 0.01, longitude=10.70 + i * 0.02,
        )
        db.add(loc)
        await db.flush()

        contract = ServiceContract(
            id=uuid.uuid4(), tenant_id=tenant.id, location_id=loc.id,
            service_type="Vedlikehold", interval_months=12,
            next_due_date=date(2026, 6, 1),
        )
        db.add(contract)
        await db.flush()

        job = Job(
            id=uuid.uuid4(), tenant_id=tenant.id,
            service_contract_id=contract.id,
            title=f"Jobb {i+1}", status=JobStatus.unscheduled,
        )
        db.add(job)
        jobs.append(job)

    await db.commit()
    return region, [tech1, tech2], jobs


@pytest.mark.asyncio
async def test_plan_routes_api(client, db, user_a, tenant_a):
    region, techs, jobs = await _setup_region_with_jobs(db, tenant_a, num_jobs=4)

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["visits_assigned"] == 4
    assert data["routes_created"] > 0
    assert data["jobs_without_coords"] == 0


@pytest.mark.asyncio
async def test_plan_routes_no_technicians(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Tromsø", city="Tromsø")
    db.add(region)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["routes_created"] == 0
    assert "Ingen aktive teknikere" in data["capacity_warnings"][0]


@pytest.mark.asyncio
async def test_list_routes(client, db, user_a, tenant_a):
    region, techs, jobs = await _setup_region_with_jobs(db, tenant_a, num_jobs=2)

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # Plan first
    await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List routes
    resp = await client.get(
        "/routes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert len(data["items"]) > 0


@pytest.mark.asyncio
async def test_get_route_detail(client, db, user_a, tenant_a):
    region, techs, jobs = await _setup_region_with_jobs(db, tenant_a, num_jobs=2)

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # Plan first
    await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List and get first route
    list_resp = await client.get(
        "/routes",
        headers={"Authorization": f"Bearer {token}"},
    )
    route_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(
        f"/routes/{route_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "visits" in data
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_update_route_status(client, db, user_a, tenant_a):
    region, techs, jobs = await _setup_region_with_jobs(db, tenant_a, num_jobs=2)

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    list_resp = await client.get("/routes", headers={"Authorization": f"Bearer {token}"})
    route_id = list_resp.json()["items"][0]["id"]

    resp = await client.patch(
        f"/routes/{route_id}/status",
        json={"status": "published"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_jobs_without_coords(client, db, user_a, tenant_a):
    """Jobs without coordinates should be counted but not assigned."""
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    db.add(region)

    tech = Technician(
        id=uuid.uuid4(), tenant_id=tenant_a.id, region_id=region.id,
        name="Test Tech", email="test@test.no", phone="11111111",
    )
    db.add(tech)

    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Kunde")
    db.add(customer)
    await db.flush()

    # Location WITHOUT coordinates
    loc = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Ukjent gate 1", city="Oslo", postal_code="0100",
        latitude=None, longitude=None,
    )
    db.add(loc)
    await db.flush()

    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=loc.id,
        service_type="Service", interval_months=12,
        next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.flush()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id,
        service_contract_id=contract.id,
        title="Jobb uten koordinater", status=JobStatus.unscheduled,
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/routes/plan",
        json={
            "region_id": str(region.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-10",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jobs_without_coords"] == 1
    assert data["visits_assigned"] == 0
