# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Debug: find multi-day jobs in DB and check exclusivity violations."""
import asyncio
import re
from pathlib import Path

import asyncpg

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"


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
        # ── 1. Find all multi-day visits (notes like "Del X/Y") ──
        print("=" * 80)
        print("STEG 1: Finn alle flerdagers-besøk i databasen")
        print("=" * 80)

        multiday_visits = await conn.fetch("""
            SELECT
                sv.id as visit_id,
                sv.job_id,
                sv.scheduled_date,
                sv.notes,
                j.title as job_title,
                t.name as tech_name,
                rv.sequence_order,
                rv.estimated_work_hours,
                rv.estimated_drive_minutes,
                r.route_date,
                r.id as route_id
            FROM scheduled_visits sv
            JOIN jobs j ON j.id = sv.job_id
            JOIN route_visits rv ON rv.scheduled_visit_id = sv.id
            JOIN routes r ON r.id = rv.route_id
            JOIN technicians t ON t.id = r.technician_id
            WHERE sv.tenant_id = $1
              AND sv.notes IS NOT NULL
              AND sv.notes LIKE 'Del %'
            ORDER BY t.name, sv.scheduled_date, rv.sequence_order
        """, TENANT_ID)

        if not multiday_visits:
            print("\nINGEN flerdagers-besøk funnet i databasen!")
            print("Dette betyr at total_parts aldri blir > 1 under planlegging.\n")

            # Check for jobs that SHOULD be multi-day (work_hours > 7.5)
            print("Sjekker jobber med sla_hours > 7.5 (burde vært splittet):")
            big_jobs = await conn.fetch("""
                SELECT j.title, sc.sla_hours, j.status
                FROM jobs j
                JOIN service_contracts sc ON sc.id = j.service_contract_id
                WHERE j.tenant_id = $1
                  AND sc.sla_hours > 7.5
                ORDER BY sc.sla_hours DESC
                LIMIT 20
            """, TENANT_ID)
            for bj in big_jobs:
                print(f"  {bj['title']:30s} | SLA: {bj['sla_hours']}t | Status: {bj['status']}")

            if not big_jobs:
                print("  Ingen jobber med sla_hours > 7.5 funnet.")

            # Check for jobs that were SPLIT due to capacity (work_hours < 7.5 but still multi-visit)
            print("\nSjekker jobber med FLERE besøk (mulig split pga kapasitet):")
            multi_visit_jobs = await conn.fetch("""
                SELECT
                    j.id,
                    j.title,
                    sc.sla_hours,
                    COUNT(sv.id) as visit_count,
                    array_agg(sv.scheduled_date ORDER BY sv.scheduled_date) as dates,
                    array_agg(sv.notes ORDER BY sv.scheduled_date) as notes_arr
                FROM jobs j
                JOIN service_contracts sc ON sc.id = j.service_contract_id
                JOIN scheduled_visits sv ON sv.job_id = j.id
                WHERE j.tenant_id = $1
                  AND j.status = 'scheduled'
                GROUP BY j.id, j.title, sc.sla_hours
                HAVING COUNT(sv.id) > 1
                ORDER BY COUNT(sv.id) DESC
                LIMIT 30
            """, TENANT_ID)
            for mvj in multi_visit_jobs:
                notes = [n or "NULL" for n in mvj['notes_arr']]
                print(f"  {mvj['title']:30s} | SLA: {mvj['sla_hours'] or '?':>5}t | "
                      f"Besøk: {mvj['visit_count']} | Datoer: {mvj['dates']} | Notes: {notes}")

            if not multi_visit_jobs:
                print("  Ingen jobber med flere besøk funnet.")

        else:
            print(f"\nFant {len(multiday_visits)} flerdagers-besøk:\n")
            for v in multiday_visits:
                print(f"  {v['tech_name']:25s} | {v['route_date']} | seq={v['sequence_order']} | "
                      f"{v['job_title']:30s} | {v['estimated_work_hours']:.1f}t arbeid | "
                      f"{v['estimated_drive_minutes']}min kjøring | {v['notes']}")

        # ── 2. For each multi-day job, check all days and their co-visits ──
        print("\n" + "=" * 80)
        print("STEG 2: Sjekk eksklusivitet — har ikke-siste dager andre besøk?")
        print("=" * 80)

        # Group by job_id
        job_groups = {}
        for v in multiday_visits:
            jid = v['job_id']
            if jid not in job_groups:
                job_groups[jid] = []
            job_groups[jid].append(v)

        violations = 0
        for job_id, visits in sorted(job_groups.items(), key=lambda x: x[1][0]['tech_name']):
            job_title = visits[0]['job_title']
            tech = visits[0]['tech_name']
            # Parse parts from notes
            parts_info = []
            for v in visits:
                m = re.match(r"Del (\d+)/(\d+)", v['notes'] or "")
                if m:
                    parts_info.append((int(m.group(1)), int(m.group(2)), v['route_date'], v['route_id']))

            if not parts_info:
                continue

            print(f"\n  Jobb: {job_title} | Tekniker: {tech}")
            for part_num, total, route_date, route_id in parts_info:
                is_last = (part_num == total)

                # Get ALL visits on this route (same tech, same day)
                all_on_day = await conn.fetch("""
                    SELECT
                        rv.sequence_order,
                        rv.estimated_work_hours,
                        rv.estimated_drive_minutes,
                        j.title as job_title,
                        sv.notes
                    FROM route_visits rv
                    JOIN scheduled_visits sv ON sv.id = rv.scheduled_visit_id
                    JOIN jobs j ON j.id = sv.job_id
                    WHERE rv.route_id = $1
                    ORDER BY rv.sequence_order
                """, route_id)

                marker = "✓ SISTE" if is_last else "⚠ IKKE-SISTE"
                visit_count = len(all_on_day)
                has_violation = not is_last and visit_count > 1

                if has_violation:
                    violations += 1
                    print(f"    Del {part_num}/{total} | {route_date} | {marker} | "
                          f"Besøk på dagen: {visit_count} | ❌ BRUDD!")
                else:
                    print(f"    Del {part_num}/{total} | {route_date} | {marker} | "
                          f"Besøk på dagen: {visit_count} | OK")

                for day_v in all_on_day:
                    notes = day_v['notes'] or ""
                    print(f"      seq={day_v['sequence_order']} | {day_v['job_title']:30s} | "
                          f"{day_v['estimated_work_hours']:.1f}t | {day_v['estimated_drive_minutes']}min | {notes}")

        print(f"\n{'=' * 80}")
        if violations:
            print(f"RESULTAT: {violations} eksklusivitetsbrudd funnet!")
        else:
            print("RESULTAT: Ingen eksklusivitetsbrudd funnet (eller ingen flerdagersjobber).")

        # ── 3. Check worst days (most hours) to see if multi-day logic matters ──
        print(f"\n{'=' * 80}")
        print("STEG 3: De 20 verste dagene (arbeid + mellom-jobb reisetid)")
        print("=" * 80)

        worst_days = await conn.fetch("""
            SELECT
                t.name as tech_name,
                r.route_date,
                r.id as route_id,
                COUNT(rv.id) as visit_count,
                COALESCE(SUM(rv.estimated_work_hours), 0) as total_work_h,
                COALESCE(SUM(CASE WHEN rv.sequence_order > 1
                    THEN rv.estimated_drive_minutes ELSE 0 END), 0) / 60.0 as inter_job_h,
                COALESCE(SUM(rv.estimated_work_hours), 0) +
                    COALESCE(SUM(CASE WHEN rv.sequence_order > 1
                        THEN rv.estimated_drive_minutes ELSE 0 END), 0) / 60.0 as capacity_h
            FROM routes r
            JOIN technicians t ON t.id = r.technician_id
            JOIN route_visits rv ON rv.route_id = r.id
            WHERE r.tenant_id = $1
            GROUP BY t.name, r.route_date, r.id
            ORDER BY capacity_h DESC
            LIMIT 20
        """, TENANT_ID)

        for wd in worst_days:
            flag = "❌ >7.5t" if float(wd['capacity_h']) > 7.51 else "  OK"
            print(f"  {wd['tech_name']:25s} | {wd['route_date']} | "
                  f"besøk={wd['visit_count']} | arbeid={float(wd['total_work_h']):.2f}t | "
                  f"mellom-jobb={float(wd['inter_job_h']):.2f}t | "
                  f"kapasitet={float(wd['capacity_h']):.2f}t | {flag}")

        # ── 4. Print the relevant code sections ──
        print(f"\n{'=' * 80}")
        print("STEG 4: Relevant kode for multi_day_exclusive")
        print("=" * 80)

        rps_path = Path(__file__).resolve().parent.parent / "app" / "services" / "route_planning_service.py"
        lines = rps_path.read_text(encoding="utf-8").splitlines()

        # Print _place_job split section (where total_parts is set)
        print("\n── _place_job: split-logikk (linje ~414-445) ──")
        for i, line in enumerate(lines[413:445], start=414):
            print(f"  {i:4d} | {line}")

        # Print _distribute_across_days: multi_day_exclusive logic
        print("\n── _distribute_across_days: pending_work + exclusive (linje ~507-572) ──")
        for i, line in enumerate(lines[506:572], start=507):
            print(f"  {i:4d} | {line}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
