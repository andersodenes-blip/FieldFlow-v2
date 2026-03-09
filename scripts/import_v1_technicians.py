# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Import technicians from FieldFlow v1 CSV files."""
import asyncio
import csv
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

# V1 CSV files mapped to region names
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
CSV_FILES = [
    (DATA_ROOT / "oslo" / "teknikere.csv", "Oslo"),
    (DATA_ROOT / "bergen" / "teknikere.csv", "Bergen"),
    (DATA_ROOT / "stavanger" / "teknikere.csv", "Stavanger"),
]


async def import_technicians():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # 1. Find tenant
        result = await db.execute(
            text("SELECT id FROM tenants WHERE slug = 'hedengren'")
        )
        tenant_id = result.scalar_one_or_none()
        if not tenant_id:
            print("Tenant 'hedengren' not found. Run seed.py first.")
            await engine.dispose()
            return

        print(f"Tenant: hedengren (id: {tenant_id})")

        # 2. Set RLS context
        await db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))

        # 3. Load regions
        result = await db.execute(
            text("SELECT id, name FROM regions WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        region_map = {row.name: row.id for row in result.fetchall()}
        print(f"Regioner i DB: {list(region_map.keys())}")

        # 4. Load existing technician names to avoid duplicates
        result = await db.execute(
            text("SELECT name FROM technicians WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        existing_names = {row.name for row in result.fetchall()}

        # 5. Import from each CSV
        total_imported = 0
        total_skipped = 0

        for csv_path, region_name in CSV_FILES:
            if not csv_path.exists():
                print(f"\n  MANGLER: {csv_path}")
                continue

            region_id = region_map.get(region_name)
            if not region_id:
                print(f"\n  Region '{region_name}' finnes ikke i DB — hopper over")
                continue

            print(f"\n  {region_name} ({csv_path.name}):")

            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row["navn"].strip()
                    if name in existing_names:
                        print(f"    HOPPER OVER (finnes): {name}")
                        total_skipped += 1
                        continue

                    is_active = row.get("aktiv", "").strip().lower() == "ja"

                    tech = Technician(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        region_id=region_id,
                        name=name,
                        email=f"{name.lower().replace(' ', '.')}@hedengren.no",
                        phone="",
                        is_active=is_active,
                    )
                    db.add(tech)
                    existing_names.add(name)
                    total_imported += 1
                    print(f"    IMPORTERT: {name} (aktiv={is_active})")

        await db.commit()

        print(f"\nFerdig! Importert: {total_imported}, hoppet over: {total_skipped}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_technicians())
