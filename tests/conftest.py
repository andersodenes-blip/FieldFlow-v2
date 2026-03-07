# Copyright (c) 2026 Anders Ødenes. All rights reserved.
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.auth_service import hash_password

TEST_DB_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db):
    from app.dependencies import get_db
    from app.main import app

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant_a(db):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A", slug="tenant-a", settings={})
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def tenant_b(db):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant B", slug="tenant-b", settings={})
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def user_a(db, tenant_a):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="user@tenant-a.no",
        hashed_password=hash_password("password123"),
        role=UserRole.owner,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db, tenant_b):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="user@tenant-b.no",
        hashed_password=hash_password("password456"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
