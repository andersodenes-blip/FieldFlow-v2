# FieldFlow v2

## VIKTIG: Oppdater denne filen etter hver endring
Etter HVER oppgave du fullforer skal du:
1. Oppdatere CLAUDE.md med hva som ble endret
2. Oppdatere TODO-listen (merk fulforte, legg til nye)
3. Oppdatere filstruktur hvis nye filer ble lagt til
4. Oppdatere API-endepunkter hvis nye ble lagt til
5. Inkludere CLAUDE.md i git commit

Dette er ikke valgfritt — CLAUDE.md er prosjektets hukommelse og ma alltid vaere oppdatert.

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
- Bruk ALDRI bash-kommandoer direkte
- Gi alltid PowerShell-kommandoer som brukeren kjorer manuelt
- Format: "Kjor i PowerShell: [kommando]"
- Docker blokkert (IT-policy) — SQLite brukes lokalt som workaround
- Rust/Cargo ikke tilgjengelig — bruk `python-jose[pycryptodome]` (ikke `[cryptography]`)
- SQLite: `DATABASE_URL=sqlite+aiosqlite:///./fieldflow_dev.db` i `.env`

### Migrations
- Kjor med: `python -m alembic upgrade head` (ikke bare `alembic`)
- Migrasjoner: 0001-0008 (siste: add_route_visit_work_hours)

### Modeller
- Bruk `sqlalchemy.Uuid` og `sqlalchemy.JSON` (generiske typer, fungerer med PG og SQLite)
- Alle tabeller har `tenant_id` (RLS i PostgreSQL)

## Filstruktur (komplett)

