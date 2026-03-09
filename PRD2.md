# FieldFlow v2 — PRD Fase 2

Prosjekt: FieldFlow v2
Repo: andersodenes-blip/FieldFlow-v2
Stack: FastAPI + SQLAlchemy + Alembic + Supabase + Auth0 + Jinja2/HTMX/Alpine.js/Tailwind

---

## Fase 1 — Fullført

| ID | Tittel | Status |
|----|--------|--------|
| US-001 | Bytt Supabase-databasepassord | BLOCKED — HUMAN |
| US-002 | Verifiser databasetilkobling etter passordbytte | BLOCKED — avhenger US-001 |
| US-003 | Docker/WSL2 lokal utviklingsmiljø | BLOCKED — IT-policy |
| US-004 | Auth0 Organizations grunnoppsett | DONE |
| US-005 | Bruker/org-mapping i database | DONE |
| US-006 | Rollebasert tilgangskontroll (RBAC) | DONE |

---

## Fase 2 — User Stories

### US-007: CRUD for regioner

**Prioritet:** high
**Avhenger av:** —

**Beskrivelse:**
Admin-bruker skal kunne opprette, liste, oppdatere og slette regioner for sin tenant. Regioner er grunnlaget for å organisere teknikere og ruter geografisk.

**Akseptansekriterier:**
- [ ] `POST /regions` oppretter en region (krever `org:admin`)
- [ ] `GET /regions` lister alle regioner for gjeldende tenant
- [ ] `GET /regions/{id}` returnerer én region
- [ ] `PUT /regions/{id}` oppdaterer en region (krever `org:admin`)
- [ ] `DELETE /regions/{id}` sletter en region (krever `org:admin`, feiler hvis teknikere er tilknyttet)
- [ ] Pydantic-schemas: `RegionCreate`, `RegionUpdate`, `RegionResponse`
- [ ] Repository: `RegionRepository` med CRUD-operasjoner
- [ ] Service: `RegionService` med forretningslogikk
- [ ] Alle endepunkter filtrerer på `tenant_id` via RLS
- [ ] Tester: opprett, list, oppdater, slett, cross-tenant isolasjon

---

### US-008: CRUD for teknikere

**Prioritet:** high
**Avhenger av:** US-007

**Beskrivelse:**
Admin-bruker skal kunne administrere teknikere. Teknikere tilhører en region og er de som utfører serviceoppdrag i felt.

**Akseptansekriterier:**
- [ ] `POST /technicians` oppretter en tekniker knyttet til en region (krever `org:admin`)
- [ ] `GET /technicians` lister alle teknikere for gjeldende tenant (støtter filtrering på `region_id`)
- [ ] `GET /technicians/{id}` returnerer én tekniker med regioninfo
- [ ] `PUT /technicians/{id}` oppdaterer en tekniker (krever `org:admin`)
- [ ] `DELETE /technicians/{id}` deaktiverer tekniker (soft delete via `is_active=false`)
- [ ] Pydantic-schemas: `TechnicianCreate`, `TechnicianUpdate`, `TechnicianResponse`
- [ ] Repository: `TechnicianRepository` med CRUD + filtrering
- [ ] Service: `TechnicianService` med forretningslogikk
- [ ] Validering: region_id må tilhøre samme tenant
- [ ] Tester: CRUD, regionfiltrering, soft delete, cross-tenant isolasjon

---

### US-009: CRUD for kunder

**Prioritet:** high
**Avhenger av:** —

**Beskrivelse:**
Admin-bruker skal kunne administrere kunder (bedrifter) som har serviceavtaler. Kunder har lokasjoner der service utføres.

**Akseptansekriterier:**
- [ ] `POST /customers` oppretter en kunde (krever `org:admin`)
- [ ] `GET /customers` lister alle kunder for gjeldende tenant (søk på navn, paginering)
- [ ] `GET /customers/{id}` returnerer kunde med antall lokasjoner
- [ ] `PUT /customers/{id}` oppdaterer en kunde (krever `org:admin`)
- [ ] `DELETE /customers/{id}` sletter kunde (feiler hvis aktive kontrakter finnes)
- [ ] Pydantic-schemas: `CustomerCreate`, `CustomerUpdate`, `CustomerResponse`
- [ ] Repository: `CustomerRepository` med CRUD + søk + paginering
- [ ] Service: `CustomerService` med forretningslogikk
- [ ] Tester: CRUD, søk, paginering, cross-tenant isolasjon

---

### US-010: CRUD for lokasjoner

**Prioritet:** high
**Avhenger av:** US-009

**Beskrivelse:**
Admin-bruker skal kunne registrere lokasjoner (adresser) tilhørende en kunde. Lokasjoner er der serviceoppdrag utføres.

