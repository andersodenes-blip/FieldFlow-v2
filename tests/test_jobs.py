# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

import pytest

from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.location import Location
from app.models.service_contract import ServiceContract
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_job(client, db, user_a, tenant_a):
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
        service_type="Vedlikehold", interval_months=6, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs",
        json={
            "service_contract_id": str(contract.id),
            "title": "Service Acme",
            "description": "Utfør vedlikehold",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Service Acme"
    assert data["status"] == "unscheduled"
    assert data["service_contract_id"] == str(contract.id)


@pytest.mark.asyncio
async def test_create_job_invalid_contract(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/jobs",
        json={
            "service_contract_id": str(uuid.uuid4()),
            "title": "Test",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    db.add(Job(tenant_id=tenant_a.id, service_contract_id=contract.id, title="Job 1"))
    db.add(Job(tenant_id=tenant_a.id, service_contract_id=contract.id, title="Job 2"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    db.add(Job(tenant_id=tenant_a.id, service_contract_id=contract.id, title="Job 1", status=JobStatus.unscheduled))
    db.add(Job(tenant_id=tenant_a.id, service_contract_id=contract.id, title="Job 2", status=JobStatus.completed))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/jobs?status=unscheduled", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["status"] == "unscheduled"


@pytest.mark.asyncio
async def test_get_job(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Test Job",
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/jobs/{job.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Job"


@pytest.mark.asyncio
async def test_update_job(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Gammel Tittel",
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.put(
        f"/jobs/{job.id}",
        json={"title": "Ny Tittel", "description": "Oppdatert beskrivelse"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Ny Tittel"
    assert resp.json()["description"] == "Oppdatert beskrivelse"


@pytest.mark.asyncio
async def test_status_transition_valid(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Test", status=JobStatus.unscheduled,
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # unscheduled -> scheduled
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "scheduled"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "scheduled"

    # scheduled -> in_progress
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # in_progress -> completed
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_status_transition_invalid(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Test", status=JobStatus.unscheduled,
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # unscheduled -> completed (invalid)
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409

    # unscheduled -> in_progress (invalid)
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_status_transition_to_cancelled(client, db, user_a, tenant_a):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Test", status=JobStatus.scheduled,
    )
    db.add(job)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # Any status -> cancelled is allowed
    resp = await client.patch(
        f"/jobs/{job.id}/status",
        json={"status": "cancelled"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_jobs(client, db, user_a, user_b, tenant_a, tenant_b):
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
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    job = Job(
        id=uuid.uuid4(), tenant_id=tenant_a.id, service_contract_id=contract.id,
        title="Secret Job",
    )
    db.add(job)
    await db.commit()

    # Tenant B cannot see Tenant A's job
    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(
        f"/jobs/{job.id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    # Tenant B's list is empty
    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0
