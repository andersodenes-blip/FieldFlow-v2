# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.region import Region
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_paginated_response_format(client, db, user_a, tenant_a):
    for i in range(5):
        db.add(Region(tenant_id=tenant_a.id, name=f"Region {i}", city="Oslo"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_pagination_second_page(client, db, user_a, tenant_a):
    for i in range(5):
        db.add(Region(tenant_id=tenant_a.id, name=f"Region {i}", city="Oslo"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?page=2&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_pagination_last_page(client, db, user_a, tenant_a):
    for i in range(5):
        db.add(Region(tenant_id=tenant_a.id, name=f"Region {i}", city="Oslo"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?page=3&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_pagination_empty_results(client, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_sorting_asc(client, db, user_a, tenant_a):
    db.add(Region(tenant_id=tenant_a.id, name="Bravo", city="Oslo"))
    db.add(Region(tenant_id=tenant_a.id, name="Alpha", city="Bergen"))
    db.add(Region(tenant_id=tenant_a.id, name="Charlie", city="Stavanger"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?sort_by=name&sort_order=asc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["items"]]
    assert names == ["Alpha", "Bravo", "Charlie"]


@pytest.mark.asyncio
async def test_sorting_desc(client, db, user_a, tenant_a):
    db.add(Region(tenant_id=tenant_a.id, name="Bravo", city="Oslo"))
    db.add(Region(tenant_id=tenant_a.id, name="Alpha", city="Bergen"))
    db.add(Region(tenant_id=tenant_a.id, name="Charlie", city="Stavanger"))
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)
    resp = await client.get(
        "/regions?sort_by=name&sort_order=desc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["items"]]
    assert names == ["Charlie", "Bravo", "Alpha"]


@pytest.mark.asyncio
async def test_all_endpoints_return_paginated(client, db, user_a, tenant_a):
    """Verify that all list endpoints return the PaginatedResponse format."""
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    endpoints = [
        "/regions",
        "/technicians",
        "/customers",
        "/service-contracts",
        "/jobs",
    ]

    for endpoint in endpoints:
        resp = await client.get(
            endpoint, headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Failed for {endpoint}"
        data = resp.json()
        assert "items" in data, f"Missing 'items' in {endpoint}"
        assert "total" in data, f"Missing 'total' in {endpoint}"
        assert "page" in data, f"Missing 'page' in {endpoint}"
        assert "page_size" in data, f"Missing 'page_size' in {endpoint}"
