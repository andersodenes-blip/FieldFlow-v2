# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Tests for US-005: Auth0 Organizations — user/org mapping in database."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.services.auth_service import hash_password


@pytest_asyncio.fixture
async def org_a(db, tenant_a):
    org = Organization(
        id=uuid.uuid4(),
        auth0_org_id="org_hedengren_test",
        name="Hedengren Test",
        tenant_id=tenant_a.id,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest_asyncio.fixture
async def org_b(db, tenant_b):
    org = Organization(
        id=uuid.uuid4(),
        auth0_org_id="org_other_company",
        name="Other Company",
        tenant_id=tenant_b.id,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest_asyncio.fixture
async def auth0_user(db, tenant_a, org_a):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="auth0user@hedengren.no",
        auth0_user_id="auth0|abc123",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestOrganizationModel:
    @pytest.mark.asyncio
    async def test_create_organization(self, db, tenant_a):
        org = Organization(
            id=uuid.uuid4(),
            auth0_org_id="org_test_123",
            name="Test Org",
            tenant_id=tenant_a.id,
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)

        assert org.auth0_org_id == "org_test_123"
        assert org.name == "Test Org"
        assert org.tenant_id == tenant_a.id
        assert org.created_at is not None

    @pytest.mark.asyncio
    async def test_organization_linked_to_tenant(self, db, org_a, tenant_a):
        assert org_a.tenant_id == tenant_a.id


class TestOrganizationRepository:
    @pytest.mark.asyncio
    async def test_get_by_auth0_org_id(self, db, org_a):
        from app.repositories.organization_repository import OrganizationRepository

        repo = OrganizationRepository(db)
        found = await repo.get_by_auth0_org_id("org_hedengren_test")
        assert found is not None
        assert found.id == org_a.id

    @pytest.mark.asyncio
    async def test_get_by_auth0_org_id_not_found(self, db):
        from app.repositories.organization_repository import OrganizationRepository

        repo = OrganizationRepository(db)
        found = await repo.get_by_auth0_org_id("org_nonexistent")
        assert found is None


class TestUserAuth0Fields:
    @pytest.mark.asyncio
    async def test_user_with_auth0_user_id(self, db, auth0_user):
        assert auth0_user.auth0_user_id == "auth0|abc123"
        assert auth0_user.hashed_password is None

    @pytest.mark.asyncio
    async def test_user_without_auth0_user_id(self, db, user_a):
        assert user_a.auth0_user_id is None
        assert user_a.hashed_password is not None

    @pytest.mark.asyncio
    async def test_get_user_by_auth0_user_id(self, db, auth0_user):
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        found = await repo.get_by_auth0_user_id("auth0|abc123")
        assert found is not None
        assert found.id == auth0_user.id

    @pytest.mark.asyncio
    async def test_get_user_by_auth0_user_id_not_found(self, db):
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        found = await repo.get_by_auth0_user_id("auth0|nonexistent")
        assert found is None


class TestAutoCreateUserOnAuth0Login:
    """Test that users are auto-created on first Auth0 login."""

    @pytest.mark.asyncio
    async def test_auto_create_user_on_first_login(self, client, db, org_a, monkeypatch):
        """First Auth0 login creates user automatically."""
        monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")

        mock_verify = AsyncMock(return_value={
            "sub": "auth0|newuser123",
            "org_id": "org_hedengren_test",
            "email": "newuser@hedengren.no",
        })
        monkeypatch.setattr("app.services.auth0_service.verify_auth0_token", mock_verify)

        # Use a fake Auth0 token (verification is mocked)
        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake-auth0-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@hedengren.no"
        assert data["auth0_user_id"] == "auth0|newuser123"
        assert data["role"] == "viewer"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_existing_user_linked_to_auth0(self, client, db, user_a, org_a, monkeypatch):
        """Existing user (by email) gets linked to Auth0 identity."""
        monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")

        mock_verify = AsyncMock(return_value={
            "sub": "auth0|linked456",
            "org_id": "org_hedengren_test",
            "email": "user@tenant-a.no",
        })
        monkeypatch.setattr("app.services.auth0_service.verify_auth0_token", mock_verify)

        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake-auth0-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@tenant-a.no"
        assert data["auth0_user_id"] == "auth0|linked456"

    @pytest.mark.asyncio
    async def test_auth0_login_unknown_org_returns_401(self, client, db, monkeypatch):
        """Auth0 login with unknown org_id returns 401."""
        monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")

        mock_verify = AsyncMock(return_value={
            "sub": "auth0|someone",
            "org_id": "org_unknown",
            "email": "someone@unknown.com",
        })
        monkeypatch.setattr("app.services.auth0_service.verify_auth0_token", mock_verify)

        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake-auth0-token"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Organization not found"


class TestMeEndpointWithOrganization:
    """Test that GET /me returns organization info."""

    @pytest.mark.asyncio
    async def test_me_returns_organization_for_auth0_user(self, client, db, auth0_user, org_a, monkeypatch):
        """GET /me includes organization for Auth0 users."""
        monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")

        mock_verify = AsyncMock(return_value={
            "sub": "auth0|abc123",
            "org_id": "org_hedengren_test",
            "email": "auth0user@hedengren.no",
        })
        monkeypatch.setattr("app.services.auth0_service.verify_auth0_token", mock_verify)

        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake-auth0-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization"] is not None
        assert data["organization"]["auth0_org_id"] == "org_hedengren_test"
        assert data["organization"]["name"] == "Hedengren Test"

    @pytest.mark.asyncio
    async def test_me_returns_null_organization_for_local_user(self, client, user_a):
        """GET /me returns null organization for local (non-Auth0) users."""
        login = await client.post(
            "/auth/token",
            json={"email": "user@tenant-a.no", "password": "password123"},
        )
        token = login.json()["access_token"]
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization"] is None
        assert data["auth0_user_id"] is None
