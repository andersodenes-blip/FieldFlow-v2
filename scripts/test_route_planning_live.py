# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Plan routes for all regions for 2027 and verify capacity limits."""
import asyncio
import os
import sys
import uuid
from datetime import date
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Set DATABASE_URL from .env before importing app modules
env_path = project_root / ".env"
for line in env_path.read_text().splitlines():
    if line.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")

import asyncpg
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.route_planning_service import RoutePlanningService

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"
REGIONS = ["Stavanger", "Oslo", "Bergen", "Drammen", "Innlandet", "Østfold"]
START_DATE = date(2027, 1, 1)
END_DATE = date(2027, 12, 31)


async def get_asyncpg_url() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")


async def main():
    asyncpg_url = await get_asyncpg_url()
    print("Kobler til database...")
    conn = await asyncpg.connect(asyncpg_url, statement_cache_size=0)

    # Run migration: add start_date column if not exists
    try:
        await conn.execute("""
            ALTER TABLE technicians ADD COLUMN IF NOT EXISTS start_date DATE
        """)
        print("  start_date-kolonne OK")
    except Exception as e:
        print(f"  start_date-kolonne: {e}")

    # Set Truls Iversen start_date to 2027-05-01
    truls_result = await conn.execute("""
        UPDATE technicians SET start_date = '2027-05-01'
        WHERE name = 'Truls Iversen' AND tenant_id = $1
    """, TENANT_ID)
    print(f"  Truls Iversen start_date satt: {truls_result}")

    # Get region IDs
    rows = await conn.fetch(
        "SELECT id, name FROM regions WHERE tenant_id = $1 ORDER BY name", TENANT_ID
    )
    region_map = {r["name"]: r["id"] for r in rows}

    # Global cleanup
    print("\n=== Rydder opp ===")
    rv_del = await conn.fetchval("SELECT COUNT(*) FROM route_visits WHERE tenant_id = $1", TENANT_ID)
    sv_del = await conn.fetchval("SELECT COUNT(*) FROM scheduled_visits WHERE tenant_id = $1", TENANT_ID)
    rt_del = await conn.fetchval("SELECT COUNT(*) FROM routes WHERE tenant_id = $1", TENANT_ID)
    if rt_del > 0:
        await conn.execute("DELETE FROM route_visits WHERE tenant_id = $1", TENANT_ID)
        await conn.execute("DELETE FROM scheduled_visits WHERE tenant_id = $1", TENANT_ID)
        await conn.execute("DELETE FROM routes WHERE tenant_id = $1", TENANT_ID)
        print(f"  Slettet: {rt_del} ruter, {sv_del} scheduled_visits, {rv_del} route_visits")
    reset_result = await conn.execute("""
        UPDATE jobs SET status = 'unscheduled'
        WHERE tenant_id = $1 AND status = 'scheduled'
    """, TENANT_ID)
    reset_n = int(reset_result.split()[-1])
    print(f"  Resatt {reset_n} jobber til 'unscheduled'")

    # Pre-check: jobs and techs per region
    print(f"\n=== Utgangspunkt ===")
    for name in REGIONS:
        job_count = await conn.fetchval("""
            SELECT COUNT(*) FROM jobs j
            JOIN service_contracts sc ON j.service_contract_id = sc.id
            JOIN locations l ON sc.location_id = l.id
            WHERE j.status = 'unscheduled' AND l.city = $1 AND j.tenant_id = $2
        """, name, TENANT_ID)
        tech_count = await conn.fetchval("""
            SELECT COUNT(*) FROM technicians t
            JOIN regions r ON t.region_id = r.id
            WHERE r.name = $1 AND t.is_active = true AND t.tenant_id = $2
        """, name, TENANT_ID)
        print(f"  {name:15s}: {job_count:4d} jobber, {tech_count} teknikere")

    await conn.close()

    # Plan each region
    engine = create_async_engine(
        os.environ["DATABASE_URL"], echo=False,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    summary = []
    print(f"\n{'='*60}")
    print(f"RUTEPLANLEGGING {START_DATE} -> {END_DATE}")
    print(f"{'='*60}")

    for name in REGIONS:
        region_id = region_map.get(name)
        if not region_id:
            print(f"\n{name}: Region ikke funnet -- hopper over")
            continue

        print(f"\n--- {name} ---")
        async with session_factory() as session:
            service = RoutePlanningService(session)
            result = await service.plan_routes(
                uuid.UUID(TENANT_ID), region_id, START_DATE, END_DATE,
            )

        print(f"  Ruter opprettet:    {result['routes_created']}")
        print(f"  Besok fordelt:      {result['visits_assigned']}")
        print(f"  Uten koordinater:   {result['jobs_without_coords']}")
        if result['capacity_warnings']:
            print(f"  Kapasitetsvarsler:  {len(result['capacity_warnings'])}")
            for w in result['capacity_warnings'][:5]:
                print(f"    ! {w}")
            if len(result['capacity_warnings']) > 5:
                print(f"    ... og {len(result['capacity_warnings']) - 5} til")

        summary.append({
            "region": name,
            "routes": result['routes_created'],
            "visits": result['visits_assigned'],
            "no_coords": result['jobs_without_coords'],
            "warnings": len(result['capacity_warnings']),
        })

    await engine.dispose()

    # Post-check: verify 7.5h limit and remaining unscheduled
    conn = await asyncpg.connect(asyncpg_url, statement_cache_size=0)
    try:
        print(f"\n{'='*60}")
        print("OPPSUMMERING")
        print(f"{'='*60}")
        print(f"{'Region':15s} | {'Ruter':>6s} | {'Besok':>6s} | {'Uten coords':>11s} | {'Varsler':>7s}")
        print("-" * 60)
        total_routes = 0
        total_visits = 0
        total_no_coords = 0
        for s in summary:
            print(f"{s['region']:15s} | {s['routes']:6d} | {s['visits']:6d} | {s['no_coords']:11d} | {s['warnings']:7d}")
            total_routes += s['routes']
            total_visits += s['visits']
            total_no_coords += s['no_coords']
        print("-" * 60)
        print(f"{'TOTALT':15s} | {total_routes:6d} | {total_visits:6d} | {total_no_coords:11d} |")

        # ── VERIFY 7.5h LIMIT ───────────────────────────────────────────
        print(f"\n=== Verifisering: 7.5t-grensen ===")
        overloaded = await conn.fetch("""
            SELECT r.route_date, t.name as tech, reg.name as region,
                   COUNT(rv.id) as visits,
                   SUM(COALESCE(sc.sla_hours, 1.0)) as work_hours,
                   SUM(COALESCE(rv.estimated_drive_minutes, 0)) / 60.0 as drive_hours
            FROM routes r
            JOIN technicians t ON r.technician_id = t.id
            JOIN regions reg ON r.region_id = reg.id
            LEFT JOIN route_visits rv ON rv.route_id = r.id
            LEFT JOIN scheduled_visits sv ON rv.scheduled_visit_id = sv.id
            LEFT JOIN jobs j ON sv.job_id = j.id
            LEFT JOIN service_contracts sc ON j.service_contract_id = sc.id
            WHERE r.tenant_id = $1
            GROUP BY r.route_date, t.name, reg.name
            HAVING SUM(COALESCE(sc.sla_hours, 1.0)) + SUM(COALESCE(rv.estimated_drive_minutes, 0)) / 60.0 > 7.5
            ORDER BY SUM(COALESCE(sc.sla_hours, 1.0)) + SUM(COALESCE(rv.estimated_drive_minutes, 0)) / 60.0 DESC
            LIMIT 20
        """, TENANT_ID)

        if overloaded:
            print(f"  FEIL: {len(overloaded)} dager overskrider 7.5t!")
            for r in overloaded[:10]:
                total_h = float(r['work_hours'] or 0) + float(r['drive_hours'] or 0)
                print(f"    {r['region']:12s} | {r['route_date']} | {r['tech']:25s} | {r['visits']} besok | {float(r['work_hours'] or 0):.1f}t arbeid + {float(r['drive_hours'] or 0):.1f}t kjoring = {total_h:.1f}t")
        else:
            print("  OK: Ingen dager overskrider 7.5t")

        # Remaining unscheduled per region
        print(f"\n=== Gjenstaaende uplanlagte jobber ===")
        total_remaining = 0
        for name in REGIONS:
            remaining = await conn.fetchval("""
                SELECT COUNT(*) FROM jobs j
                JOIN service_contracts sc ON j.service_contract_id = sc.id
                JOIN locations l ON sc.location_id = l.id
                WHERE j.status = 'unscheduled' AND l.city = $1 AND j.tenant_id = $2
            """, name, TENANT_ID)
            if remaining > 0:
                print(f"  {name:15s}: {remaining} jobber")
            total_remaining += remaining
        print(f"  {'TOTALT':15s}: {total_remaining} jobber")

        # Truls Iversen check
        print(f"\n=== Truls Iversen-sjekk (skal ikke ha jobber for 2027-05-01) ===")
        truls_early = await conn.fetchval("""
            SELECT COUNT(*) FROM routes r
            JOIN technicians t ON r.technician_id = t.id
            WHERE t.name = 'Truls Iversen' AND r.route_date < '2027-05-01' AND r.tenant_id = $1
        """, TENANT_ID)
        print(f"  Ruter for mai: {truls_early} (skal vaere 0)")

        # Route distribution sample
        print(f"\n=== Eksempel: forste 10 ruter ===")
        routes = await conn.fetch("""
            SELECT r.route_date, t.name as tech, reg.name as region,
                   COUNT(rv.id) as visits,
                   SUM(COALESCE(sc.sla_hours, 1.0)) as work_hours,
                   SUM(COALESCE(rv.estimated_drive_minutes, 0)) / 60.0 as drive_hours
            FROM routes r
            JOIN technicians t ON r.technician_id = t.id
            JOIN regions reg ON r.region_id = reg.id
            LEFT JOIN route_visits rv ON rv.route_id = r.id
            LEFT JOIN scheduled_visits sv ON rv.scheduled_visit_id = sv.id
            LEFT JOIN jobs j ON sv.job_id = j.id
            LEFT JOIN service_contracts sc ON j.service_contract_id = sc.id
            WHERE r.tenant_id = $1
            GROUP BY r.route_date, t.name, reg.name
            ORDER BY reg.name, r.route_date
            LIMIT 10
        """, TENANT_ID)
        for r in routes:
            total_h = float(r['work_hours'] or 0) + float(r['drive_hours'] or 0)
            print(f"  {r['region']:12s} | {r['route_date']} | {r['tech']:25s} | {r['visits']} besok | {total_h:.1f}t total")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
