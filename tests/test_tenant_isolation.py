# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import pytest


@pytest.mark.asyncio
async def test_tenant_a_gets_own_data(client, user_a, tenant_a):
    login = await client.post("/auth/token", json={"email": "user@tenant-a.no", "password": "password123"})
    token = login.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(tenant_a.id)
    assert data["email"] == "user@tenant-a.no"


@pytest.mark.asyncio
async def test_tenant_b_gets_own_data(client, user_b, tenant_b):
    login = await client.post("/auth/token", json={"email": "user@tenant-b.no", "password": "password456"})
    token = login.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(tenant_b.id)
    assert data["email"] == "user@tenant-b.no"


@pytest.mark.asyncio
async def test_tenant_a_cannot_use_tenant_b_token(client, user_a, user_b):
    login_b = await client.post("/auth/token", json={"email": "user@tenant-b.no", "password": "password456"})
    token_b = login_b.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    data = response.json()
    # Token from tenant B must return tenant B data, not tenant A
    assert data["tenant_id"] != str(user_a.tenant_id)
    assert data["tenant_id"] == str(user_b.tenant_id)


@pytest.mark.asyncio
async def test_cross_tenant_login_fails(client, user_a, user_b):
    # Tenant A password should not work for tenant B email
    response = await client.post("/auth/token", json={"email": "user@tenant-b.no", "password": "password123"})
    assert response.status_code == 401