```
app/
  __init__.py
  config.py              # Settings fra .env (har is_sqlite property)
  dependencies.py        # get_db, get_current_user, require_role, RLS SET LOCAL
  main.py                # FastAPI-app med lifespan
  route_config.py        # Per-region ruteplanleggingsconfig (RegionRouteConfig)

  models/
    __init__.py
    base.py              # Base, TenantBase (id, created_at, updated_at)
    tenant.py            # tenants: name, slug, plan, is_active, settings
    organization.py      # organizations: auth0_org_id, name, tenant_id
    user.py              # users: email, hashed_password, auth0_user_id, role, is_active
    region.py            # regions: name, city
    technician.py        # technicians: region_id, name, email, phone, is_active, home_lat/lon, start_date
    customer.py          # customers: name, org_number, contact_email, contact_phone
    location.py          # locations: customer_id, address, city, postal_code, lat/lon, external_id
    service_contract.py  # service_contracts: location_id, service_type, interval_months, next_due_date, sla_hours
    job.py               # jobs: service_contract_id, title, description, status, external_id
    scheduled_visit.py   # scheduled_visits: job_id, technician_id, scheduled_date, start/end, status, notes
    route.py             # routes: region_id, route_date, technician_id, status
    route_visit.py       # route_visits: route_id, scheduled_visit_id, sequence_order, drive_minutes, work_hours
    audit_event.py       # audit_events: user_id, action, resource_type, resource_id, metadata_
    import_job.py        # import_jobs: filename, status, row_count, error_log

  schemas/
    __init__.py
    auth.py              # TokenRequest/Response, UserResponse, Auth0CallbackResponse
    region.py            # RegionCreate/Update/Response
    technician.py        # TechnicianCreate/Update/Response
    customer.py          # CustomerCreate/Update/Response
    location.py          # LocationCreate/Update/Response
    service_contract.py  # ServiceContractCreate/Update/Response
    job.py               # JobCreate/Update/Response, JobStatusUpdate, JobGenerateRequest/Response
    route.py             # RoutePlanRequest/Response, RouteResponse, RouteVisitResponse, RouteListResponse
    scheduled_visit.py   # ScheduledVisitCreate/Response
    audit_event.py       # AuditEventResponse
    import_job.py        # ImportJobResponse
    pagination.py        # PaginatedResponse[T] (generic)

  services/
    __init__.py
    auth_service.py      # hash_password, verify_password, create_access_token, authenticate_user
    auth0_service.py     # JWKS-caching, verify_auth0_token, exchange_code, build_authorize_url
    region_service.py    # CRUD + kan-ikke-slette-med-teknikere
    technician_service.py # CRUD + region-validering + soft delete
    customer_service.py  # CRUD + sok + lokasjon-telling
    location_service.py  # CRUD under customer + aktiv-kontrakt-sjekk
    service_contract_service.py # CRUD + interval-beregning + soft delete
    job_service.py       # CRUD + status-overgangsvalidering
    job_generation_service.py   # Generer jobber fra kontrakter (horizon_days)
    route_service.py     # CRUD ruter + detaljert visitt-henting
    route_planning_service.py   # KJERNEMOTOR: haversine, nearest-neighbor, 7.5t kapasitet, helligdager
    import_service.py    # CSV-import av kunder/lokasjoner
    audit_service.py     # Logg + list audit-hendelser

  repositories/
    __init__.py
    organization_repository.py  # get_by_auth0_org_id, get_by_id
    user_repository.py          # get_by_email, get_by_id, get_by_auth0_user_id, create
    region_repository.py        # CRUD + has_technicians
    technician_repository.py    # CRUD + region-filter + soft_delete
    customer_repository.py      # CRUD + search + has_active_contracts
    location_repository.py      # CRUD per customer + has_active_contracts
    service_contract_repository.py # CRUD + get_due_contracts(horizon)
    job_repository.py           # CRUD + search + selectinload(service_contract.location)
    scheduled_visit_repository.py  # CRUD + bulk_create + count_per_technician_month
    route_repository.py         # CRUD + bulk_create_visits + delete_routes_for_region_dates
    audit_event_repository.py   # CRUD + filtrer pa resource_type/user/dato
    import_job_repository.py    # CRUD

  routers/
    __init__.py
    health.py            # GET /health
    auth.py              # POST /auth/token, GET /auth/login, GET /auth/callback, GET /auth/me
    admin.py             # GET /admin/users (org:admin)
    organizations.py     # GET/POST /organizations
    regions.py           # CRUD /regions
    technicians.py       # CRUD /technicians
    customers.py         # CRUD /customers
    locations.py         # CRUD /customers/{id}/locations, /locations/{id}
    service_contracts.py # CRUD /service-contracts
    jobs.py              # CRUD /jobs + /generate, /complete, /defer, /reschedule, /detail, /history
    routes.py            # GET /routes, GET /routes/{id}, POST /routes/plan, PATCH /routes/{id}/status
    imports.py           # POST /import/customers, GET /import/{id}
    audit_events.py      # GET /audit-events (org:admin)
    frontend.py          # Server-rendered pages + dashboard week-data API

  templates/
    base.html            # Layout med sidebar-nav, Alpine.js, HTMX
    login.html           # Login-side
    dashboard.html       # Hoved-dashboard (7 seksjoner + ukesvisning med jobb-kort)
    regions/
      list.html          # Region-liste
      _table.html        # Region-tabell (HTMX-partial)
    technicians/
      list.html          # Tekniker-liste
      _table.html        # Tekniker-tabell (HTMX-partial)
    customers/
      list.html          # Kunde-liste
      _table.html        # Kunde-tabell (HTMX-partial)
    jobs/
      list.html          # Jobb-liste med filter
      _table.html        # Jobb-tabell (HTMX-partial)
      detail.html        # Jobb-detaljside
    routes/
      dashboard.html     # Ruteplanlegging med kart

alembic/
  env.py
  script.py.mako
  versions/
    0001_initial_schema.py
    0002_enable_rls.py
    0003_organizations_and_auth0_user_mapping.py
    0004_add_external_id_columns.py
    0005_rls_on_organizations.py
    0006_add_technician_home_coordinates.py
    0007_add_technician_start_date.py
    0008_add_route_visit_work_hours.py

scripts/
  seed.py                      # Seed grunndata (tenant, admin, regioner)
  test_db.py                   # Test DB-tilkobling
  import_v1_master.py          # Importer jobber fra v1 Excel
  import_v1_jobs.py            # Importer jobber fra v1
  import_v1_technicians.py     # Importer teknikere fra v1
  import_v1_coordinates.py     # Importer/geocode koordinater (--geocode flag)
  _inspect_excel.py            # Inspiser Excel-filer
  _inspect_master.py           # Inspiser master-data
  add_technicians.py           # Legg til teknikere med geocoding
  add_drammen_technicians.py   # Legg til Drammen-teknikere
  update_sla_hours.py          # Oppdater SLA-timer fra pris
  update_seed_technicians.py   # Oppdater seed-teknikere
  cleanup_seed_technicians.py  # Rydd opp seed-teknikere
  check_work_hours.py          # Sjekk arbeidstimer
  check_due_dates.py           # Sjekk forfallsdatoer
  test_route_planning_live.py  # Test planlegging alle regioner
  test_stavanger.py            # Test kun Stavanger

tests/
  conftest.py                  # Pytest fixtures (async, SQLite in-memory)
  test_health.py
  test_auth.py
  test_auth0.py
  test_tenant_isolation.py
  test_user_org_mapping.py
  test_rbac.py
  test_job_generation.py
  test_pagination.py
  test_audit_events.py
  test_regions.py
  test_customers.py
  test_technicians.py
  test_locations.py
  test_service_contracts.py
  test_jobs.py
  test_route_planning.py
  test_import.py

data/
  stavanger/teknikere.csv
  oslo/teknikere.csv
  bergen/teknikere.csv
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

### Tabeller (15)

| Tabell | Viktige kolonner | Merknader |
|--------|-----------------|-----------|
| tenants | name, slug, plan, is_active, settings(JSON) | Base (ikke TenantBase) |
| organizations | auth0_org_id(UNIQUE), name, tenant_id | Auth0-kobling, Base |
| users | email, hashed_password, auth0_user_id, role(Enum), is_active | UQ(tenant_id,email) |
| regions | name, city | |
| technicians | region_id(FK), name, email, phone, is_active, home_latitude, home_longitude, start_date | Soft delete |
| customers | name, org_number, contact_email, contact_phone | |
| locations | customer_id(FK), address, city, postal_code, latitude, longitude, external_id(idx) | |
| service_contracts | location_id(FK), service_type, interval_months, next_due_date, sla_hours(int), is_active | Soft delete |
| jobs | service_contract_id(FK), title, description, status(Enum), external_id(idx) | |
| scheduled_visits | job_id(FK), technician_id(FK), scheduled_date, scheduled_start, scheduled_end, status(Enum), notes | |
| routes | region_id(FK), route_date, technician_id(FK), status(Enum) | |
| route_visits | route_id(FK), scheduled_visit_id(FK), sequence_order, estimated_drive_minutes, estimated_work_hours(Float) | |
| audit_events | user_id(FK), action, resource_type, resource_id, metadata_(JSON) | Base (ikke TenantBase) |
| import_jobs | filename, status(Enum), row_count, error_log(JSON) | |

Alle TenantBase-tabeller har: id(UUID PK), tenant_id(FK), created_at, updated_at.

### Enums

| Enum | Verdier |
|------|---------|
| UserRole | owner, admin, planner, dispatcher, viewer |
| JobStatus | unscheduled, scheduled, in_progress, completed, cancelled |
| VisitStatus | planned, confirmed, completed, missed |
| RouteStatus | draft, published, completed |
| ImportStatus | pending, processing, completed, failed |

### JobStatus-overganger
```
unscheduled -> scheduled, cancelled
scheduled   -> in_progress, completed, unscheduled, cancelled
in_progress -> completed, unscheduled, cancelled
completed   -> (terminal)
cancelled   -> (terminal)
```

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

## API-endepunkter (komplett)

### System
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| GET | `/health` | Ingen | Helsesjekk (status + DB) |

### Auth (`/auth`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/auth/token` | Ingen | Login (email/password -> JWT) |
| GET | `/auth/login` | Ingen | Auth0 Universal Login redirect |
| GET | `/auth/callback` | Ingen | Auth0 callback (code -> tokens) |
| GET | `/auth/me` | JWT | Gjeldende bruker |

