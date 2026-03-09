# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date, timedelta

import pytest

from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.location import Location
from app.models.service_contract import ServiceContract
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_generate_jobs_basic(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    # Contract due in 10 days (within default 30-day horizon)
    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=location.id,
        service_type="Vedlikehold", interval_months=6,
        next_due_date=date.today() + timedelta(days=10),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs/generate",
        json={"horizon_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_count"] == 1
    assert len(data["job_ids"]) == 1


@pytest.mark.asyncio
async def test_generate_jobs_outside_horizon(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    # Contract due in 60 days (outside 30-day horizon)
    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=location.id,
        service_type="Vedlikehold", interval_months=6,
        next_due_date=date.today() + timedelta(days=60),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs/generate",
        json={"horizon_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["generated_count"] == 0


@pytest.mark.asyncio
async def test_generate_jobs_duplicate_check(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=location.id,
        service_type="Vedlikehold", interval_months=6,
        next_due_date=date.today() + timedelta(days=10),
    )
    db.add(contract)
    await db.commit()

    # Already has an unscheduled job for this contract
    db.add(Job(
        tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Existing", status=JobStatus.unscheduled,
    ))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs/generate",
        json={"horizon_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["generated_count"] == 0


@pytest.mark.asyncio
async def test_generate_jobs_updates_next_due_date(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    original_due = date.today() + timedelta(days=5)
    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=location.id,
        service_type="Vedlikehold", interval_months=3,
        next_due_date=original_due,
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    await client.post(
        "/jobs/generate",
        json={"horizon_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Check that next_due_date was advanced by interval_months
    resp = await client.get(
        f"/service-contracts/{contract.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    # Should be ~3 months later
    new_due = date.fromisoformat(resp.json()["next_due_date"])
    assert new_due > original_due
    # Roughly 3 months difference (allow for month-length variation)
    diff_days = (new_due - original_due).days
    assert 85 <= diff_days <= 95


@pytest.mark.asyncio
async def test_generate_jobs_skips_inactive_contracts(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    # Inactive contract due within horizon
    contract = ServiceContract(
        id=uuid.uuid4(), tenant_id=tenant_a.id, location_id=location.id,
        service_type="Vedlikehold", interval_months=6,
        next_due_date=date.today() + timedelta(days=5),
        is_active=False,
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs/generate",
        json={"horizon_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["generated_count"] == 0
