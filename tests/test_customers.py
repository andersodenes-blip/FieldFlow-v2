# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.customer import Customer
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_customer(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/customers",
        json={"name": "Acme AS", "org_number": "123456789", "contact_email": "post@acme.no"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme AS"
    assert data["org_number"] == "123456789"
    assert data["tenant_id"] == str(tenant_a.id)


@pytest.mark.asyncio
async def test_list_customers(client, db, user_a, tenant_a):
    db.add(Customer(tenant_id=tenant_a.id, name="Kunde 1"))
    db.add(Customer(tenant_id=tenant_a.id, name="Kunde 2"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get("/customers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_search_customers(client, db, user_a, tenant_a):
    db.add(Customer(tenant_id=tenant_a.id, name="Acme AS"))
    db.add(Customer(tenant_id=tenant_a.id, name="Globex Corp"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/customers?search=Acme", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["name"] == "Acme AS"


@pytest.mark.asyncio
async def test_pagination_customers(client, db, user_a, tenant_a):
    for i in range(5):
        db.add(Customer(tenant_id=tenant_a.id, name=f"Kunde {i}"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/customers?page=1&page_size=2", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_customer_with_location_count(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Test Kunde")
    db.add(customer)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/customers/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["location_count"] == 0


@pytest.mark.asyncio
async def test_update_customer(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Gammel Navn")
    db.add(customer)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.put(
        f"/customers/{customer.id}",
        json={"name": "Nytt Navn"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nytt Navn"


@pytest.mark.asyncio
async def test_delete_customer(client, db, user_a, tenant_a):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Sletbar")
    db.add(customer)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(
        f"/customers/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cross_tenant_isolation_customers(client, db, user_a, user_b, tenant_a, tenant_b):
    customer = Customer(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Tenant A Kunde")
    db.add(customer)
    await db.commit()

    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(
        f"/customers/{customer.id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    resp = await client.get("/customers", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp.json()) == 0
