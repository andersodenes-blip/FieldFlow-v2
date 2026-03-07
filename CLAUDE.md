# FieldFlow v2

## Prosjektoversikt

FieldFlow v2 er en multi-tenant SaaS-plattform for ruteplanlegging av serviceoppdrag.
Bygget av en solo-utvikler (Anders Ødenes) med AI-assistanse.
V1 og V2 er adskilte kodebaser — ingen krysskopiering mellom dem.

**Mål:** Lansering 1. januar 2027.

## Teknologistack

- **Backend:** FastAPI, SQLAlchemy 2.0.41+, Alembic, Pydantic v2
- **Database:** PostgreSQL via Supabase (transaction pooler, port 6543)
- **Auth:** Auth0 Organizations (ikke implementert ennå)
- **Deployment:** Railway (auto-deploy ved push til main)
- **Frontend:** Jinja2 + HTMX + Alpine.js + Tailwind (ikke startet ennå)

## Viktige tekniske noter

- Python 3.14 lokalt — krever SQLAlchemy>=2.0.41
- PgBouncer-fix: `statement_cache_size=0` i `create_async_engine` (Supabase transaction pooler)
- Docker ikke operativt lokalt (IT-policy blokkerer WSL2-oppdatering)
- Kjør lokalt med: `python -m uvicorn app.main:app --reload --port 8000`
- SQLite-støtte for lokal utvikling (aiosqlite) — sett `DATABASE_URL=sqlite+aiosqlite:///./fieldflow_dev.db` i `.env`
- Rust/Cargo ikke tilgjengelig lokalt — bruk `python-jose[pycryptodome]` i stedet for `[cryptography]`

## Mappestruktur

```
app/
├── config.py          # Innstillinger fra .env via pydantic-settings
├── dependencies.py    # get_db, get_current_user, get_current_tenant, SQLAlchemy engine
├── main.py            # FastAPI-app med lifespan (auto-create tables for SQLite)
├── models/            # SQLAlchemy ORM-modeller (12 tabeller + Base/TenantBase)
├── schemas/           # Pydantic request/response-modeller
├── services/          # Forretningslogikk (auth_service)
├── repositories/      # Database-operasjoner (user_repository)
├── routers/           # FastAPI-endepunkter (health, auth)
└── templates/         # Jinja2-maler (tom, ikke startet)
alembic/               # Databasemigrasjoner (0001 initial, 0002 RLS)
scripts/               # Hjelpeskript (seed.py for testdata)
tests/                 # Pytest-tester
```

## Arkitekturprinsipper

- **Routers:** Validering + kall service + returner respons. Ingen forretningslogikk.
- **Services:** All forretningslogikk.
- **Repositories:** Alle DB-operasjoner.
- **Multi-tenant:** Row-Level Security (RLS) i PostgreSQL. Alle tabeller har `tenant_id`.
- `tenant_id` settes via middleware/dependency, aldri manuelt i routers.
- Modeller bruker `sqlalchemy.Uuid` og `sqlalchemy.JSON` (generiske typer, fungerer med både PostgreSQL og SQLite).

## Datamodell (12 tabeller)

tenants, users, regions, technicians, customers, locations, service_contracts, jobs, scheduled_visits, routes, route_visits, import_jobs, audit_events

## Seed-data

- Tenant: Hedengren Norge (slug: hedengren)
- Admin: admin@hedengren.no / admin123 (owner-rolle)
- 3 regioner (Oslo, Bergen, Stavanger), 2 teknikere per region

## Fase 1 status

- **Fullført:** FastAPI-app, datamodell (12 tabeller), Supabase-tilkobling, Railway-deploy, health + auth endepunkter
- **Gjenstår:** Auth0 Organizations, integrasjonstester, Docker-oppsett lokalt

## Deployment

- **GitHub:** andersodenes-blip/FieldFlow-v2
- **Railway:** Automatisk deploy ved push til main
- **Supabase:** Transaction pooler URL (hent fra .env, aldri hardkod)