### Admin (`/admin`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| GET | `/admin/users` | org:admin | List alle brukere i tenant |

### Regions (`/regions`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/regions` | org:admin | Opprett region |
| GET | `/regions` | JWT | List regioner (paginert) |
| GET | `/regions/{id}` | JWT | Hent region |
| PUT | `/regions/{id}` | org:admin | Oppdater region |
| DELETE | `/regions/{id}` | org:admin | Slett region (feiler hvis teknikere) |

### Technicians (`/technicians`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/technicians` | org:admin | Opprett tekniker |
| GET | `/technicians` | JWT | List teknikere (?region_id=) |
| GET | `/technicians/{id}` | JWT | Hent tekniker |
| PUT | `/technicians/{id}` | org:admin | Oppdater tekniker |
| DELETE | `/technicians/{id}` | org:admin | Soft-delete tekniker |

### Customers (`/customers`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/customers` | org:admin | Opprett kunde |
| GET | `/customers` | JWT | List kunder (?search=) |
| GET | `/customers/{id}` | JWT | Hent kunde (inkl. location_count) |
| PUT | `/customers/{id}` | org:admin | Oppdater kunde |
| DELETE | `/customers/{id}` | org:admin | Slett (feiler hvis aktive kontrakter) |

### Locations (`/customers/{id}/locations`, `/locations/{id}`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/customers/{id}/locations` | org:admin | Opprett lokasjon |
| GET | `/customers/{id}/locations` | JWT | List lokasjoner for kunde |
| GET | `/locations/{id}` | JWT | Hent lokasjon |
| PUT | `/locations/{id}` | org:admin | Oppdater lokasjon |
| DELETE | `/locations/{id}` | org:admin | Slett (feiler hvis aktive kontrakter) |

