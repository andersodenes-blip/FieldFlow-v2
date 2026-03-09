# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine_kwargs = {}
if settings.is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0}

engine = create_async_engine(settings.DATABASE_URL, echo=False, **_engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False)

security = HTTPBearer()


async def get_db():
    async with async_session() as session:
        yield session


async def _decode_local_token(token: str) -> dict:
    """Decode a locally-issued HS256 JWT token."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if user_id is None or tenant_id is None:
        raise ValueError("Missing required claims")
    return {"user_id": user_id, "tenant_id": tenant_id, "role": payload.get("role")}


async def _decode_auth0_token(token: str) -> dict:
    """Decode an Auth0-issued RS256 JWT token with org_id validation."""
    from app.services.auth0_service import verify_auth0_token

    payload = await verify_auth0_token(token)
    return {
        "sub": payload.get("sub"),
        "org_id": payload.get("org_id"),
        "email": payload.get("email") or payload.get(f"https://{settings.AUTH0_DOMAIN}/email"),
    }


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = credentials.credentials

    # Try local HS256 token first
    try:
        claims = await _decode_local_token(token)
    except (JWTError, ValueError):
        claims = None

    if claims:
        # Local token path — look up user by ID
        from app.repositories.user_repository import UserRepository

        repo = UserRepository(db)
        user = await repo.get_by_id(uuid.UUID(claims["user_id"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Set tenant context for RLS (PostgreSQL only)
        if db.bind.dialect.name != "sqlite":
            await db.execute(text(f"SET LOCAL app.current_tenant = '{user.tenant_id}'"))

        return user

    # Try Auth0 RS256 token if Auth0 is configured
    if settings.auth0_enabled:
        try:
            auth0_claims = await _decode_auth0_token(token)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        auth0_sub = auth0_claims.get("sub")
        auth0_org_id = auth0_claims.get("org_id")
        email = auth0_claims.get("email")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")
        if not auth0_org_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing org_id claim")

        from app.repositories.organization_repository import OrganizationRepository
        from app.repositories.user_repository import UserRepository

        org_repo = OrganizationRepository(db)
        org = await org_repo.get_by_auth0_org_id(auth0_org_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Organization not found")

        repo = UserRepository(db)
        # Look up user by Auth0 sub, then fall back to email
        user = None
        if auth0_sub:
            user = await repo.get_by_auth0_user_id(auth0_sub)
        if user is None:
            user = await repo.get_by_email(email)

        if user is None:
            # Auto-create user on first Auth0 login
            from app.models.user import User, UserRole

            user = User(
                tenant_id=org.tenant_id,
                email=email,
                auth0_user_id=auth0_sub,
                role=UserRole.viewer,
                is_active=True,
            )
            user = await repo.create(user)
        elif user.auth0_user_id is None and auth0_sub:
            # Link existing user to Auth0 identity
            user.auth0_user_id = auth0_sub
            await db.commit()
            await db.refresh(user)

        # Set tenant context for RLS (PostgreSQL only)
        if db.bind.dialect.name != "sqlite":
            await db.execute(text(f"SET LOCAL app.current_tenant = '{user.tenant_id}'"))

        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_tenant(request: Request, user=Depends(get_current_user)):
    request.state.tenant_id = user.tenant_id
    return user.tenant_id


def require_role(*allowed_roles: str):
    """FastAPI dependency that restricts access to users with specific roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("org:admin"))])
        async def admin_endpoint(...): ...

    Role mapping:
        Auth0 roles (org:admin, org:member) map to internal UserRole values.
        Internal roles (owner, admin, planner, dispatcher, viewer) are also accepted.
    """
    # Map Auth0 role names to internal role names
    _AUTH0_ROLE_MAP = {
        "org:admin": {"owner", "admin"},
        "org:member": {"planner", "dispatcher", "viewer"},
    }

    # Expand Auth0 roles to internal roles
    resolved: set[str] = set()
    for role in allowed_roles:
        if role in _AUTH0_ROLE_MAP:
            resolved.update(_AUTH0_ROLE_MAP[role])
        else:
            resolved.add(role)

    async def _check_role(
        current_user: Annotated["User", Depends(get_current_user)],
    ):
        if current_user.role.value not in resolved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return Depends(_check_role)
