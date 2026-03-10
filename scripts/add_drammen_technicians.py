# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Add Drammen technicians."""
import asyncio
import uuid
from pathlib import Path

import asyncpg

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"

TECHNICIANS = [
    ("Samuel Gonzales", "samuel.gonzales@hedengren.no", 59.8938, 9.9203),
    ("Waseem Ghannam", "waseem.ghannam@hedengren.no", 59.7799, 9.8993),
]


async def main():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    db_url = None
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )

    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        # Get Drammen region_id
        region_id = await conn.fetchval(
            "SELECT id FROM regions WHERE name = 'Drammen' AND tenant_id = $1", TENANT_ID
        )
        if not region_id:
            print("Region 'Drammen' ikke funnet!")
            return
        print(f"Region: Drammen ({region_id})")

        for name, email, lat, lon in TECHNICIANS:
            tech_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO technicians (id, tenant_id, region_id, name, email, phone, is_active, home_latitude, home_longitude, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8, NOW(), NOW())
            """, tech_id, TENANT_ID, region_id, name, email, "00000000", lat, lon)
            print(f"  {name:25s} | {lat:.4f}, {lon:.4f} | {tech_id}")

        # Verify all
        print("\n=== Alle teknikere ===")
        techs = await conn.fetch("""
            SELECT t.name, r.name as region, t.home_latitude, t.home_longitude
            FROM technicians t JOIN regions r ON t.region_id = r.id
            WHERE t.tenant_id = $1 ORDER BY r.name, t.name
        """, TENANT_ID)
        for t in techs:
            lat = f"{t['home_latitude']:.4f}" if t['home_latitude'] else "NULL"
            lon = f"{t['home_longitude']:.4f}" if t['home_longitude'] else "NULL"
            print(f"  {t['region']:15s} | {t['name']:25s} | {lat}, {lon}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
