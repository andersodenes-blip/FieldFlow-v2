# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import time
from typing import Any

import httpx
from jose import jwt

from app.config import settings

# Cache JWKS keys in memory with TTL
_jwks_cache: dict[str, Any] = {}
_jwks_cache_ttl: float = 0
JWKS_CACHE_SECONDS = 3600


async def get_jwks() -> dict[str, Any]:
    """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
    global _jwks_cache, _jwks_cache_ttl

    if _jwks_cache and time.time() < _jwks_cache_ttl:
        return _jwks_cache

    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_ttl = time.time() + JWKS_CACHE_SECONDS
        return _jwks_cache


def _get_signing_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    """Find the signing key matching the JWT kid header."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_auth0_token(token: str) -> dict[str, Any]:
    """Verify an Auth0-issued JWT and return the decoded payload.

    Validates:
    - RS256 signature against Auth0 JWKS
    - Issuer matches Auth0 domain
    - Audience matches configured audience
    - Token is not expired
    - org_id claim is present (Auth0 Organizations)
    """
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing kid header")

    jwks = await get_jwks()
    signing_key = _get_signing_key(jwks, kid)
    if not signing_key:
        raise ValueError("Unable to find matching signing key")

    payload = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.AUTH0_AUDIENCE,
        issuer=f"https://{settings.AUTH0_DOMAIN}/",
    )

    if not payload.get("org_id"):
        raise ValueError("Token missing org_id claim")

    return payload


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchange an authorization code for Auth0 tokens."""
    token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            json={
                "grant_type": "authorization_code",
                "client_id": settings.AUTH0_CLIENT_ID,
                "client_secret": settings.AUTH0_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.AUTH0_CALLBACK_URL,
            },
        )
        response.raise_for_status()
        return response.json()


def build_authorize_url(state: str | None = None) -> str:
    """Build the Auth0 authorization URL for login."""
    params = {
        "response_type": "code",
        "client_id": settings.AUTH0_CLIENT_ID,
        "redirect_uri": settings.AUTH0_CALLBACK_URL,
        "scope": "openid profile email",
        "audience": settings.AUTH0_AUDIENCE,
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://{settings.AUTH0_DOMAIN}/authorize?{query}"
