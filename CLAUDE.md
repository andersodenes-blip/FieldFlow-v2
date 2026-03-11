# FieldFlow v2

## Prosjekt

- **Repo:** andersodenes-blip/FieldFlow-v2
- **Railway:** https://fieldflow-v2-production.up.railway.app
- **Stack:** FastAPI + SQLAlchemy 2.0.41+ async + Alembic + Pydantic v2 + Supabase PostgreSQL
- **Frontend:** Jinja2 + HTMX + Alpine.js + Tailwind CSS
- **Python:** 3.12 pa Railway, 3.14 lokalt
- **Auth:** Auth0 Organizations (ikke aktivert enna) + JWT (python-jose)
- **Deploy:** Railway auto-deploy ved push til main
- **Mal:** Lansering 1. januar 2027

V1 og V2 er adskilte kodebaser. Ingen krysskopiering.

## Kritiske tekniske regler

### PgBouncer / Supabase
- **ALLTID** `statement_cache_size=0` i `create_async_engine` connect_args
- **ALLTID** `statement_cache_size=0` i `asyncpg.connect()`
- DB-URL: les fra `.env`, aldri hardkod

### Lokalt miljo
- Bash er blokkert — skriv alltid PowerShell-kommandoer til brukeren
- Docker blokkert (IT-policy) — SQLite brukes lokalt som workaround
- Rust/Cargo ikke tilgjengelig — bruk `python-jose[pycryptodome]` (ikke `[cryptography]`)
- Kjor lokalt: `python -m uvicorn app.main:app --reload --port 8000`
- SQLite: `DATABASE_URL=sqlite+aiosqlite:///./fieldflow_dev.db` i `.env`

### Migrations
- Kjor med: `python -m alembic upgrade head` (ikke bare `alembic`)
- Migrasjoner: 0001-0008 (siste: add_route_visit_work_hours)

### Modeller
- Bruk `sqlalchemy.Uuid` og `sqlalchemy.JSON` (generiske typer, fungerer med PG og SQLite)
- Alle tabeller har `tenant_id` (RLS i PostgreSQL)

## Arkitektur

```
app/
  config.py          # Settings fra .env (har is_sqlite property)
  dependencies.py    # get_db, get_current_user, RLS SET LOCAL
  main.py            # FastAPI-app med lifespan
  route_config.py    # Per-region ruteplanleggingsconfig
  models/            # SQLAlchemy ORM (13 tabeller + Base/TenantBase)
  schemas/           # Pydantic v2 request/response
  services/          # Forretningslogikk
  repositories/      # DB-operasjoner
  routers/           # FastAPI-endepunkter
  templates/         # Jinja2 (dashboard, routes, jobs, etc.)
alembic/versions/    # 0001-0008
scripts/             # Import, test, seed
tests/               # Pytest
```

**Prinsipper:**
- Routers: validering + kall service + returner respons. Ingen forretningslogikk.
- Services: all forretningslogikk.
- Repositories: alle DB-operasjoner.
- `tenant_id` settes via middleware/dependency, aldri manuelt i routers.

## Database

**Tenant:** Hedengren Norge
- Slug: `hedengren`
- ID: `d1372aa8-46d5-4a5c-a439-132e285fe46c`
- Admin: admin@hedengren.no / admin123 (owner-rolle)

**Tabeller (13):** tenants, users, regions, technicians, customers, locations, service_contracts, jobs, scheduled_visits, routes, route_visits, audit_events, import_jobs

### Regioner og teknikere

| Region | Teknikere |
|--------|-----------|
| Stavanger | Helge Bratland, Gunnar Sunde |
| Oslo | Eric Gronneberg, Johnny Andresen |
| Bergen | Ardian Lomesi, John Eirik Duley Sande |
| Drammen | Samuel Gonzales, Waseem Ghannam |
| Innlandet | Truls Iversen (start_date: 2027-05-01) |
| Ostfold | Kristian Hokeli, Kristoffer Sandaker, Peder Skjeltorp |

Region-IDer hentes dynamisk fra DB:
```sql
SELECT id, name FROM regions WHERE tenant_id = 'd1372aa8-46d5-4a5c-a439-132e285fe46c' ORDER BY name;
```

## Ruteplanlegging

**Kjernefil:** `app/services/route_planning_service.py`
**Config:** `app/route_config.py`

### Regler
- Maks **7.5t per dag** per tekniker (arbeid + reisetid, inkl. forste jobb fra hjemadresse)
- Store jobber splittes over flere dager (f.eks. 20t → 3 dager)
- `route_visit.estimated_work_hours` = kun tildelt del (ikke total SLA)
- Norske helligdager og helger hoppes over (Easter-algoritme)
- Nearest-neighbor for jobbrekkefolge
- Respekterer `technician.start_date`

