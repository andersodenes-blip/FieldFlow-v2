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


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        role = payload.get("role")
        if user_id is None or tenant_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Set tenant context for RLS (PostgreSQL only)
    if db.bind.dialect.name != "sqlite":
        await db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(user.tenant_id)})

    return user


async def get_current_tenant(request: Request, user=Depends(get_current_user)):
    request.state.tenant_id = user.tenant_id
    return user.tenant_id
