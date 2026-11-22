# Kontrakt danych wejściowych (v2)

Granica między źródłami (demo, scraper, ręczne zbieranie) a pipeline'em. Źródło prawdy: `orchestrator/pipeline/contract.py`
(Pydantic `IntakeItem`), JSON Schema w [`intake-item.schema.json`](intake-item.schema.json) jest z niego generowany
(`cd orchestrator && uv run python -m pipeline.contract > ../docs/intake-item.schema.json`; test pilnuje zgodności).
Źródło, które chce trafić do pipeline'u, pisze ten kształt i nic więcej; reszta systemu nie zna scrapera.

## Warstwa landing (MinIO, bucket `investwatch`)

- Obiekt `raw/{platform}/{external_id}/{hash12}.json` jest **niezmienny**. Zmiana treści materiału to nowy obiekt (nowa wersja), nigdy nadpisanie.
- Obrazy leżą w tym samym buckecie (`images/...`), obiekt wskazuje je kluczem i sumą SHA-256.
- Obiekt niezgodny z kontraktem trafia do kwarantanny (`intake_rejections`, powód zapisany) i nie jest walidowany ponownie.

## Pola

| Pole | Znaczenie |
|---|---|
| `schema_version` | zawsze `2` |
| `source` | `system` (`demo`/`scraper`/`manual`), `platform`, `external_id` (stabilny u źródła), `url`; `platform:external_id` to klucz dokumentu |
| `module` | `third_party_ads` (M1), `self_promotion` (M2), `non_investment_companies` (M3) |
| `observation` | `advertiser {handle, name?, url?}` i `advertised_firm` (pusty, gdy nie dotyczy); para to **obserwacja**, jej materiały tworzą historię |
| `published_at`, `captured_at` | kiedy opublikowano u źródła (jeśli znane) i kiedy zebrano tę wersję |
| `title`, `text`, `lang` | treść; wymagany jest tekst albo obraz |
| `images[]` | `key`, `sha256`, `variant` (`desktop`/`mobile`/`tablet`/`original`), `focus` (`page` albo `risk` = wycięty blok z informacją o ryzyku), `width`, `height` |
| `label` | etykieta referencyjna (naruszenie), tylko dane testowe; służy do kalibracji progu |
| `manipulated` | `{rules[], recipe}` dla kontrolowanych wariantów testowych (celowo zepsuta reguła); w UI znacznik „zmanipulowany” |

## Co z tym robi Dagster

`intake_items` (nowe obiekty spoza ledgera + walidacja) → `documents` (obserwacje, dokumenty, obrazy, ledger `ingestions`) → `analysis_batch` → moduły AI.

- Wersja treści = hash tekstu i sum wszystkich obrazów. Ten sam hash: nic się nie dzieje (`unchanged`); inny: dokument dostaje nową wersję (`changed`) i jest oceniany od nowa.
- Wyniki są per (dokument, moduł, model, wersja treści); stare wersje i wyniki zostają w bazie.
- `analysis_batch` ma konfigurację (Launchpad w Dagsterze; domyślne z `.env`): `batch_size` (`BATCH_SIZE`), `reprocess_lookback_days` (`REPROCESS_LOOKBACK_DAYS`), `modules`.
  Nowe i zmienione wersje bierze zawsze. Dokumenty już ocenione innym modelem przelicza tylko, gdy `published_at` (a bez niego `captured_at`) mieści się w oknie wstecz; po zmianie `JEV_MODEL` stare materiały poza oknem zostają przy starym wyniku.
- Metadane assetu pokazują liczniki: `fresh`, `reprocess_in_window`, `skipped_outside_window`, `selected`, `deferred_by_batch_size`.
- Reguła 8 (responsywność) jest oceniana tylko, gdy rekord ma obraz `desktop` i `mobile`; w przeciwnym razie ma wynik „nie dotyczy”.

## Skąd bierze się `hash12` i obrazy

`hash12` to pierwsze 12 znaków hex z sha256 listy `[title, text, [sha256 obrazów]]` (JSON). Obrazy to `images/{sha256}{ext}`. Oba klucze zależą tylko od treści,
więc każdy producent (seed, scraper) liczy je tak samo i ponowny zapis tego samego materiału nie tworzy nowego obiektu. Implementacja: `common/investwatch_common/landing.py`.

## Scraper

Scraper zapisuje do tego kontraktu po każdym jobie (adapter `scraper/app/landing.py`, wyłączany `LANDING_SYNC=false`) albo na żądanie (`POST /landing/sync`,
`python -m app.landing from-export <katalog>`). Mapowanie:

| Pole kontraktu | Z posta scrapera |
|---|---|
| `source` | `system: scraper`, `platform`, `external_id`, `url` |
| `module` | `first_task`: `registry_ads` → M1, `firm_marketing` → M2, `shadow_advisory` → M3 |
| `observation.advertiser` | `author_handle` (a bez niego host z URL), `author_display_name`, `author_url` |
| `observation.advertised_firm` | M2: wydawca (nazwa autora); M1: marka, której alias (najdłuższy) występuje w zapytaniu (`config/brand_aliases.json`); M3: pusta |
| `published_at`, `captured_at` | `published_at`; `captured_at` wersji z `post_versions` |
| `title`, `text`, `lang` | `title`; `content` + `transcript`; `lang` |
| `images[]` | `media`: zrzuty `screenshot:desktop|mobile:...` → `desktop`/`mobile`, inne obrazy i miniatury → `original`; wszystkie z `focus: page` |
| `meta.scraper` | `first_task`, `first_query`, `first_job_id`, `engagement`, `outbound_links` |

Każda wersja treści posta to osobny obiekt (historia), obrazy dostają wszystkie wersje (scraper nie trzyma mediów per wersja), więc nowa wersja jest jedynym nowym obiektem.
Nie przekazujemy jeszcze `raw.layout` (style bloków z ryzykiem) ani bloków `focus: risk`.