### Correction factors (haversine → virkelig kjoreavstand)
| Region | Factor |
|--------|--------|
| Stavanger | 1.49 |
| Bergen | 1.40 |
| Oslo | 1.30 |
| Drammen | 1.20 |
| Innlandet | 1.20 |
| Ostfold | 1.20 |

### Travel-formel
```
travel_minutes = (haversine_km * correction_factor / 30 km/h) * 60 + 10 min parking
```

### SLA-timer formel
```
sla_hours = round_up(cost / 2 / 1450, nearest 0.5)
Stavanger-unntak: <7000 kr → 3t, 7000-15000 → 6t, >15000 → formel
```

### Kapasitetslogikk (v1-paritet)
```python
space_left = max_hours - hours_today
travel_hours = estimate_drive_minutes(...) / 60
actual = travel_hours + job.work_hours
if actual <= space_left:    # Hele jobben far plass
elif work_today > 0:        # Split: jobb i dag + resten til pending_work
else:                       # Ikke plass — neste dag
```

## API-endepunkter

### Frontend (server-rendered)
- `GET /app/dashboard` — Hovedoversikt med KPI, teknikere, kalender
- `GET /app/routes` — Ruteplanlegging med kart og kalender
- `GET /app/jobs` — Jobbliste med filter
- `GET /app/customers` — Kundeliste
- `GET /app/regions` — Regionliste
- `GET /app/technicians` — Teknikerliste

### REST API
- `GET/POST /jobs` — CRUD + filter (status, region_id, customer_id)
- `GET /jobs/{id}/detail` — Beriket jobbinfo for modal
- `GET /jobs/{id}/history` — Audit-hendelser
- `POST /jobs/{id}/complete|defer|reschedule` — Handlinger
- `GET /routes` — Ruter med filter (region_id, date, technician_id)
- `GET /routes/{id}` — Rutedetaljer med besok og koordinater
- `POST /routes/plan` — Kjor ruteplanlegging
- `GET/POST /technicians|regions|customers|locations|service_contracts`

## Nyttige scripts

| Script | Beskrivelse |
|--------|-------------|
| `scripts/test_route_planning_live.py` | Test planlegging alle regioner |
| `scripts/test_stavanger.py` | Test kun Stavanger |
| `scripts/import_v1_master.py` | Importer jobber fra v1 Excel |
| `scripts/update_sla_hours.py` | Oppdater arbeidstimer fra pris |
| `scripts/import_v1_coordinates.py --geocode` | Importer/geocode koordinater |
| `scripts/add_technicians.py` | Legg til nye teknikere med geocoding |
| `scripts/seed.py` | Seed grunndata |

## Vanlige feilmeldinger

| Feil | Losning |
|------|---------|
| `prepared statement ... does not exist` | Legg til `statement_cache_size=0` i engine/connect |
| `cannot import settings` | Sjekk `app/config.py` vs `app/config/` |
| `start_date does not exist` | Kjor `python -m alembic upgrade head` |
| `estimated_work_hours does not exist` | Kjor `python -m alembic upgrade head` (0008) |
| Railway build timeout | Sjekk requirements.txt for tunge pakker (fjern openpyxl etc.) |
| 422 Unprocessable Entity | Sjekk page_size limit i API vs frontend request |
| Map already initialized | Sjekk `container._leaflet_id` for Leaflet double-init |
| Alpine `@change` ikke fungerer | Bruk `$watch('variabel', ...)` i stedet |

## Dashboard (v2)

Dashboardet (`/app/dashboard`) replikerer v1-layouten med 7 seksjoner:
1. **Header** — mork gradient (#1a1a2e → #16213e)
2. **KPI-grid** — Totalt, Fullfort (#ec4899), Planlagt (#2563eb), Uplanlagt (#ea580c)
3. **Arets fremgang** — progress-bar med rod dato-markor
4. **Fordeling per tekniker** — 2-kolonne grid med stats og progress
5. **Filter-bar** — tekniker-dropdown
6. **Kalender** — manedsgrid + ukevisning med kapasitetsbar per tekniker
7. **Job-modal** — detaljer + fullfor/utsett/endre dato

CSS-fargepalett (identisk med v1):
- Background: `#f0f2f5`
- Header: `linear-gradient(135deg, #1a1a2e, #16213e)`
- Fullfort: `#ec4899`
- Planlagt: `#2563eb`
- Uplanlagt: `#ea580c`
- Kort: hvit, `border-radius: 10px`, `box-shadow: 0 1px 3px rgba(0,0,0,.06)`
