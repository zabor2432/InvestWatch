# Scraper: integracja z pipeline'em

Stan: scraper (`scraper/`, `common/`, `migrations/`, autor: współpracownik) jest **wpięty przez kontrakt danych v2**. Wyłączony domyślnie (`COMPOSE_PROFILES=scraper`).
Nasz kontrakt (`docs/data-contract.md`) jest ważniejszy niż jego tabele: scraper dostosowuje się do niego, a nie odwrotnie.

## Przepływ

```
scraper (joby, cron)  ->  Postgres scrapera (posts, versions, media) + MinIO investwatch-media
        |  po każdym jobie (LANDING_SYNC) albo POST /landing/sync
        v
adapter scraper/app/landing.py  ->  MinIO investwatch: raw/{platform}/{id}/{hash12}.json + images/{sha256}.ext   (kontrakt v2)
        v
Dagster (intake_items -> documents -> analysis_batch -> ...)  ->  dashboard
```

- Co dostaje pipeline: patrz tabela mapowania w `docs/data-contract.md` (sekcja Scraper).
- **Bez duplikatów**: klucze zależą tylko od treści (`hash12`, sha256 obrazu). Adapter listuje, co już jest w buckecie (nasze dane, wcześniejsze synchronizacje, seed), i pomija to; zmieniony post dodaje jeden obiekt (nowa wersja), starych nie rusza. Zweryfikowane: ten sam wynik z bazy scrapera i z eksportu `data/scraped/`.
- Kod: `scraper/app/landing.py` (baza → bucket, CLI, hook) i `common/investwatch_common/landing.py` (konwersja i zapis, tylko biblioteka standardowa, używane też przez seed). Testy: `scraper/tests/`, `demo/seed/tests/test_scraped.py`.

## Uruchomienie ad hoc (na potrzeby projektu)

```bash
COMPOSE_PROFILES=scraper docker compose up -d --build
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_sync"}'        # najpierw rejestr firm
curl -X POST localhost:8001/jobs/run-all -H 'content-type: application/json' -d '{"limit":3}'            # jeden przebieg jak cron
# nowe posty trafiają do bucketa investwatch same; potem w dashboardzie "Odśwież dane"
```

Na cronie działa to samo (`SCRAPE_CRON`), a wynik czeka w buckecie do następnego "Odśwież dane" (start modeli zostaje ręczny).

## Próbki zebranych danych

`data/scraped/<data>/` (eksport scrapera: `posts.jsonl`, `media/`). `docker compose up` ładuje je do bucketa `investwatch` przez usługę `seed` (ten sam adapter), więc po "Odśwież dane" są w dashboardzie obok danych demo.

## Znane ograniczenia

1. Firma M1 wynika z aliasu w zapytaniu, nie z treści posta; zapytania bez aliasu marki dają pustą firmę (obserwacja po samym podmiocie).
2. Zrzuty to pierwszy ekran strony (desktop 1366x768, mobile 390x844). Nie przekazujemy jeszcze `raw.layout` (style bloków z ryzykiem, reguły 4-8, 13) ani bloków `focus: risk`; to naturalny następny krok dla M2.
3. Wideo: tylko miniatura i transkrypt; transkrypt YouTube bywa niedostępny (429).
4. Wszystkie wersje posta dostają te same obrazy (scraper nie trzyma mediów per wersja).
5. Rejestr firm i wykluczenia właścicieli (`owners.py`) działają po stronie scrapera, pipeline ich nie powiela.