**Akseptansekriterier:**
- [ ] `POST /customers/{customer_id}/locations` oppretter lokasjon under en kunde
- [ ] `GET /customers/{customer_id}/locations` lister lokasjoner for en kunde
- [ ] `GET /locations/{id}` returnerer én lokasjon med kundeinformasjon
- [ ] `PUT /locations/{id}` oppdaterer lokasjon (adresse, koordinater)
- [ ] `DELETE /locations/{id}` sletter lokasjon (feiler hvis aktive kontrakter finnes)
- [ ] Felt: address, city, postal_code, latitude, longitude
- [ ] Pydantic-schemas: `LocationCreate`, `LocationUpdate`, `LocationResponse`
- [ ] Repository: `LocationRepository` med CRUD
- [ ] Service: `LocationService` med validering (customer_id tilhører tenant)
- [ ] Tester: CRUD, nestede under kunde, cross-tenant isolasjon

---

### US-011: CRUD for serviceavtaler

**Prioritet:** high
**Avhenger av:** US-010

**Beskrivelse:**
Admin-bruker skal kunne opprette og administrere serviceavtaler knyttet til en lokasjon. Avtaler definerer hva slags service som skal utføres og hvor ofte.

**Akseptansekriterier:**
- [ ] `POST /service-contracts` oppretter en avtale knyttet til en lokasjon
- [ ] `GET /service-contracts` lister avtaler (filtrering: location_id, customer_id, is_active)
- [ ] `GET /service-contracts/{id}` returnerer avtale med lokasjon- og kundeinfo
- [ ] `PUT /service-contracts/{id}` oppdaterer avtale
- [ ] `DELETE /service-contracts/{id}` deaktiverer avtale (soft delete via `is_active=false`)
- [ ] Felt: service_type, interval_months, next_due_date, sla_hours
- [ ] Automatisk beregning av `next_due_date` basert på `interval_months`
- [ ] Pydantic-schemas: `ServiceContractCreate`, `ServiceContractUpdate`, `ServiceContractResponse`
- [ ] Repository + Service-lag
- [ ] Tester: CRUD, filtrering, datoberegning, cross-tenant isolasjon

---

### US-012: CRUD for jobber (serviceoppdrag)

**Prioritet:** high
**Avhenger av:** US-011

**Beskrivelse:**
Systemet skal kunne opprette og administrere individuelle servicejobber basert på serviceavtaler. Jobber har en livssyklus fra uplanlagt til fullført.

**Akseptansekriterier:**
- [ ] `POST /jobs` oppretter en jobb (manuelt eller basert på kontrakt)
- [ ] `GET /jobs` lister jobber (filtrering: status, customer_id, region)
- [ ] `GET /jobs/{id}` returnerer jobb med kontrakts- og lokasjonsinformasjon
- [ ] `PUT /jobs/{id}` oppdaterer jobb (tittel, beskrivelse)
- [ ] `PATCH /jobs/{id}/status` endrer jobbstatus med validering av tillatte overganger
- [ ] Tillatte statusoverganger: unscheduled→scheduled, scheduled→in_progress, in_progress→completed, *→cancelled
- [ ] Pydantic-schemas: `JobCreate`, `JobUpdate`, `JobStatusUpdate`, `JobResponse`
- [ ] Repository + Service-lag
- [ ] Tester: CRUD, statusoverganger (gyldige og ugyldige), cross-tenant isolasjon

---

### US-013: Generering av jobber fra serviceavtaler

**Prioritet:** medium
**Avhenger av:** US-012

**Beskrivelse:**
Systemet skal automatisk kunne generere jobber basert på serviceavtaler der `next_due_date` er innen en gitt horisont. Dette er kjernelogikken for planlegging.

**Akseptansekriterier:**
- [ ] `POST /jobs/generate` genererer jobber for avtaler der `next_due_date <= today + horisont`
- [ ] Horisontparameter (default 30 dager) kan angis i request
- [ ] Duplikatsjekk: ikke opprett jobb hvis uplanlagt/planlagt jobb allerede finnes for avtalen
- [ ] `next_due_date` oppdateres på avtalen etter jobbgenerering
- [ ] Returnerer antall genererte jobber og liste over jobb-IDer
- [ ] Service: `JobGenerationService` med dedikert forretningslogikk
- [ ] Tester: generering, duplikatsjekk, datooppdatering, ingen jobber utenfor horisont

---

### US-014: Paginering og filtrering (felles)

**Prioritet:** medium
**Avhenger av:** US-007–US-012

**Beskrivelse:**
Alle list-endepunkter skal støtte konsistent paginering og filtrering.

**Akseptansekriterier:**
- [ ] Felles pagineringsschema: `PaginatedResponse[T]` med `items`, `total`, `page`, `page_size`
- [ ] Query-parametere: `page` (default 1), `page_size` (default 20, max 100)
- [ ] Sortering: `sort_by` og `sort_order` (asc/desc)
- [ ] Alle list-endepunkter bruker felles pagineringsmønster
- [ ] Tester: paginering med ulike sider, sortering, tomme resultater

---

### US-015: Bulk-import av kunder/lokasjoner (CSV)

**Prioritet:** medium
**Avhenger av:** US-010

**Beskrivelse:**
Admin-bruker skal kunne laste opp CSV-fil med kunder og lokasjoner for å raskt sette opp data. Bruker `import_jobs`-tabellen for sporing.

