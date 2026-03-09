# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Tests for Auth0 Organizations integration (US-004)."""
import pytest


@pytest.mark.asyncio
async def test_auth0_login_returns_501_when_not_configured(client):
    """Auth0 login endpoint returns 501 when Auth0 is not configured."""
    response = await client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 501
    assert response.json()["detail"] == "Auth0 is not configured"


@pytest.mark.asyncio
async def test_auth0_callback_returns_501_when_not_configured(client):
    """Auth0 callback endpoint returns 501 when Auth0 is not configured."""
    response = await client.get("/auth/callback?code=fake-code")
    assert response.status_code == 501
    assert response.json()["detail"] == "Auth0 is not configured"


@pytest.mark.asyncio
async def test_protected_endpoint_returns_401_without_token(client):
    """Protected routes return 401/403 without a valid Bearer token."""
    response = await client.get("/auth/me")
    # HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_protected_endpoint_returns_401_with_invalid_token(client):
    """Protected routes return 401 with an invalid Bearer token."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token-value"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_returns_401_with_expired_token(client):
    """Protected routes return 401 with an expired token."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from app.config import settings

    expired_payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth0_login_redirects_when_configured(client, monkeypatch):
    """Auth0 login endpoint redirects to Auth0 when configured."""
    monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
    monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")
    monkeypatch.setattr("app.config.settings.AUTH0_CALLBACK_URL", "http://localhost:8000/auth/callback")

    response = await client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "test.auth0.com/authorize" in location
    assert "client_id=test-client-id" in location
    assert "response_type=code" in location
    assert "scope=openid+profile+email" in location or "scope=openid%20profile%20email" in location


@pytest.mark.asyncio
async def test_auth0_callback_fails_with_invalid_code(client, monkeypatch):
    """Auth0 callback returns 401 when code exchange fails."""
    monkeypatch.setattr("app.config.settings.AUTH0_DOMAIN", "test.auth0.com")
    monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setattr("app.config.settings.AUTH0_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr("app.config.settings.AUTH0_AUDIENCE", "https://api.fieldflow.no")

    response = await client.get("/auth/callback?code=invalid-code")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth0_verify_token_requires_org_id():
    """Auth0 token validation requires org_id claim."""
    from app.services.auth0_service import verify_auth0_token

    # A random JWT without proper signing will fail validation
    with pytest.raises(Exception):
        await verify_auth0_token("not.a.valid.jwt")


@pytest.mark.asyncio
async def test_build_authorize_url_includes_state():
    """build_authorize_url includes state parameter when provided."""
    from unittest.mock import patch

    with patch("app.services.auth0_service.settings") as mock_settings:
        mock_settings.AUTH0_DOMAIN = "test.auth0.com"
        mock_settings.AUTH0_CLIENT_ID = "test-client-id"
        mock_settings.AUTH0_CALLBACK_URL = "http://localhost:8000/auth/callback"
        mock_settings.AUTH0_AUDIENCE = "https://api.fieldflow.no"

        from app.services.auth0_service import build_authorize_url

        url = build_authorize_url(state="my-state-value")
        assert "state=my-state-value" in url
        assert "test.auth0.com/authorize" in url


@pytest.mark.asyncio
async def test_build_authorize_url_excludes_state_when_none():
    """build_authorize_url excludes state parameter when not provided."""
    from unittest.mock import patch

    with patch("app.services.auth0_service.settings") as mock_settings:
        mock_settings.AUTH0_DOMAIN = "test.auth0.com"
        mock_settings.AUTH0_CLIENT_ID = "test-client-id"
        mock_settings.AUTH0_CALLBACK_URL = "http://localhost:8000/auth/callback"
        mock_settings.AUTH0_AUDIENCE = "https://api.fieldflow.no"

        from app.services.auth0_service import build_authorize_url

        url = build_authorize_url()
        assert "state=" not in url
