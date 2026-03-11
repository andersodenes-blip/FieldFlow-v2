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

# Canonical technician home coordinates (all regions)
TECH_COORDINATES = {
    "Helge Bratland": (58.8636, 5.7430),
    "Gunnar Sunde": (58.9750, 5.6550),
    "Eric Grønneberg": (60.0148, 11.0476),
    "Johnny Andresen": (59.4643, 10.6941),
    "Ardian Lomesi": (60.3158, 5.3457),
    "John Eirik Duley Sande": (60.4603, 5.3329),
    "Samuel Gonzales": (59.8938, 9.9203),
    "Waseem Ghannam": (59.7799, 9.8993),
    "Truls Iversen": (60.7073, 11.1090),
    "Kristian Høkeli": (59.2181, 10.9298),
    "Kristoffer Sandaker": (59.4340, 10.6590),
    "Peder Skjeltorp": (59.3770, 10.7140),
}


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

    # ── Fix technician coordinates ──────────────────────────────────────
    print("\n=== Fikser tekniker-koordinater ===")
    for name, (lat, lon) in TECH_COORDINATES.items():
        result = await conn.execute("""
            UPDATE technicians SET home_latitude = $1, home_longitude = $2
            WHERE name = $3 AND tenant_id = $4
        """, lat, lon, name, TENANT_ID)
        count = int(result.split()[-1])
        if count > 0:
            print(f"  {name:25s} -> {lat:.4f}, {lon:.4f}")
        else:
            print(f"  {name:25s} -> IKKE FUNNET (ignorerer)")

    # ── Deduplicate technicians (keep one per name per region) ──────────
    print("\n=== Sjekker duplikat-teknikere ===")
    dupes = await conn.fetch("""
        SELECT t.name, r.name as region, COUNT(*) as cnt
        FROM technicians t
        JOIN regions r ON t.region_id = r.id
        WHERE t.tenant_id = $1 AND t.is_active = true
        GROUP BY t.name, r.name
        HAVING COUNT(*) > 1
    """, TENANT_ID)
    if dupes:
        for d in dupes:
            print(f"  DUPLIKAT: {d['name']} ({d['region']}) x{d['cnt']}")
            # Keep the one with coordinates, deactivate the rest
            ids = await conn.fetch("""
                SELECT t.id, t.home_latitude FROM technicians t
                JOIN regions r ON t.region_id = r.id
                WHERE t.name = $1 AND r.name = $2 AND t.tenant_id = $3 AND t.is_active = true
                ORDER BY t.home_latitude IS NOT NULL DESC, t.created_at ASC
            """, d['name'], d['region'], TENANT_ID)
            keep_id = ids[0]['id']
            deactivate_ids = [row['id'] for row in ids[1:]]
            for did in deactivate_ids:
                await conn.execute(
                    "UPDATE technicians SET is_active = false WHERE id = $1", did
                )
            print(f"    Beholder {keep_id}, deaktiverte {len(deactivate_ids)} duplikater")
    else:
        print("  Ingen duplikater funnet")

    # Verify all technicians
    print("\n=== Tekniker-oversikt ===")
    techs = await conn.fetch("""
        SELECT t.name, r.name as region, t.home_latitude, t.home_longitude, t.is_active
        FROM technicians t
        JOIN regions r ON t.region_id = r.id
        WHERE t.tenant_id = $1
        ORDER BY r.name, t.name
    """, TENANT_ID)
    for t in techs:
        lat = f"{t['home_latitude']:.4f}" if t['home_latitude'] else "NULL"
        lon = f"{t['home_longitude']:.4f}" if t['home_longitude'] else "NULL"
        active = "aktiv" if t['is_active'] else "INAKTIV"
        print(f"  {t['region']:15s} | {t['name']:25s} | {lat}, {lon} | {active}")

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
        # Rule: work_hours + inter-job travel counts. Home→job1 does NOT count.
        # Tolerance: 7.51 to allow rounding errors
        TOLERANCE = 7.51
        print(f"\n=== Verifisering: 7.5t-grensen (arbeid + reisetid mellom jobber) ===")
        print(f"  Regel: hjem→jobb1 teller IKKE. Kun arbeidstid + jobb-til-jobb reisetid.")

        # Fetch all routes with per-visit detail for correct calculation
        all_route_rows = await conn.fetch("""
            SELECT r.id as route_id, r.route_date, t.name as tech, reg.name as region,
                   t.home_latitude, t.home_longitude
            FROM routes r
            JOIN technicians t ON r.technician_id = t.id
            JOIN regions reg ON r.region_id = reg.id
            WHERE r.tenant_id = $1
            ORDER BY reg.name, t.name, r.route_date
        """, TENANT_ID)

        all_visit_rows = await conn.fetch("""
            SELECT rv.route_id, rv.sequence_order,
                   COALESCE(rv.estimated_work_hours, 1.0) as work_hours,
                   COALESCE(rv.estimated_drive_minutes, 0) as drive_minutes,
                   l.latitude, l.longitude
            FROM route_visits rv
            JOIN scheduled_visits sv ON rv.scheduled_visit_id = sv.id
            JOIN jobs j ON sv.job_id = j.id
            JOIN service_contracts sc ON j.service_contract_id = sc.id
            JOIN locations l ON sc.location_id = l.id
            WHERE rv.tenant_id = $1
            ORDER BY rv.route_id, rv.sequence_order
        """, TENANT_ID)

        # Group visits by route_id
        from collections import defaultdict
        visits_by_route = defaultdict(list)
        for v in all_visit_rows:
            visits_by_route[v['route_id']].append(v)

        violations = []
        all_route_details = []
        for rt in all_route_rows:
            visits = visits_by_route.get(rt['route_id'], [])
            if not visits:
                continue

            work_h = sum(float(v['work_hours']) for v in visits)
            # First visit drive = home→job (informational, does NOT count)
            home_to_job_h = float(visits[0]['drive_minutes']) / 60.0
            # Inter-job drive = all visits except first (counts against 7.5h)
            inter_job_h = sum(float(v['drive_minutes']) / 60.0 for v in visits[1:])

            # Job→home: last visit location back to tech home
            job_to_home_h = 0.0
            last_v = visits[-1]
            if rt['home_latitude'] and last_v['latitude']:
                from app.services.route_planning_service import estimate_drive_minutes
                from app.route_config import get_region_config
                cfg = get_region_config(rt['region'])
                job_to_home_h = estimate_drive_minutes(
                    float(last_v['latitude']), float(last_v['longitude']),
                    float(rt['home_latitude']), float(rt['home_longitude']),
                    cfg,
                ) / 60.0

            countable = work_h + inter_job_h
            detail = {
                'region': rt['region'], 'date': rt['route_date'],
                'tech': rt['tech'], 'visits': len(visits),
                'work_h': work_h, 'inter_job_h': inter_job_h,
                'home_to_job_h': home_to_job_h, 'job_to_home_h': job_to_home_h,
                'countable': countable,
            }
            all_route_details.append(detail)
            if countable > TOLERANCE:
                violations.append(detail)

        violations.sort(key=lambda d: d['countable'], reverse=True)

        if violations:
            print(f"  FEIL: {len(violations)} dager overskrider 7.5t!")
            for d in violations[:15]:
                print(f"    {d['region']:12s} | {d['date']} | {d['tech']:25s} | {d['visits']} besok | "
                      f"{d['work_h']:.1f}t arbeid + {d['inter_job_h']:.1f}t mellom-jobb = {d['countable']:.1f}t | "
                      f"hjem→jobb: {d['home_to_job_h']:.1f}t | jobb→hjem: {d['job_to_home_h']:.1f}t")
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

        # Route distribution sample (first 10 per region)
        print(f"\n=== Eksempel: forste 10 ruter ===")
        for d in all_route_details[:10]:
            print(f"  {d['region']:12s} | {d['date']} | {d['tech']:25s} | {d['visits']} besok | "
                  f"{d['work_h']:.1f}t arbeid + {d['inter_job_h']:.1f}t mellom = {d['countable']:.1f}t | "
                  f"hjem→jobb: {d['home_to_job_h']:.1f}t | jobb→hjem: {d['job_to_home_h']:.1f}t")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
