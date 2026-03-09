# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from datetime import date

import pytest

from app.models.customer import Customer
from app.models.location import Location
from app.models.service_contract import ServiceContract
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_service_contract(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Storgata 1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/service-contracts",
        json={
            "location_id": str(location.id),
            "service_type": "Vedlikehold",
            "interval_months": 6,
            "next_due_date": "2026-06-01",
            "sla_hours": 48,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_type"] == "Vedlikehold"
    assert data["interval_months"] == 6
    assert data["next_due_date"] == "2026-06-01"
    assert data["sla_hours"] == 48
    assert data["is_active"] is True
    assert data["location_id"] == str(location.id)


@pytest.mark.asyncio
async def test_create_contract_invalid_location(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/service-contracts",
        json={
            "location_id": str(uuid.uuid4()),
            "service_type": "Test",
            "interval_months": 3,
            "next_due_date": "2026-06-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_service_contracts(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    location = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    db.add(location)
    await db.commit()

    db.add(ServiceContract(
        tenant_id=tenant_a.id, location_id=location.id,
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    ))
    db.add(ServiceContract(
        tenant_id=tenant_a.id, location_id=location.id,
        service_type="Type B", interval_months=6, next_due_date=date(2026, 9, 1),
    ))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/service-contracts", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_list_contracts_filter_by_location(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    loc1 = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A1", city="Oslo", postal_code="0001",
    )
    loc2 = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="A2", city="Bergen", postal_code="5001",
    )
    db.add_all([loc1, loc2])
    await db.commit()

    db.add(ServiceContract(
        tenant_id=tenant_a.id, location_id=loc1.id,
        service_type="Type A", interval_months=3, next_due_date=date(2026, 6, 1),
    ))
    db.add(ServiceContract(
        tenant_id=tenant_a.id, location_id=loc2.id,
        service_type="Type B", interval_months=6, next_due_date=date(2026, 9, 1),
    ))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/service-contracts?location_id={loc1.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["service_type"] == "Type A"


@pytest.mark.asyncio
async def test_get_service_contract(client, db, user_a, tenant_a):
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
        service_type="Inspeksjon", interval_months=12, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/service-contracts/{contract.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["service_type"] == "Inspeksjon"


@pytest.mark.asyncio
async def test_update_service_contract(client, db, user_a, tenant_a):
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
        service_type="Gammel", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.put(
        f"/service-contracts/{contract.id}",
        json={"service_type": "Ny Type", "sla_hours": 24},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["service_type"] == "Ny Type"
    assert resp.json()["sla_hours"] == 24
    assert resp.json()["interval_months"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_delete_service_contract_soft_delete(client, db, user_a, tenant_a):
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
        service_type="Test", interval_months=6, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(
        f"/service-contracts/{contract.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify it's still there but deactivated
    resp = await client.get(
        f"/service-contracts/{contract.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_cross_tenant_isolation_contracts(client, db, user_a, user_b, tenant_a, tenant_b):
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
        service_type="Secret", interval_months=3, next_due_date=date(2026, 6, 1),
    )
    db.add(contract)
    await db.commit()

    # Tenant B cannot see Tenant A's contract
    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(
        f"/service-contracts/{contract.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404

    # Tenant B's list is empty
    resp = await client.get(
        "/service-contracts", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0
