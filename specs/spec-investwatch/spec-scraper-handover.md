---
title: 'Scraper: oddanie danych do pipeline''u w kontrakcie v2 bez duplikatów'
type: 'feature'
created: '2026-11-22'
status: 'done'
baseline_commit: '48b42fa'
context: ['docs/data-contract.md', 'docs/scraper-integration.md', 'scraper/README.md', 'data/scraped/README.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Scraper ma własny kształt danych (Postgres `posts`, `media`), a pipeline czyta nasz kontrakt v2 z historią obserwacji. Scraper pójdzie na cron, ale na potrzeby projektu jest odpalany ad hoc. Jego wynik nie może duplikować niczego w naszym storage'u, a próbki zebranych danych mają trafić do MinIO w naszym formacie.

**Approach:** Nasz kontrakt jest ważniejszy: adapter po stronie scrapera (`app/landing.py`) zapisuje posty do bucketa `investwatch` po każdym jobie, a konwersja i zapis są we wspólnym module `common` (też dla seeda). Klucze zależą tylko od treści, więc duplikaty są wykluczone z konstrukcji.

## Boundaries & Constraints

**Always:**
- Kontrakt v2 bez zmian; scraper dopasowuje się do niego. Obiekty niezmienne, klucze `raw/{platform}/{external_id}/{hash12}.json` i `images/{sha256}.ext`.
- Zapis pomija wszystko, co już jest w buckecie (nasze dane, wcześniejsze synchronizacje); obrazy zapisywane przed obiektem.
- Awaria przekazania nie przerywa joba scrapera (`LANDING_SYNC=false` wyłącza hook).
- Zmiany w `scraper/` ograniczone do adaptera, ustawień i testów; reszta kodu współpracownika bez refaktorów (poza wyodrębnieniem `post_row` z eksportu).
- Bramki: testy, ruff dla nowych plików, audyt zależności; CI uruchamia testy scrapera.

**Ask First:** zmiany w kolektorach, schemacie bazy scrapera, nowe zależności scrapera.

**Never:** nadpisywanie obiektów landing, usuwanie danych z bucketa, uruchamianie cronu scrapera w domyślnym stacku.

## I/O & Edge-Case Matrix

| Scenariusz | Wejście / stan | Oczekiwane zachowanie | Obsługa błędów |
|---|---|---|---|
| Pierwszy sync | posty w bazie scrapera | po jednym obiekcie na wersję, obrazy raz (po sha256) | brak pliku w MinIO scrapera: wyjątek, hook go loguje |
| Drugi sync, bez zmian | te same posty | zero zapisów | n/a |
| Zmieniony post | nowy wiersz `post_versions` | jeden nowy obiekt, stare zostają | n/a |
| Próbki z `data/scraped` | eksport (JSONL + media) | te same klucze co sync z bazy | brak katalogu: pomijane |
| Post bez treści i obrazów | pusta treść | pominięty (kontrakt wymaga treści albo obrazu) | n/a |
| Moduł 1 | zapytanie z aliasem marki | `advertised_firm` = marka (najdłuższy alias, całe słowo) | bez aliasu: pusta |

</frozen-after-approval>

## Code Map

- `common/investwatch_common/landing.py` -- `convert`, `Landing`, `firm_for`, `iter_export` (stdlib).
- `scraper/app/{landing,jobs,main,settings,dataset}.py` -- hook po jobie, `POST /landing/sync`, CLI, `PIPELINE_S3_BUCKET`, `post_row`.
- `demo/seed/seed.py`, `docker-compose.yml` -- próbki `data/scraped` do bucketa przy starcie.
- `scraper/tests/`, `demo/seed/tests/test_scraped.py` -- testy.

## Tasks & Acceptance

- [x] Merge `origin/main` (scraper), konflikt tylko w README (zostaje nasz)
- [x] Wspólny adapter, hook po jobie, endpoint i CLI, ustawienia
- [x] Seed ładuje próbki scrapera; CI i dokumentacja

**Acceptance Criteria:**
- Given próbki `data/scraped/`, when startuje `seed` drugi raz, then `objects_new: 0` i `images_new: 0`.
- Given sync z bazy scrapera po imporcie tych samych próbek, then adapter nie tworzy nowych obiektów względem seeda.
- Given post M2, when trafia do pipeline'u, then ma obrazy `desktop` i `mobile` (reguła 8) i firmę z nazwy wydawcy.

## Verification

- `cd scraper && uv run pytest -q`; `cd demo/seed && uv run pytest -q`; `scripts/smoke.sh`
- Stack z próbkami: 67 rekordów po dwóch "Odśwież dane" (limit batcha 50), trzeci refresh bez przeliczania.
