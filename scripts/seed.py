"""Seed script for initial test data."""
import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base
from app.models.region import Region
from app.models.technician import Technician
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.auth_service import hash_password


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # Check if tenant already exists
        result = await db.execute(text("SELECT id FROM tenants WHERE slug = 'hedengren'"))
        if result.scalar_one_or_none():
            print("Seed data already exists, skipping.")
            await engine.dispose()
            return

        # Create tenant
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id,
            name="Hedengren Norge",
            slug="hedengren",
            plan="free",
            is_active=True,
            settings={},
        )
        db.add(tenant)

        # Create admin user
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="admin@hedengren.no",
            hashed_password=hash_password("admin123"),
            role=UserRole.owner,
            is_active=True,
        )
        db.add(user)

        # Create regions
        regions_data = [
            {"name": "Oslo", "city": "Oslo"},
            {"name": "Bergen", "city": "Bergen"},
            {"name": "Stavanger", "city": "Stavanger"},
        ]
        regions = []
        for r in regions_data:
            region = Region(id=uuid.uuid4(), tenant_id=tenant_id, name=r["name"], city=r["city"])
            db.add(region)
            regions.append(region)

        # Create 2 technicians per region
        tech_counter = 1
        for region in regions:
            for i in range(1, 3):
                tech = Technician(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    region_id=region.id,
                    name=f"Tekniker {tech_counter}",
                    email=f"tech{tech_counter}@hedengren.no",
                    phone=f"+47 900 00 {tech_counter:03d}",
                    is_active=True,
                )
                db.add(tech)
                tech_counter += 1

        await db.commit()
        print("Seed data created successfully!")
        print(f"  Tenant: {tenant.name} (id: {tenant.id})")
        print(f"  Admin: admin@hedengren.no / admin123")
        print(f"  Regions: Oslo, Bergen, Stavanger")
        print(f"  Technicians: 6 (2 per region)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
