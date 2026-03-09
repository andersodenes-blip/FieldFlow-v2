# FieldFlow v2 — PRD Fase 1 (Ralph Loop)

Prosjekt: FieldFlow v2  
Repo: andersodenes-blip/FieldFlow-v2  
Deployment: Railway (auto-deploy fra GitHub)  
Stack: FastAPI + SQLAlchemy + Alembic + Supabase (PostgreSQL) + Auth0

---

## Regler for Ralph

- Jobb på én task om gangen
- Commit etter hver fullført task med beskrivende melding
- Oppdater `progress.txt` etter hver task: merk `[DONE]` eller `[BLOCKED]`
- Hvis en task er blokkert av menneskelig handling, merk den `[BLOCKED – HUMAN]` og gå til neste
- Når alle tasks har `passes: true`, output `<promise>COMPLETE</promise>`

---

## User Stories

```json
{
  "userStories": [
    {
      "id": "US-001",
      "title": "Bytt Supabase-databasepassord",
      "priority": "critical",
      "passes": false,
      "blocked": true,
      "blockedReason": "Krever manuell handling i Supabase-dashboard og Railway env vars",
      "description": "Det eksisterende Supabase-passordet ble eksponert i en chat-logg og må byttes umiddelbart.",
      "acceptanceCriteria": [
        "Nytt sterkt passord er satt i Supabase under Settings > Database > Reset password",
        "DATABASE_URL og alle relaterte env vars er oppdatert i Railway",
        "Railway-deployment er restartet og applikasjonen kobler til databasen uten feil",
        "Alembic-migrasjoner kjører uten feil mot ny tilkobling",
        "PgBouncer statement_cache_size=0 er fortsatt konfigurert i create_async_engine"
      ],
      "notes": "BLOKKERT – må gjøres manuelt av Anders i Supabase og Railway dashboard før Ralph kan verifisere."
    },
    {
      "id": "US-002",
      "title": "Verifiser databasetilkobling etter passordbytte",
      "priority": "critical",
      "passes": false,
      "blocked": false,
      "description": "Etter at passord er byttet (US-001), verifiser at applikasjonen fungerer korrekt mot Supabase.",
      "acceptanceCriteria": [
        "GET /health returnerer 200 OK med database-status 'connected'",
        "Alembic kjører `alembic upgrade head` uten feil",
        "Eksisterende tabeller er intakte og data er bevart",
        "Railway-logger viser ingen tilkoblingsfeil"
      ],
      "dependsOn": "US-001"
    },
    {
      "id": "US-003",
      "title": "Docker/WSL2 lokal utviklingsmiljø",
      "priority": "high",
      "passes": false,
      "blocked": true,
      "blockedReason": "WSL2-oppdatering blokkert av Hedengren IT-policy — krever IT-hjelp",
      "description": "Sett opp Docker for lokalt utviklingsmiljø slik at FieldFlow kan kjøres uten direkte Railway-avhengighet under utvikling.",
      "acceptanceCriteria": [
        "docker-compose.yml er opprettet i repo-rot med services: api, db (PostgreSQL lokal)",
        "`docker compose up` starter applikasjonen lokalt på port 8000",
        "Lokal PostgreSQL-instans brukes for utvikling (ikke Supabase prod)",
        ".env.example er oppdatert med alle nødvendige variabler for lokal kjøring",
        "README.md inneholder instruksjoner for lokal Docker-oppsett",
        "Applikasjonen på localhost:8000/docs viser Swagger UI"
      ],
      "notes": "BLOKKERT – WSL2-oppdatering krever IT-godkjenning hos Hedengren. Lag docker-compose.yml og dokumentasjon, men kan ikke testes lokalt uten IT-hjelp. Marker som done når filer er på plass."
    },
    {
      "id": "US-004",
      "title": "Auth0 Organizations — grunnoppsett",
      "priority": "high",
      "passes": false,
      "blocked": false,
      "description": "Konfigurer Auth0 Organizations slik at FieldFlow kan støtte multi-tenant (én org per kunde/selskap).",
      "acceptanceCriteria": [
        "Auth0 Organizations er aktivert i Auth0 dashboard under tenant-innstillinger",
        "En test-organisasjon 'hedengren-test' er opprettet i Auth0",
        "AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_AUDIENCE er lagt til Railway env vars",
        "FastAPI har en /auth/login og /auth/callback route som håndterer Auth0 OIDC-flow",
        "JWT-token fra Auth0 valideres korrekt i FastAPI med org_id i claims",
        "Uautoriserte requests mot beskyttede ruter returnerer 401"
      ]
    },
    {
      "id": "US-005",
      "title": "Auth0 Organizations — bruker/org-mapping i database",
      "priority": "high",
      "passes": false,
      "blocked": false,
      "description": "Lagre organisasjons- og brukertilhørighet fra Auth0 i Supabase slik at FieldFlow vet hvilken org en bruker tilhører.",
      "acceptanceCriteria": [
        "Alembic-migrasjon oppretter tabell `organizations` (id, auth0_org_id, name, created_at)",
        "Alembic-migrasjon oppretter tabell `users` (id, auth0_user_id, email, org_id FK, role, created_at)",
        "Ved første innlogging opprettes bruker automatisk i `users`-tabellen",
        "org_id fra Auth0 JWT-token matches mot `organizations`-tabellen",
        "GET /me returnerer innlogget brukers info inkl. organisasjon",
        "Migrasjoner kjører rent på Railway uten feil"
      ],
      "dependsOn": "US-004"
    },
    {
      "id": "US-006",
      "title": "Auth0 Organizations — rollebasert tilgangskontroll (RBAC)",
      "priority": "medium",
      "passes": false,
      "blocked": false,
      "description": "Implementer enkelt RBAC så admin-brukere i en org kan se og administrere data, mens vanlige brukere kun ser sin egen org sine data.",
      "acceptanceCriteria": [
        "Roller definert i Auth0: `org:admin` og `org:member`",
        "FastAPI dependency `require_role('org:admin')` er implementert",
        "Admin-ruter er beskyttet og returnerer 403 for org:member",
        "All datahenting filtreres på org_id — brukere kan ikke se andre orgers data",
        "Tester verifiserer at cross-org datalekkasje ikke er mulig"
      ],
      "dependsOn": "US-005"
    }
  ]
}
```

---

## Manuelle handlinger (ikke for Ralph)

Disse tasks kan **ikke** automatiseres og må gjøres av Anders manuelt:

| # | Handling | Hvor |
|---|----------|------|
| M-1 | Bytt Supabase-databasepassord | supabase.com → Settings → Database |
| M-2 | Oppdater DATABASE_URL i Railway | railway.app → FieldFlow → Variables |
| M-3 | Restart Railway deployment | railway.app → Deployments → Redeploy |
| M-4 | Kontakt Hedengren IT for WSL2-godkjenning | Intern IT-support |
| M-5 | Aktiver Auth0 Organizations i dashboard | manage.auth0.com → Organizations |

---

## Fremgang

Oppdater denne filen etter hver task:

- [ ] US-001 — Bytt Supabase-passord `[BLOCKED – HUMAN]`
- [ ] US-002 — Verifiser tilkobling
- [ ] US-003 — Docker/WSL2 oppsett `[BLOCKED – HUMAN for testing]`
- [ ] US-004 — Auth0 grunnoppsett
- [ ] US-005 — Bruker/org-mapping
- [ ] US-006 — RBAC