### Service Contracts (`/service-contracts`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/service-contracts` | org:admin | Opprett kontrakt |
| GET | `/service-contracts` | JWT | List (?location_id, ?customer_id, ?is_active) |
| GET | `/service-contracts/{id}` | JWT | Hent kontrakt |
| PUT | `/service-contracts/{id}` | org:admin | Oppdater kontrakt |
| DELETE | `/service-contracts/{id}` | org:admin | Soft-delete |

### Jobs (`/jobs`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/jobs/generate` | org:admin | Generer jobber fra kontrakter |
| POST | `/jobs` | org:admin | Opprett jobb |
| GET | `/jobs` | JWT | List jobber (?status, ?region_id, ?customer_id) |
| GET | `/jobs/{id}` | JWT | Hent jobb |
| PUT | `/jobs/{id}` | org:admin | Oppdater jobb |
| PATCH | `/jobs/{id}/status` | org:admin | Endre status |
| GET | `/jobs/{id}/detail` | JWT | Beriket jobbinfo for modal |
| GET | `/jobs/{id}/history` | JWT | Audit-hendelser (siste 20) |
| POST | `/jobs/{id}/complete` | org:admin | Marker fullfort |
| POST | `/jobs/{id}/schedule` | org:admin | Marker planlagt |
| POST | `/jobs/{id}/start` | org:admin | Marker pastartet |
| POST | `/jobs/{id}/unschedule` | org:admin | Avplanlegg |
| POST | `/jobs/{id}/cancel` | org:admin | Kanseller |
| POST | `/jobs/{id}/defer` | org:admin | Utsett (sletter visits, setter uplanlagt) |
| POST | `/jobs/{id}/reschedule` | org:admin | Endre dato (oppdaterer visit + rute) |

### Routes (`/routes`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/routes/plan` | org:admin | Kjor ruteplanlegging (region, start, end) |
| GET | `/routes` | JWT | List ruter (?region_id, ?route_date, ?technician_id, ?status) |
| GET | `/routes/{id}` | JWT | Rutedetaljer med besok og koordinater |
| PATCH | `/routes/{id}/status` | org:admin | Oppdater rutestatus |

### Import (`/import`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| POST | `/import/customers` | org:admin | CSV-import av kunder/lokasjoner |
| GET | `/import/{id}` | JWT | Hent import-status |

### Organizations (`/organizations`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| GET | `/organizations` | JWT | List organisasjoner |
| POST | `/organizations` | org:admin | Opprett Auth0-organisasjon |

### Audit Events (`/audit-events`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| GET | `/audit-events` | org:admin | List hendelser (?resource_type, ?user_id, ?date_from, ?date_to) |

