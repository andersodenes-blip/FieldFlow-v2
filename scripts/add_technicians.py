# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Add new technicians with geocoded home addresses."""
import asyncio
import uuid
from pathlib import Path

import asyncpg
import httpx

TENANT_ID = "d1372aa8-46d5-4a5c-a439-132e285fe46c"

TECHNICIANS = [
    {
        "region": "Innlandet",
        "name": "Truls Iversen",
        "email": "truls.iversen@hedengren.no",
        "phone": "00000000",
        "address": "Tangenvegen 65, 2335 Stange, Norway",
    },
    {
        "region": "Østfold",
        "name": "Kristian Høkeli",
        "email": "kristian.hokeli@hedengren.no",
        "phone": "00000000",
        "address": "Skredderveien 12, 1617 Fredrikstad, Norway",
    },
    {
        "region": "Østfold",
        "name": "Kristoffer Sandaker",
        "email": "kristoffer.sandaker@hedengren.no",
        "phone": "00000000",
        "address": "Nesveien 30, 1513 Moss, Norway",
    },
    {
        "region": "Østfold",
        "name": "Peder Skjeltorp",
        "email": "peder.skjeltorp@hedengren.no",
        "phone": "00000000",
        "address": "Skogfaret 45, 1580 Rygge, Norway",
    },
]


def read_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env = {}
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


async def geocode(address: str, api_key: str) -> tuple[float, float]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key},
        )
        data = resp.json()
        if data["status"] != "OK" or not data["results"]:
            raise RuntimeError(f"Geocoding failed for '{address}': {data['status']}")
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]


async def main():
    env = read_env()
    db_url = env["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    api_key = env.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("GOOGLE_MAPS_API_KEY not found in .env!")
        return

    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        # Get region IDs
        regions = await conn.fetch(
            "SELECT id, name FROM regions WHERE tenant_id = $1", TENANT_ID
        )
        region_map = {r["name"]: r["id"] for r in regions}
        print("Regioner:", ", ".join(region_map.keys()))

        for tech in TECHNICIANS:
            region_name = tech["region"]
            region_id = region_map.get(region_name)
            if not region_id:
                print(f"  Region '{region_name}' ikke funnet — hopper over {tech['name']}")
                continue

            # Geocode
            lat, lon = await geocode(tech["address"], api_key)
            print(f"\n{tech['name']}:")
            print(f"  Adresse: {tech['address']}")
            print(f"  Koordinater: {lat:.6f}, {lon:.6f}")
            print(f"  Region: {region_name} ({region_id})")

            # Insert
            tech_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO technicians (id, tenant_id, region_id, name, email, phone, is_active, home_latitude, home_longitude, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8, NOW(), NOW())
            """, tech_id, TENANT_ID, region_id, tech["name"], tech["email"], tech["phone"], lat, lon)
            print(f"  Opprettet: {tech_id}")

        # Verify
        print("\n=== Alle teknikere ===")
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
            print(f"  {t['region']:15s} | {t['name']:25s} | {lat}, {lon} | aktiv={t['is_active']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
