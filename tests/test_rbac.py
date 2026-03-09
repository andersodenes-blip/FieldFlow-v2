# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Tests for US-006: Role-Based Access Control (RBAC).

Covers:
- require_role dependency with org:admin / org:member
- Admin routes return 403 for org:member users
- Cross-org data isolation (tenant A cannot see tenant B data)
"""
import uuid

import pytest
import pytest_asyncio

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(db, tenant_a):
    """Admin user (org:admin mapped role) in tenant A."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="admin@tenant-a.no",
        hashed_password=hash_password("admin123"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_user(db, tenant_a):
    """Owner user (org:admin mapped role) in tenant A."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="owner@tenant-a.no",
        hashed_password=hash_password("owner123"),
        role=UserRole.owner,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db, tenant_a):
    """Viewer user (org:member mapped role) in tenant A."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="viewer@tenant-a.no",
        hashed_password=hash_password("viewer123"),
        role=UserRole.viewer,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def planner_user(db, tenant_a):
    """Planner user (org:member mapped role) in tenant A."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="planner@tenant-a.no",
        hashed_password=hash_password("planner123"),
        role=UserRole.planner,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def dispatcher_user(db, tenant_a):
    """Dispatcher user (org:member mapped role) in tenant A."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="dispatcher@tenant-a.no",
        hashed_password=hash_password("dispatcher123"),
        role=UserRole.dispatcher,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user_b(db, tenant_b):
    """Admin user in tenant B (for cross-org isolation tests)."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="admin@tenant-b.no",
        hashed_password=hash_password("adminb123"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _token_for(user: User) -> str:
    return create_access_token(str(user.id), str(user.tenant_id), user.role.value)


# ---------------------------------------------------------------------------
# Tests: require_role dependency
# ---------------------------------------------------------------------------

class TestRequireRole:
    """Test the require_role dependency with Auth0 role mapping."""

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_route(self, client, admin_user):
        token = _token_for(admin_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_can_access_admin_route(self, client, owner_user):
        token = _token_for(owner_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_access_admin_route(self, client, viewer_user):
        token = _token_for(viewer_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"

    @pytest.mark.asyncio
    async def test_planner_cannot_access_admin_route(self, client, planner_user):
        token = _token_for(planner_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_dispatcher_cannot_access_admin_route(self, client, dispatcher_user):
        token = _token_for(dispatcher_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_admin_route(self, client):
        response = await client.get("/admin/users")
        assert response.status_code == 403  # HTTPBearer returns 403 without credentials


# ---------------------------------------------------------------------------
# Tests: Admin users list endpoint returns correct data
# ---------------------------------------------------------------------------

class TestAdminUsersEndpoint:
    """Test GET /admin/users returns tenant-scoped user list."""

    @pytest.mark.asyncio
    async def test_admin_sees_own_tenant_users(self, client, admin_user, viewer_user):
        """Admin sees all users in their own tenant."""
        token = _token_for(admin_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        emails = {u["email"] for u in data}
        assert "admin@tenant-a.no" in emails
        assert "viewer@tenant-a.no" in emails

    @pytest.mark.asyncio
    async def test_admin_does_not_see_other_tenant_users(
        self, client, admin_user, admin_user_b
    ):
        """Admin in tenant A cannot see users from tenant B."""
        token = _token_for(admin_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        emails = {u["email"] for u in data}
        assert "admin@tenant-b.no" not in emails


# ---------------------------------------------------------------------------
# Tests: Cross-org data isolation
# ---------------------------------------------------------------------------

class TestCrossOrgIsolation:
    """Verify that users cannot access data from other organizations/tenants."""

    @pytest.mark.asyncio
    async def test_tenant_a_admin_cannot_see_tenant_b_users(
        self, client, admin_user, admin_user_b
    ):
        """Tenant A admin only sees tenant A users, not tenant B."""
        token_a = _token_for(admin_user)
        response_a = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response_a.status_code == 200
        tenant_ids_a = {u["tenant_id"] for u in response_a.json()}
        assert str(admin_user.tenant_id) in tenant_ids_a
        assert str(admin_user_b.tenant_id) not in tenant_ids_a

    @pytest.mark.asyncio
    async def test_tenant_b_admin_cannot_see_tenant_a_users(
        self, client, admin_user, admin_user_b
    ):
        """Tenant B admin only sees tenant B users, not tenant A."""
        token_b = _token_for(admin_user_b)
        response_b = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response_b.status_code == 200
        tenant_ids_b = {u["tenant_id"] for u in response_b.json()}
        assert str(admin_user_b.tenant_id) in tenant_ids_b
        assert str(admin_user.tenant_id) not in tenant_ids_b

    @pytest.mark.asyncio
    async def test_me_only_returns_own_user_data(self, client, admin_user, admin_user_b):
        """GET /me returns only the authenticated user's data."""
        token_a = _token_for(admin_user)
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@tenant-a.no"
        assert data["tenant_id"] == str(admin_user.tenant_id)

    @pytest.mark.asyncio
    async def test_viewer_cannot_list_users_cross_org(
        self, client, viewer_user, admin_user_b
    ):
        """Viewer in tenant A gets 403 on admin endpoint — cannot reach tenant B data."""
        token = _token_for(viewer_user)
        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