### Frontend (server-rendered, `/app`)
| Metode | Sti | Auth | Beskrivelse |
|--------|-----|------|-------------|
| GET | `/app/login` | Ingen | Login-side |
| GET | `/app/logout` | Ingen | Logg ut (slett cookie) |
| GET | `/app/dashboard` | Cookie | Dashboard med KPI, kalender, ukesvisning |
| GET | `/app/dashboard/week-data` | Cookie | JSON: jobb-kort + tekniker-kapasitet per dag |
| GET | `/app/customers` | Cookie | Kundeliste |
| GET | `/app/customers/table` | Cookie | Kunde-tabell (HTMX) |
| GET | `/app/regions` | Cookie | Regionliste |
| GET | `/app/regions/table` | Cookie | Region-tabell (HTMX) |
| GET | `/app/technicians` | Cookie | Teknikerliste |
| GET | `/app/technicians/table` | Cookie | Tekniker-tabell (HTMX) |
| GET | `/app/jobs` | Cookie | Jobbliste med filter |
| GET | `/app/jobs/table` | Cookie | Jobb-tabell (HTMX) |
| GET | `/app/jobs/{id}` | Cookie | Jobb-detaljside |
| GET | `/app/routes` | Cookie | Ruteplanlegging |

### Paginering (alle list-endepunkter)
```json
{ "items": [...], "total": 42, "page": 1, "page_size": 20 }
```
Params: `page` (default 1), `page_size` (default 20, max 100), `sort_by`, `sort_order` (asc/desc)

## Ruteplanlegging

**Kjernefil:** `app/services/route_planning_service.py`
**Config:** `app/route_config.py`

### Regler
- Maks **7.5t per dag** per tekniker (arbeid + reisetid, inkl. forste jobb fra hjemadresse)
- Store jobber splittes over flere dager (f.eks. 20t -> 3 dager)
- `route_visit.estimated_work_hours` = kun tildelt del (ikke total SLA)
- Norske helligdager og helger hoppes over (Easter-algoritme)
- Nearest-neighbor for jobbrekkefolge
- Respekterer `technician.start_date`
- Sletter eksisterende draft-ruter for replanning

### Correction factors (haversine -> virkelig kjoreavstand)
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
Stavanger-unntak: <7000 kr -> 3t, 7000-15000 -> 6t, >15000 -> formel
```

### Kapasitetslogikk (v1-paritet)
```python
space_left = max_hours - hours_today
travel_hours = estimate_drive_minutes(...) / 60
actual = travel_hours + job.work_hours
if actual <= space_left:    # Hele jobben far plass
elif work_today > 0:        # Split: jobb i dag + resten til pending_work
else:                       # Ikke plass -> neste dag
```

### Jobb-tildeling
- Vektet scoring: geo-avstand (0.4) + manedlig balanse (0.4) + kapasitet (0.2)
- Jobber sortert etter avstand fra centroid (lengst forst)

## Dashboard (v2)

Dashboardet (`/app/dashboard`) replikerer v1-layouten med 7 seksjoner:
1. **Header** — mork gradient (#1a1a2e -> #16213e)
2. **KPI-grid** — Totalt, Fullfort (#ec4899), Planlagt (#2563eb), Uplanlagt (#ea580c)
3. **Arets fremgang** — progress-bar med rod dato-markor
4. **Fordeling per tekniker** — 2-kolonne grid med stats og progress
5. **Filter-bar** — tekniker-dropdown
6. **Kalender** — manedsgrid + ukesvisning med jobb-kort
7. **Job-modal** — detaljer + fullfor/utsett/endre dato

### Ukesvisning (implementert)
- Klikk pa dato i manedskalender -> apner ukesvisning for den uken
- 5 kolonner (Man-Fre), henter data fra `GET /app/dashboard/week-data`
- **Uke-tabs** med jobbtelling per uke (f.eks. "Uke 10 (12)")
- **Jobb-kort** per besok: ticket, adresse, tekniker, SLA-timer, status-badge
- **Status-badges:** Fullfort (rosa), Planlagt (bla), Forsinket (rod), Uplanlagt (oransje)
- **Fargede venstrekanter:** gron=fullfort, bla=planlagt, gul=forsinket, oransje=uplanlagt
- **Knapper:** Fullfor (gron) + Utsett (gul) + Detaljer (bla). Fulforte viser bare Detaljer
- **+Xd/-Xd badges:** viser dager for/etter plan for fulforte jobber (gron/oransje)
- **Tekniker-progress-bars** per dag under jobbene: <50% gron, 50-80% gul, >80% rod

### CSS-fargepalett (identisk med v1)
- Background: `#f0f2f5`
- Header: `linear-gradient(135deg, #1a1a2e, #16213e)`
- Fullfort: `#ec4899`
- Planlagt: `#2563eb`
- Uplanlagt: `#ea580c`
- Kort: hvit, `border-radius: 10px`, `box-shadow: 0 1px 3px rgba(0,0,0,.06)`

