# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Check next_due_date distribution for jobs per region."""
import asyncio
import sys
from pathlib import Path

import asyncpg

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"


async def get_db_url() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )
    raise RuntimeError("DATABASE_URL not found in .env")


async def main():
    conn = await asyncpg.connect(await get_db_url(), statement_cache_size=0)
    try:
        # Per region: next_due_date distribution
        regions = await conn.fetch(
            "SELECT id, name FROM regions WHERE tenant_id = $1 ORDER BY name",
            TENANT_ID,
        )
        for region in regions:
            print(f"\n=== {region['name']} ===")
            rows = await conn.fetch("""
                SELECT DATE_TRUNC('month', sc.next_due_date)::date as month,
                       COUNT(*) as cnt
                FROM jobs j
                JOIN service_contracts sc ON j.service_contract_id = sc.id
                JOIN locations l ON sc.location_id = l.id
                WHERE j.tenant_id = $1
                  AND l.city = $2
                  AND j.status = 'unscheduled'
                GROUP BY month
                ORDER BY month
            """, TENANT_ID, region['name'])
            total = 0
            for r in rows:
                m = r['month'].strftime('%Y-%m') if r['month'] else 'NULL'
                print(f"  {m}: {r['cnt']} jobber")
                total += r['cnt']
            print(f"  Totalt: {total}")

        # Also check sla_hours for Stavanger
        print(f"\n=== Stavanger sla_hours ===")
        rows = await conn.fetch("""
            SELECT sc.sla_hours, COUNT(*) as cnt
            FROM jobs j
            JOIN service_contracts sc ON j.service_contract_id = sc.id
            JOIN locations l ON sc.location_id = l.id
            WHERE j.tenant_id = $1 AND l.city = 'Stavanger' AND j.status = 'unscheduled'
            GROUP BY sc.sla_hours ORDER BY sc.sla_hours
        """, TENANT_ID)
        for r in rows:
            print(f"  {r['sla_hours'] or 'NULL':>5} → {r['cnt']} jobber")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
