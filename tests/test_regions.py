# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.region import Region
from app.models.technician import Technician
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_create_region(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.post(
        "/regions",
        json={"name": "Østlandet", "city": "Oslo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Østlandet"
    assert data["city"] == "Oslo"
    assert data["tenant_id"] == str(tenant_a.id)


@pytest.mark.asyncio
async def test_list_regions(client, db, user_a, tenant_a):
    db.add(Region(tenant_id=tenant_a.id, name="Region 1", city="Oslo"))
    db.add(Region(tenant_id=tenant_a.id, name="Region 2", city="Bergen"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get("/regions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_get_region(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Nord", city="Tromsø")
    db.add(region)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(f"/regions/{region.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nord"


@pytest.mark.asyncio
async def test_update_region(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Gammel", city="Oslo")
    db.add(region)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.put(
        f"/regions/{region.id}",
        json={"name": "Ny"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ny"
    assert resp.json()["city"] == "Oslo"


@pytest.mark.asyncio
async def test_delete_region(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Sletbar", city="Oslo")
    db.add(region)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(f"/regions/{region.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_region_with_technicians_fails(client, db, user_a, tenant_a):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Opptatt", city="Oslo")
    db.add(region)
    await db.commit()

    tech = Technician(
        tenant_id=tenant_a.id, region_id=region.id,
        name="Ola", email="ola@test.no", phone="12345678",
    )
    db.add(tech)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.delete(f"/regions/{region.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cross_tenant_isolation_regions(client, db, user_a, user_b, tenant_a, tenant_b):
    region = Region(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Tenant A Region", city="Oslo")
    db.add(region)
    await db.commit()

    # Tenant B cannot see Tenant A's region
    token_b = create_access_token(str(user_b.id), str(tenant_b.id), user_b.role.value)
    resp = await client.get(f"/regions/{region.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404

    # Tenant B's list doesn't include Tenant A's regions
    resp = await client.get("/regions", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0


@pytest.mark.asyncio
async def test_get_nonexistent_region_returns_404(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(f"/regions/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
