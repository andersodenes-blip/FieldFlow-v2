# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest

from app.models.user import UserRole, User
from app.services.auth_service import create_access_token, hash_password


@pytest.mark.asyncio
async def test_audit_event_created_on_region_create(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # Create a region
    await client.post(
        "/regions",
        json={"name": "Test Region", "city": "Oslo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Check audit log
    resp = await client.get(
        "/audit-events?resource_type=region",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    events = data["items"]
    assert any(e["action"] == "create" and e["resource_type"] == "region" for e in events)


@pytest.mark.asyncio
async def test_audit_event_created_on_customer_update(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    # Create then update
    resp = await client.post(
        "/customers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    customer_id = resp.json()["id"]

    await client.put(
        f"/customers/{customer_id}",
        json={"name": "Acme Corp"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Check audit log
    resp = await client.get(
        "/audit-events?resource_type=customer",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    events = resp.json()["items"]
    actions = [e["action"] for e in events]
    assert "create" in actions
    assert "update" in actions


@pytest.mark.asyncio
async def test_audit_event_created_on_delete(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    resp = await client.post(
        "/regions",
        json={"name": "Deletable", "city": "Oslo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    region_id = resp.json()["id"]

    await client.delete(
        f"/regions/{region_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/audit-events?resource_type=region",
        headers={"Authorization": f"Bearer {token}"},
    )
    events = resp.json()["items"]
    actions = [e["action"] for e in events]
    assert "delete" in actions


@pytest.mark.asyncio
async def test_audit_events_filter_by_user(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    await client.post(
        "/regions",
        json={"name": "Test", "city": "Oslo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/audit-events?user_id={user_a.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_audit_events_requires_admin(client, db, tenant_a):
    # Create a viewer user
    viewer = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="viewer@test.no",
        hashed_password=hash_password("pass"),
        role=UserRole.viewer,
        is_active=True,
    )
    db.add(viewer)
    await db.commit()

    token = create_access_token(str(viewer.id), str(tenant_a.id), viewer.role.value)
    resp = await client.get(
        "/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
