# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_has_status_and_db_fields(client):
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "db" in data
    assert data["status"] == "ok"
    assert data["db"] == "connected"
