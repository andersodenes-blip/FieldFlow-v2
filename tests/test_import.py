# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import io
import uuid

import pytest

from app.models.customer import Customer
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_import_valid_csv(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    csv_content = (
        "customer_name,org_number,contact_email,address,city,postal_code\n"
        "Acme AS,123456789,acme@test.no,Storgata 1,Oslo,0001\n"
        "Beta AS,987654321,beta@test.no,Lillegata 2,Bergen,5001\n"
    )

    resp = await client.post(
        "/import/customers",
        files={"file": ("customers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["row_count"] == 2
    assert data["error_log"]["created"] == 2
    assert data["error_log"]["errors"] == []


@pytest.mark.asyncio
async def test_import_validation_errors(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    csv_content = (
        "customer_name,org_number,contact_email,address,city,postal_code\n"
        ",,,,,\n"  # All fields empty
    )

    resp = await client.post(
        "/import/customers",
        files={"file": ("customers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert len(data["error_log"]["errors"]) > 0


@pytest.mark.asyncio
async def test_import_missing_columns(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    csv_content = "name,email\nAcme,acme@test.no\n"

    resp = await client.post(
        "/import/customers",
        files={"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_import_duplicate_handling(client, db, user_a, tenant_a):
    # Pre-create a customer with org_number
    existing = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Old Name",
        org_number="111222333",
        contact_email="old@test.no",
    )
    db.add(existing)
    await db.commit()

    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    csv_content = (
        "customer_name,org_number,contact_email,address,city,postal_code\n"
        "New Name,111222333,new@test.no,Storgata 1,Oslo,0001\n"
    )

    resp = await client.post(
        "/import/customers",
        files={"file": ("customers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["error_log"]["updated"] == 1
    assert data["error_log"]["created"] == 0


@pytest.mark.asyncio
async def test_get_import_status(client, db, user_a, tenant_a):
    token = create_access_token(str(user_a.id), str(tenant_a.id), user_a.role.value)

    csv_content = (
        "customer_name,org_number,contact_email,address,city,postal_code\n"
        "Acme AS,123,acme@test.no,Gata 1,Oslo,0001\n"
    )

    resp = await client.post(
        "/import/customers",
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    import_id = resp.json()["id"]

    # Get import status
    resp = await client.get(
        f"/import/{import_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
