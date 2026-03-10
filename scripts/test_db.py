# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Minimal DB connectivity test with asyncpg."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env", override=True)
DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

import asyncpg


async def test():
    print(f"Connecting to: {DATABASE_URL[:40]}...")
    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    try:
        # Test 1: SELECT 1
        row = await conn.fetchrow("SELECT 1 AS ok")
        print(f"1. SELECT 1 => {row['ok']} OK")

        # Test 2: Get tenant_id
        row = await conn.fetchrow("SELECT id FROM tenants WHERE slug = $1", "hedengren")
        if not row:
            print("2. Tenant 'hedengren' not found. Run seed.py first.")
            return
        tenant_id = row["id"]
        print(f"2. Tenant: {tenant_id} OK")

        # Test 3: Get a customer_id
        row = await conn.fetchrow("SELECT id FROM customers WHERE tenant_id = $1 LIMIT 1", tenant_id)
        if not row:
            print("3. No customers found. Run import or seed first.")
            return
        customer_id = row["id"]
        print(f"3. Customer: {customer_id} OK")

        # Test 4: INSERT into locations
        now = datetime.now(timezone.utc)
        loc_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO locations (id, tenant_id, customer_id, address, city, postal_code, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $7)",
            loc_id, tenant_id, customer_id, "Test adresse 123", "Oslo", "0001", now,
        )
        print(f"4. INSERT location {loc_id} OK")

        # Cleanup
        await conn.execute("DELETE FROM locations WHERE id = $1", loc_id)
        print("5. DELETE cleanup OK")

        print("\nAlle tester bestått!")
    except Exception as e:
        print(f"\nFEIL: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(test())
