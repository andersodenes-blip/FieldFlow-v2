# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.customer import Customer
from app.models.location import Location
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_location(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        f"/customers/{customer.id}/locations",
        json={
            "address": "Storgata 1",
            "city": "Oslo",
            "postal_code": "0001",
            "latitude": 59.911,
            "longitude": 10.752,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["address"] == "Storgata 1"
    assert data["customer_id"] == str(customer.id)


@pytest.mark.asyncio
async def test_create_location_invalid_customer(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        f"/customers/{uuid.uuid4()}/locations",
        json={"address": "Test", "city": "Oslo", "postal_code": "0001"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_locations_for_customer(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    db.add(Location(tenant_id=tenant_a.id, customer_id=customer.id, address="A1", city="Oslo", postal_code="0001"))
    db.add(Location(tenant_id=tenant_a.id, customer_id=customer.id, address="A2", city="Bergen", postal_code="5001"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/customers/{customer.id}/locations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_location(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    loc = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Storgata 1", city="Oslo", postal_code="0001",
    )
    db.add(loc)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/locations/{loc.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["address"] == "Storgata 1"


@pytest.mark.asyncio
async def test_update_location(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    loc = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Gammel", city="Oslo", postal_code="0001",
    )
    db.add(loc)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.put(
        f"/locations/{loc.id}",
        json={"address": "Ny Adresse 5", "latitude": 60.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["address"] == "Ny Adresse 5"
    assert resp.json()["latitude"] == 60.0


@pytest.mark.asyncio
async def test_delete_location(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    loc = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Sletbar", city="Oslo", postal_code="0001",
    )
    db.add(loc)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(
        f"/locations/{loc.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cross_tenant_isolation_locations(client, db, user_a, user_b, tenant_a, tenant_b):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Acme")
    db.add(customer)
    await db.commit()

    loc = Location(
        id=uuid.uuid4(), tenant_id=tenant_a.id, customer_id=customer.id,
        address="Secret", city="Oslo", postal_code="0001",
    )
    db.add(loc)
    await db.commit()

    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(
        f"/locations/{loc.id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
