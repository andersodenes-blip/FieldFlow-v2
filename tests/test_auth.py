# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import pytest


@pytest.mark.asyncio
async def test_login_valid_credentials(client, user_a):
    response = await client.post("/auth/token", json={"email": "user@tenant-a.no", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client, user_a):
    response = await client.post("/auth/token", json={"email": "user@tenant-a.no", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_me_without_token(client):
    response = await client.get("/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_with_valid_token(client, user_a):
    login = await client.post("/auth/token", json={"email": "user@tenant-a.no", "password": "password123"})
    token = login.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@tenant-a.no"
    assert data["role"] == "owner"
    assert data["is_active"] is True
    assert data["tenant_id"] == str(user_a.tenant_id)
