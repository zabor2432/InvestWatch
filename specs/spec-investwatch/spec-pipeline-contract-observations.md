---
title: 'Pipeline: kontrakt danych v2, obserwacje z historią, parametryzowana ingestia, odświeżanie z UI'
type: 'feature'
created: '2026-11-22'
status: 'done'
baseline_commit: '212d4a7'
context: ['docs/architecture.md', 'docs/scraper-integration.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Wejście pipeline'u to płaskie pliki z jednym obrazem i bez historii. Nie da się "obserwować" pary (podmiot, firma), ocenić responsywności (reguła 8), ani sterować tym, co trafia do modelu. Scraper (współpracownik) zaraz się zmieni, a dane z internetu są potrzebne do testów.

**Approach:** Własny kontrakt wejścia (warstwa landing w MinIO + ledger w Postgresie), do którego scraper dostosuje się adapterem. Dagster ma parametry ingestii (rozmiar batcha, okno przeliczania wstecz po zmianie modelu). Przycisk w UI uruchamia run. Zbiór testowy z publicznych stron zbiera osobne narzędzie dev.

## Boundaries & Constraints

**Always:**
- Obiekt landing jest niezmienny; zmiana treści to nowy obiekt i nowa wersja dokumentu. Wyniki per (dokument, moduł, model, wersja treści).
- Źródło prawdy kontraktu: `orchestrator/pipeline/contract.py`; JSON Schema generowany i sprawdzany testem.
- Nic nie startuje samo (bez sensorów i harmonogramów): Dagster UI albo przycisk "Odśwież dane".
- Zbiór z internetu: tylko publiczne strony pierwotne, poza gitem (`demo/collected/`); warianty zmanipulowane oznaczone w danych i w UI.

**Ask First:** zmiany w `scraper/` (współpracownik), nowe zewnętrzne usługi, retencja i dane osobowe.

**Never:** płatne API, nadpisywanie obiektów landing, ocena cudzych treści jako rozstrzygnięć KNF (etykiety to oceny autora z uzasadnieniem).

## I/O & Edge-Case Matrix

| Scenariusz | Wejście / stan | Oczekiwane zachowanie | Obsługa błędów |
|---|---|---|---|
| Nowy materiał | obiekt spoza ledgera | dokument + obserwacja + obrazy + wpis ledgera, ocena modelem | niepoprawny kontrakt: `intake_rejections`, run trwa |
| Zmieniona treść | ten sam `platform:external_id`, inny hash | nowa wersja dokumentu, nowa ocena, stare wyniki zostają | starszy `captured_at` niż bieżący: tylko ledger |
| Drugi "Odśwież dane" bez nowych danych | brak zmian | zero wywołań modelu | trwający run: zwrócony ten sam run, bez drugiego |
| Zmiana modelu | `JEV_MODEL` inny | przeliczane dokumenty z okna wstecz (`reprocess_lookback_days`), starsze zostają | brak |
| Reguła 8 | rekord z obrazem desktop i mobile | pytanie o czytelność ryzyka na telefonie vs komputer | bez pary: "nie dotyczy" |
| Dagster niedostępny | klik "Odśwież dane" | toast z błędem, lista bez zmian | `POST /api/refresh` zwraca 502 |

</frozen-after-approval>

## Code Map

- `db/init.sql` -- `observations`, `documents`, `document_images`, `ingestions`, `intake_rejections`, `results`.
- `orchestrator/pipeline/{contract,store,definitions,analyze,rules}.py` -- kontrakt, ledger i wybór batcha, graf assetów, reguła 8.
- `backend/app/{refresh,records,main,schemas}.py` -- Dagster GraphQL, rekord z obserwacją i obrazami, `/api/refresh`, `/api/records/{id}/images/{variant}`.
- `frontend/src/` -- przycisk, Desktop/Mobile, historia, znacznik "zmanipulowany".
- `demo/seed`, `demo/collect` -- źródła: dane demo i zbiór z publicznych stron.

## Tasks & Acceptance

- [x] Model danych, kontrakt v2, ingestia z ledgerem, `IngestConfig` (`orchestrator/`)
- [x] Backend: refresh przez GraphQL, obrazy wg wariantu, historia obserwacji
- [x] Frontend: przycisk, podgląd obrazów, historia, znacznik
- [x] Seed w kontrakcie v2, `demo/collect` (manifest, kolektor, 14 przepisów manipulacji, ewaluacja)

**Acceptance Criteria:**
- Given pusty stack, when klikam "Odśwież dane", then lista wypełnia się, a drugi klik niczego nie przelicza (`scripts/smoke.sh`).
- Given obserwację z 3 materiałami, when otwieram jeden, then widzę pozostałe w "Historii obserwacji".
- Given rekord z obrazami desktop i mobile, when jest oceniany, then reguła 8 ma wynik; bez pary ma "nie dotyczy".
- Given zmianę modelu i okno 5 dni, when startuje run, then przeliczone są tylko dokumenty z ostatnich 5 dni.

## Verification

- `cd orchestrator && uv run pytest -q`; `cd backend && DATABASE_URL=x uv run pytest -q`; `cd frontend && npm test`
- `COMPOSE=podman-compose scripts/smoke.sh` (albo `docker compose` bez zmiennej)
- Niezweryfikowane: jakość prawdziwego modelu na zebranym zbiorze (`demo/collect/evaluate.py`).
