# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Check work hours data in the database."""
import asyncio
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
        # 1. Check if jobs has estimated_work_hours column
        col = await conn.fetchval("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'jobs' AND column_name = 'estimated_work_hours'
        """)
        if col:
            print("=== jobs.estimated_work_hours ===")
            rows = await conn.fetch(f"""
                SELECT estimated_work_hours, COUNT(*)
                FROM jobs WHERE tenant_id = $1
                GROUP BY estimated_work_hours ORDER BY count DESC
            """, TENANT_ID)
            for r in rows:
                print(f"  {r['estimated_work_hours']}\t→ {r['count']} jobber")
        else:
            print("jobs.estimated_work_hours: kolonnen finnes IKKE")

        # 2. Check sla_hours on service_contracts (what we actually use)
        print("\n=== service_contracts.sla_hours ===")
        rows = await conn.fetch("""
            SELECT sc.sla_hours, COUNT(*)
            FROM jobs j
            JOIN service_contracts sc ON j.service_contract_id = sc.id
            WHERE j.tenant_id = $1
            GROUP BY sc.sla_hours ORDER BY count DESC
        """, TENANT_ID)
        for r in rows:
            print(f"  {r['sla_hours']}\t→ {r['count']} jobber")

        # 3. Summary
        print("\n=== Oppsummering ===")
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE tenant_id = $1", TENANT_ID
        )
        unscheduled = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE tenant_id = $1 AND status = 'unscheduled'",
            TENANT_ID,
        )
        scheduled = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE tenant_id = $1 AND status = 'scheduled'",
            TENANT_ID,
        )
        print(f"  Totalt: {total} jobber")
        print(f"  Uplanlagte: {unscheduled}")
        print(f"  Planlagte: {scheduled}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