## Implementeringsstatus

### Ferdig implementert
- Full 3-lags arkitektur (router -> service -> repository) for alle 13 entiteter
- JWT-autentisering med rolle-basert tilgangskontroll
- Auth0 OAuth2-integrasjon (forberedt, ikke aktivert)
- Ruteplanlegging med haversine, nearest-neighbor, 7.5t kapasitet
- Dashboard med KPI, teknikerstats, kalender, ukesvisning med jobb-kort
- CRUD for alle entiteter med paginering og sortering
- Jobb-generering fra servicekontrakter
- CSV-import av kunder/lokasjoner
- Jobb-handlinger: fullfor, utsett, endre dato, kanseller
- Audit-logging for alle mutasjoner
- 19 testfiler med pytest
- 8 Alembic-migrasjoner
- Frontend: dashboard, jobbliste, kundeliste, regionliste, teknikerliste, ruteplanlegging

### Mangler / TODO
- Auth0 Organizations aktivering i produksjon
- Tekniker-mobilapp / feltvisning
- Varslingssystem (e-post/SMS)
- Kartvisning i dashboard (Leaflet-kart er i routes/dashboard.html men ikke dashboard)
- Backup/eksport-funksjon
- Rapporter og statistikk-side
- Kunde-detaljside (kun liste eksisterer)
- Multi-dag jobb-splitting i ukesvisning (dag X/Y badges)
- Smart planlegging (5 beste datoforslag) — kun i v1
- Kapasitetsvarsler (bjelle-ikon med proaktive advarsler)
- Kryssregion-forslag (flytt jobber til nabolag-tekniker)
- ICS kalender-eksport + e-postutsendelse
- Global optimering (MOVE/SWAP hill-climbing)
- Territory-rapport og belastningsanalyse
- Bompengeestimering fra NVDB API
- Frie dager per tekniker-visning

## Nyttige scripts

| Script | Beskrivelse |
|--------|-------------|
| `scripts/seed.py` | Seed grunndata (tenant, admin, regioner) |
| `scripts/test_route_planning_live.py` | Test planlegging alle regioner |
| `scripts/test_stavanger.py` | Test kun Stavanger |
| `scripts/import_v1_master.py` | Importer jobber fra v1 Excel |
| `scripts/import_v1_jobs.py` | Importer jobber fra v1 |
| `scripts/import_v1_technicians.py` | Importer teknikere fra v1 |
| `scripts/import_v1_coordinates.py --geocode` | Importer/geocode koordinater |
| `scripts/add_technicians.py` | Legg til nye teknikere med geocoding |
| `scripts/add_drammen_technicians.py` | Legg til Drammen-teknikere |
| `scripts/update_sla_hours.py` | Oppdater SLA-timer fra pris |
| `scripts/update_seed_technicians.py` | Oppdater seed-teknikere |
| `scripts/cleanup_seed_technicians.py` | Rydd opp seed-teknikere |
| `scripts/check_work_hours.py` | Sjekk arbeidstimer |
| `scripts/check_due_dates.py` | Sjekk forfallsdatoer |
| `scripts/test_db.py` | Test DB-tilkobling |

## PowerShell-kommandoer

```powershell
# Start lokal server
python -m uvicorn app.main:app --reload --port 8000

# Kjor migrasjoner
python -m alembic upgrade head

# Kjor alle tester
python -m pytest tests/ -v

# Kjor spesifikk test
python -m pytest tests/test_route_planning.py -v

# Test ruteplanlegging (krever Railway DB)
python scripts/test_route_planning_live.py
python scripts/test_stavanger.py

# Seed grunndata
python scripts/seed.py

# Importer v1-data
python scripts/import_v1_master.py
python scripts/import_v1_coordinates.py --geocode

# Git push
git add -A && git commit -m "beskrivelse" && git push
```

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
| 401 pa dashboard/week-data | Cookie mangler, sjekk at login setter access_token cookie |
| Ruteplanlegging viser 0 jobber ved innlasting | Fikset: server-side preloading av ruter i routes_page() |
