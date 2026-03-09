# Copyright (c) 2026 Anders Ødenes. All rights reserved.
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import admin, auth, customers, health, jobs, locations, regions, service_contracts, technicians


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_sqlite:
        from app.dependencies import engine
        from app.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="FieldFlow v2", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(regions.router)
app.include_router(customers.router)
app.include_router(technicians.router)
app.include_router(locations.router)
app.include_router(service_contracts.router)
app.include_router(jobs.router)
