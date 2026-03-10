# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Update seed technicians with real names and home coordinates."""
import asyncio
from pathlib import Path

import asyncpg

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"

# Map old name → (new name, email, lat, lon, region)
UPDATES = [
    ("Tekniker 3", "Ardian Lomesi", "ardian.lomesi@hedengren.no", 60.3158, 5.3457, "Bergen"),
    ("Tekniker 4", "John Eirik Duley Sande", "john.sande@hedengren.no", 60.4603, 5.3329, "Bergen"),
    ("Tekniker 1", "Eric Grønneberg", "eric.gronneberg@hedengren.no", 60.0148, 11.0476, "Oslo"),
    ("Tekniker 2", "Johnny Andresen", "johnny.andresen@hedengren.no", 59.4643, 10.6941, "Oslo"),
    ("Tekniker 5", "Helge Bratland", "helge.bratland@hedengren.no", 58.8636, 5.7430, "Stavanger"),
    ("Tekniker 6", "Gunnar Sunde", "gunnar.sunde@hedengren.no", 58.9750, 5.6550, "Stavanger"),
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
        for old_name, new_name, email, lat, lon, region in UPDATES:
            result = await conn.execute("""
                UPDATE technicians
                SET name = $1, email = $2, home_latitude = $3, home_longitude = $4
                WHERE name = $5 AND tenant_id = $6
            """, new_name, email, lat, lon, old_name, TENANT_ID)
            count = int(result.split()[-1])
            if count > 0:
                print(f"  {old_name:15s} → {new_name:25s} | {lat:.4f}, {lon:.4f} | {region}")
            else:
                print(f"  {old_name}: IKKE FUNNET")

        # Verify
        print("\n=== Alle teknikere ===")
        techs = await conn.fetch("""
            SELECT t.name, r.name as region, t.home_latitude, t.home_longitude
            FROM technicians t
            JOIN regions r ON t.region_id = r.id
            WHERE t.tenant_id = $1
            ORDER BY r.name, t.name
        """, TENANT_ID)
        for t in techs:
            lat = f"{t['home_latitude']:.4f}" if t['home_latitude'] else "NULL"
            lon = f"{t['home_longitude']:.4f}" if t['home_longitude'] else "NULL"
            print(f"  {t['region']:15s} | {t['name']:25s} | {lat}, {lon}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