**Akseptansekriterier:**
- [ ] `POST /import/customers` aksepterer CSV-filopplasting
- [ ] CSV-format: customer_name, org_number, contact_email, address, city, postal_code
- [ ] Validering per rad med detaljert feilrapportering
- [ ] ImportJob opprettes med status `pending` → `processing` → `completed`/`failed`
- [ ] `GET /import/{id}` returnerer importstatus med feillogg
- [ ] Eksisterende kunder (basert på org_number) oppdateres, nye opprettes
- [ ] Service: `ImportService` med radvis prosessering
- [ ] Tester: gyldig import, valideringsfeil, duplikathåndtering

---

### US-016: Audit-logging

**Prioritet:** medium
**Avhenger av:** US-007–US-012

**Beskrivelse:**
Alle muterende operasjoner (opprett, oppdater, slett) skal logges i `audit_events`-tabellen for sporbarhet.

**Akseptansekriterier:**
- [ ] Audit-event opprettes ved create/update/delete på alle ressurser
- [ ] Felt: user_id, action (create/update/delete), resource_type, resource_id, metadata (JSON diff)
- [ ] `GET /audit-events` lister hendelser (filtrering: resource_type, user_id, dato)
- [ ] Kun `org:admin` kan se audit-logg
- [ ] Service/middleware: `AuditService` som kalles fra service-laget
- [ ] Tester: logging ved CRUD-operasjoner, filtrering

---

### US-017: Frontend — layout og navigasjon

**Prioritet:** high
**Avhenger av:** US-007–US-009

**Beskrivelse:**
Sett opp Jinja2 + HTMX + Alpine.js + Tailwind-basert frontend med felles layout, navigasjon og innloggingsside.

**Akseptansekriterier:**
- [ ] Base-template med Tailwind CSS (CDN eller lokal build)
- [ ] Responsiv sidebar-navigasjon med menyvalg: Dashboard, Regioner, Teknikere, Kunder, Jobber
- [ ] Login-side med e-post/passord-skjema (og Auth0-knapp hvis konfigurert)
- [ ] Dashboard-side med placeholder-innhold
- [ ] HTMX-oppsett for partial page updates
- [ ] Alpine.js for enkel klientside-interaktivitet
- [ ] Autentisert bruker vises i header med rolle
- [ ] Redirect til login ved 401

---

### US-018: Frontend — kundeliste og -skjema

**Prioritet:** medium
**Avhenger av:** US-017, US-009

**Beskrivelse:**
HTMX-basert kundeliste med søk, paginering og opprett/rediger-skjema.

**Akseptansekriterier:**
- [ ] `/customers`-side viser paginerbar kundeliste
- [ ] Søkefelt filtrerer kunder med HTMX (debounced)
- [ ] «Ny kunde»-knapp åpner skjema (inline eller modal via HTMX)
- [ ] Opprett/rediger-skjema med validering og feilmeldinger
- [ ] Slette-knapp med bekreftelsesdialog
- [ ] Responsivt design (mobil + desktop)

---

## Manuelle handlinger (fra Fase 1, fortsatt gjeldende)

| # | Handling | Hvor |
|---|----------|------|
| M-1 | Bytt Supabase-databasepassord | supabase.com → Settings → Database |
| M-2 | Oppdater DATABASE_URL i Railway | railway.app → FieldFlow → Variables |
| M-3 | Restart Railway deployment | railway.app → Deployments → Redeploy |
| M-4 | Kontakt Hedengren IT for WSL2-godkjenning | Intern IT-support |

---

## Fremgangstabell — Fase 2

| ID | Tittel | Prioritet | Avhenger av | Status |
|----|--------|-----------|-------------|--------|
| US-007 | CRUD for regioner | high | — | TODO |
| US-008 | CRUD for teknikere | high | US-007 | TODO |
| US-009 | CRUD for kunder | high | — | TODO |
| US-010 | CRUD for lokasjoner | high | US-009 | TODO |
| US-011 | CRUD for serviceavtaler | high | US-010 | TODO |
| US-012 | CRUD for jobber | high | US-011 | TODO |
| US-013 | Generering av jobber fra avtaler | medium | US-012 | TODO |
| US-014 | Paginering og filtrering (felles) | medium | US-007–012 | TODO |
| US-015 | Bulk-import kunder/lokasjoner | medium | US-010 | TODO |
| US-016 | Audit-logging | medium | US-007–012 | TODO |
| US-017 | Frontend — layout og navigasjon | high | US-007–009 | TODO |
| US-018 | Frontend — kundeliste og skjema | medium | US-017, US-009 | TODO |

---

## Anbefalt rekkefølge

**Sprint 1 (CRUD-grunnlag):**
1. US-007 — Regioner
2. US-009 — Kunder (parallelt med US-007)
3. US-008 — Teknikere
4. US-010 — Lokasjoner

**Sprint 2 (Serviceoppdrag):**
5. US-011 — Serviceavtaler
6. US-012 — Jobber
7. US-013 — Jobbgenerering

**Sprint 3 (Kvalitet + Frontend):**
8. US-014 — Paginering/filtrering
9. US-016 — Audit-logging
10. US-015 — CSV-import
11. US-017 — Frontend layout
12. US-018 — Frontend kundeliste
