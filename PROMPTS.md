# FieldFlow v2 - Prompt-maler for Claude Code

## Fiks en bug

```
Det er en feil: [BESKRIV FEIL].
Relevante filer: [FILER].
Fiks feilen, kjor tester, og gi meg PowerShell-kommandoer for commit.
```

## Legg til feature

```
Legg til folgende feature: [BESKRIV].
Folg eksisterende monstre i [REFERANSEFIL].
Lag tester, og gi meg PowerShell-kommandoer for commit.
```

## Kjor ruteplanlegging

```
Slett eksisterende ruter for [REGION/alle] og kjor ny planlegging
for periode [DATO]-[DATO]. Bruk scripts/test_route_planning_live.py.
Vis oppsummering og 7.5t-verifisering.
```

## Debug Railway

```
Railway gir feil: [KOPIER FEILMELDING].
Finn arsaken i koden og fiks den.
Gi meg PowerShell-kommandoer for commit og push.
```

## Ny migrasjon

```
Legg til kolonne [KOLONNE] av type [TYPE] pa tabell [TABELL].
Lag Alembic-migrasjon, oppdater SQLAlchemy-modellen og schema.
Gi meg: python -m alembic upgrade head
```

## Oppdater dashboard

```
Les v1-dashboardet i [FIL] og sammenlign med v2 dashboard.html.
[BESKRIV ENDRING].
Bruk eksakt samme CSS-fargepalett som v1.
```

## Importer data fra v1

```
Importer [DATATYPE] fra v1 Excel-fil [FILNAVN].
Bruk scripts/import_v1_master.py som referanse.
Verifiser med en SELECT-sporring etterpaa.
```

## Endre ruteplanleggingslogikk

```
Gjeldende logikk i app/services/route_planning_service.py:
[BESKRIV NAVARENDE OPPFORSEL].

Onsket oppforsel: [BESKRIV].
Referanse fra v1: [KODEEKSEMPEL].

Fiks, kjor scripts/test_stavanger.py, og verifiser ingen dag > 7.5t.
```
