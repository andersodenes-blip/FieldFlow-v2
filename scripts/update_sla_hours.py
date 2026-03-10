# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Update service_contracts.sla_hours based on price from Master.xlsx.

Rules:
- Stavanger:
    price < 7000    → 3.0 hours
    7000-15000      → 6.0 hours
    price > 15000   → round_up(price / 140, nearest 0.5)
- All other regions:
    round_up(price / 140, nearest 0.5)

Minimum: 0.5 hours
"""
import asyncio
import math
import sys
from collections import defaultdict
from pathlib import Path

import asyncpg
import openpyxl

MASTER_FILE = Path(__file__).resolve().parent.parent / "data" / "Master.xlsx"
SHEET_NAME = "Årskontroller Hedengren Master"
COL_TICKET = 3
COL_REGION = 7
COL_PRICE = 8


def round_up_half(value: float) -> float:
    """Round up to nearest 0.5."""
    return math.ceil(value * 2) / 2


def calc_sla_hours(price: float, region: str) -> float:
    """Calculate sla_hours from price and region.

    Formula: round_up(cost / 2 / 1450, nearest 0.5)
    Stavanger exceptions: <7000 → 3.0t, 7000-15000 → 6.0t
    """
    if price is None or price <= 0:
        return 1.0

    if region and region.lower() == "stavanger":
        if price < 7000:
            return 3.0
        elif price <= 15000:
            return 6.0
        else:
            return max(0.5, round_up_half(price / 2 / 1450))
    else:
        return max(0.5, round_up_half(price / 2 / 1450))


async def get_db_url() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )
    raise RuntimeError("DATABASE_URL not found in .env")


async def main():
    dry_run = "--dry-run" in sys.argv

    # 1. Read Master.xlsx
    print(f"Leser {MASTER_FILE}...")
    wb = openpyxl.load_workbook(str(MASTER_FILE), read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    ticket_data: dict[str, tuple[float, str]] = {}  # ticket_number → (price, region)
    skipped = 0
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        ticket = row[COL_TICKET]
        region = row[COL_REGION]
        price = row[COL_PRICE]

        if not ticket:
            skipped += 1
            continue
        if price is None:
            skipped += 1
            continue

        try:
            price_val = float(price)
        except (ValueError, TypeError):
            skipped += 1
            continue

        ticket_data[str(ticket).strip()] = (price_val, str(region or "").strip())

    wb.close()
    print(f"  Lest {len(ticket_data)} tickets med pris ({skipped} hoppet over)")

    # 2. Calculate sla_hours
    hours_map: dict[str, float] = {}
    for ticket, (price, region) in ticket_data.items():
        hours_map[ticket] = calc_sla_hours(price, region)

    # Stats
    hour_dist: dict[float, int] = defaultdict(int)
    for h in hours_map.values():
        hour_dist[h] += 1

    print(f"\n  Fordeling av beregnede timer:")
    for h in sorted(hour_dist.keys()):
        print(f"    {h:5.1f}t → {hour_dist[h]:4d} jobber")

    # Region breakdown
    region_stats: dict[str, list[float]] = defaultdict(list)
    for ticket, (price, region) in ticket_data.items():
        region_stats[region].append(hours_map[ticket])

    print(f"\n  Per region:")
    for region in sorted(region_stats.keys()):
        hours = region_stats[region]
        avg = sum(hours) / len(hours)
        print(f"    {region:15s}: {len(hours):4d} jobber, snitt {avg:.1f}t, min {min(hours):.1f}t, maks {max(hours):.1f}t")

    if dry_run:
        print("\n  --dry-run: ingen databaseoppdatering")
        return

    # 3. Update database
    print(f"\nKobler til database...")
    conn = await asyncpg.connect(await get_db_url(), statement_cache_size=0)
    try:
        updated = 0
        not_found = 0
        tickets = list(hours_map.keys())

        # Batch: find jobs by external_id, get their service_contract_id
        for ticket, sla_hours in hours_map.items():
            row = await conn.fetchrow("""
                SELECT j.service_contract_id
                FROM jobs j
                WHERE j.external_id = $1
                LIMIT 1
            """, ticket)

            if not row:
                not_found += 1
                continue

            await conn.execute("""
                UPDATE service_contracts
                SET sla_hours = $1
                WHERE id = $2
            """, int(math.ceil(sla_hours)), row["service_contract_id"])
            updated += 1

        print(f"\n  Oppdatert: {updated} service_contracts")
        print(f"  Ikke funnet i DB: {not_found} tickets")

        # Verify
        result = await conn.fetch("""
            SELECT sla_hours, COUNT(*) as cnt
            FROM service_contracts
            WHERE sla_hours IS NOT NULL
            GROUP BY sla_hours
            ORDER BY sla_hours
        """)
        print(f"\n  Verifisering — sla_hours i databasen:")
        for r in result:
            print(f"    {r['sla_hours']:3d}t → {r['cnt']:4d} kontrakter")

        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM service_contracts WHERE sla_hours IS NULL"
        )
        print(f"    NULL → {null_count:4d} kontrakter")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
