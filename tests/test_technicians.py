# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.region import Region
from app.models.technician import Technician
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_technician(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    db.add(region)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/technicians",
        json={
            "region_id": str(region.id),
            "name": "Ola Nordmann",
            "email": "ola@test.no",
            "phone": "12345678",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Ola Nordmann"
    assert data["region_id"] == str(region.id)
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_technician_invalid_region(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/technicians",
        json={
            "region_id": str(uuid.uuid4()),
            "name": "Test",
            "email": "test@test.no",
            "phone": "000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_technicians(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    db.add(region)
    await db.commit()

    db.add(Technician(tenant_id=tenant_a.id, region_id=region.id, name="T1", email="t1@t.no", phone="1"))
    db.add(Technician(tenant_id=tenant_a.id, region_id=region.id, name="T2", email="t2@t.no", phone="2"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get("/technicians", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_filter_technicians_by_region(client, db, user_a, tenant_a):
    r1 = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    r2 = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Bergen", city="Bergen")
    db.add_all([r1, r2])
    await db.commit()

    db.add(Technician(tenant_id=tenant_a.id, region_id=r1.id, name="T1", email="t1@t.no", phone="1"))
    db.add(Technician(tenant_id=tenant_a.id, region_id=r2.id, name="T2", email="t2@t.no", phone="2"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        f"/technicians?region_id={r1.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    results = resp.json()["items"]
    assert len(results) == 1
    assert results[0]["name"] == "T1"


@pytest.mark.asyncio
async def test_soft_delete_technician(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    db.add(region)
    await db.commit()

    tech = Technician(
        id=uuid.uuid4(), tenant_id=tenant_a.id, region_id=region.id,
        name="Sletbar", email="s@t.no", phone="1",
    )
    db.add(tech)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(
        f"/technicians/{tech.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_cross_tenant_isolation_technicians(client, db, user_a, user_b, tenant_a, tenant_b):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Oslo", city="Oslo")
    db.add(region)
    await db.commit()

    tech = Technician(
        id=uuid.uuid4(), tenant_id=tenant_a.id, region_id=region.id,
        name="Secret", email="s@t.no", phone="1",
    )
    db.add(tech)
    await db.commit()

    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(
        f"/technicians/{tech.id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    resp = await client.get("/technicians", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp.json()["items"]) == 0
