# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Remove placeholder seed technicians from the database."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

SEED_NAMES = [
    "Tekniker 1", "Tekniker 2", "Tekniker 3",
    "Tekniker 4", "Tekniker 5", "Tekniker 6",
]


async def cleanup():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # Find tenant
        result = await db.execute(
            text("SELECT id FROM tenants WHERE slug = 'hedengren'")
        )
        tenant_id = result.scalar_one_or_none()
        if not tenant_id:
            print("Tenant 'hedengren' not found.")
            await engine.dispose()
            return

        # Set RLS context
        await db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))

        # Delete seed technicians
        result = await db.execute(
            text(
                "DELETE FROM technicians WHERE tenant_id = :tid AND name = ANY(:names) RETURNING name"
            ),
            {"tid": tenant_id, "names": SEED_NAMES},
        )
        deleted = [row.name for row in result.fetchall()]
        await db.commit()

        if deleted:
            print(f"Slettet {len(deleted)} seed-teknikere:")
            for name in deleted:
                print(f"  - {name}")
        else:
            print("Ingen seed-teknikere funnet.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(cleanup())
