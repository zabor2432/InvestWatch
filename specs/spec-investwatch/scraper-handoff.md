# Scraper InvestWatch — stan prac i kontekst do kontynuacji

Stan na 2026-11-21. Kod zmergowany do `main` (PR #3, branch `feat/baltruszewiczwb/scraper`).
Zasady pracy: **nie commitować bez review użytkownika**; branche zakłada użytkownik.

## Cel

POC scrapera dla zadania UKNF (`UKNF/UKNF - Pełna treść zadania konkursowego.pdf`), z dwoma zadaniami:

| Task | Moduł | Co szuka |
|---|---|---|
| `registry_ads` | 1 | reklam firm z rejestru KNF (finfluencerzy, podmioty trzecie) |
| `shadow_advisory` | 3 | ofert doradztwa / wealth management / sygnałów podmiotów bez zezwolenia |
| `registry_sync` | — | odświeżenie rejestru firm (KNF + I-SCAN) |

Scraper **tylko zbiera** dane. Klasyfikacja (dopasowanie do rejestru, ocena reklamy, LLM) należy do osobnego modułu AI, który nie powstał.

## Uzgodnione decyzje (sesja „grill-me”)

- **Źródła:**
  - działają: YouTube (`yt-dlp`), Telegram (`t.me/s/<kanał>`), WWW (SearXNG + `trafilatura`, Playwright jako fallback), Reddit (OAuth), Wykop (API v3);
  - stuby: FB, IG, X (`CollectorUnavailable`).
- **Discovery tylko przez zapytania** z plików w `scraper/config/`, bez ręcznych watchlist. Telegram nie ma wyszukiwania, więc kanały znajdujemy przez SearXNG `site:t.me <fraza>`.
- **Aliasy:** firma musi być w KNF, ale może mieć dowolne aliasy, także spoza KNF (np. xStation → XTB). Do zapytań idą **wszystkie** aliasy, także ≤4 znaki. Po firmach, których nie ma w KNF, nie szukamy.
- **Moduł 3:** bez krypto. Zapytania to najpierw frazy (`m3_phrases.yaml`, priorytet), potem nazwy i domeny z list: ostrzeżenia KNF, cofnięte zezwolenia, I-SCAN.
- **Filtry:** tylko treści po polsku (`lingua`), okno 90 dni (strony WWW bez daty zapisujemy zawsze). `robots.txt` jest ignorowany (decyzja użytkownika).
- **Media:** obrazy z postów zapisujemy do MinIO. Z wideo bierzemy tylko miniaturkę i transkrypcję; wideo nie jest pobierane.
- **Duplikaty:** upsert po `(platform, external_id)`. Zmiana `content_hash` tworzy nowy wiersz w `post_versions`.
- **Kolejka i harmonogram:** RQ + Redis. Cron jest wątkiem w `scraper-worker`, konfigurowany z `.env`. Joby można też odpalać ręcznie przez API.
- **Baza i migracje:**
  - jeden schemat bazy, modele w `common/`, kopiowanym do kontenerów przez `additional_contexts` (bez monorepo);
  - migracje robi Alembic w osobnym serwisie `migrations`, który wykonuje `upgrade head` i kończy działanie.
- **Zależności:** zarządzane przez **uv** (`pyproject.toml` + `uv.lock`, `uv sync --frozen`).
- **Logi:** JSON na stdout (`structlog`), bez sekretów i treści postów. Testy: nie piszemy (decyzja).

## Architektura / pliki

```
common/investwatch_common/   models.py (firms, scrape_jobs, posts, post_versions, post_hits, media),
                             enums.py, db.py (session_scope), text.py (normalize_name, extract_domains)
migrations/                  Alembic; alembic/versions/20261121_fb2ebbcab011_initial_scraper_schema.py
scraper/app/
  main.py                    FastAPI: /health, POST /jobs, POST /jobs/run-all, GET /jobs[/{id}], GET /posts[/{id}]
  queue.py, jobs.py          enqueue (wiersz scrape_jobs + RQ job o tym samym id), wykonanie joba
  worker.py, scheduler.py    RQ worker + cron (croniter, lock w Redis)
  queries.py                 generowanie zapytań + rotacja offsetu w Redis (MAX_QUERIES_PER_RUN)
  collectors/                base, youtube, telegram, web, searxng, reddit, wykop, stubs
  registry/                  knf.py (parsery stron KNF), iscan.py, records.py, sync.py, export.py (CLI)
  storage/                   repository.py (upsert/wersje/hity/media), blobs.py (MinIO, bucket public-read)
  http.py, lang.py, log.py, settings.py, models.py (RawPost)
scraper/config/              brand_aliases.json (49 marek, 109 aliasów), ad_phrases.yaml (3 szablony),
                             m3_phrases.yaml (26 fraz), user_agents.txt
searxng/settings.yml         SearXNG z formatem JSON, bez limitera
docs/firm_registry/          9 list rejestru (seed); scope_codes.json
scraper/README.md            opis endpointów
```

Serwisy compose: `db` (Postgres 16, port `${POSTGRES_HOST_PORT:-5432}` wystawiony), `migrations`, `redis`,
`minio` (`pgsty/minio`, bo oficjalny obraz MinIO nie jest już publikowany; konsola :9001), `searxng`,
`scraper` (:8001), `scraper-worker`.

## Rejestr (docs/firm_registry)

| Plik | Wpisów | Uwagi |
|---|---|---|
| brokerage_banks / brokerage_firms / foreign_investment_firms | 10 / 28 / 10 | KNF |
| foreign_investment_firms_without_branches | 712 | uzupełniony (był 106); KNF filtruje po `?firstLetter=` |
| credit_institutions_branches / _cross_border | 34 / 658 | dodane; tu są Trade Republic, Saxo, flatexDEGIRO |
| revoked_licences | 2 | KNF |
| knf_public_warnings | 474 | `dla_konsumenta/ostrzezenia_publiczne`; sekcje rynku kapitałowego; **brak dat** |
| iscan_warnings | 78 | IOSCO I-SCAN, `NCA_ID=75` (KNF), 24 mies. |

Szczegóły techniczne:
- KNF wymaga nagłówków przeglądarki (`Accept`, `Accept-Language`) i HTTP/1.1.
- Wykaz transgraniczny to JSON osadzony w stronie Next.js.
- HTML KNF ma błędy: `<strike> <br />B</strike>iuro…` — przekreślenia ≤2 znaków są ignorowane.

## Zweryfikowane na żywo (Docker, 2026-11-21)

- `registry_sync`: seed 1963 podmiotów, odświeżenie wszystkich 9 list (~2,5 min), bez błędów.
- `registry_ads` YouTube: działa (2 posty z 3 zapytań przy limit=3).
- `shadow_advisory` WWW: 14 stron z 3 zapytań (m.in. family-office.pl, f-trust.pl, mbank.pl).
- `shadow_advisory` Telegram: 0 postów (patrz problemy).
- `pip-audit`: brak podatności.

## Znane problemy / ograniczenia

1. **YouTube blokuje napisy (429 / IP blocked)**, więc `transcript_status=unavailable`. Obejście: `PROXY_LIST`.
   `ytsearchdate` usunięto z yt-dlp; używamy URL wyników z `sp=CAI%3D`.
2. **SearXNG: DuckDuckGo zwraca CAPTCHA**, więc część zapytań `site:t.me` daje 0 wyników. Ponawianie jest dodane, ale nie pomaga.
3. **Telegram + ogólne frazy (wealth management)** dają przypadkowe, niepolskie kanały, które odpadają na filtrze języka.
   Dobrze działają frazy typu „sygnały giełdowe” (np. GPW_Analizy, fxpopolsku).
4. **Reddit / Wykop** bez kluczy w `.env` są pomijane. Kodu Wykopu nie testowano z prawdziwym kluczem.
5. **Wydajność:** YouTube ~20 s na film. Przy `MAX_QUERIES_PER_RUN=30` i `DEFAULT_LIMIT=20` job może trwać godziny (limit joba 3 h).
   Rozwiązanie: mniejszy limit dla crona albo `docker compose up -d --scale scraper-worker=3`.
6. **Zadanie 2 przy 30 zapytaniach:** wszystkie 26 fraz mieszczą się w budżecie, więc każdy przebieg je powtarza, a rotują tylko 4 zapytania z nazwami podmiotów.
7. Plik `UKNF/zasoby/ZASÓB…md` ma nazwę w Unicode NFD, co daje błędy `pathspec` w VS Code na macOS. Przywracanie: `git restore UKNF/zasoby`.
8. `backend/` i `orchestrator/` nadal instalują zależności przez pip (nie przeniesione na uv).

## Proponowane następne kroki

- **A.** `searxng/settings.yml`: wyłączyć DuckDuckGo, jawnie włączyć Bing / Brave / Startpage / Mojeek.
- **B.** Frazy per źródło w `m3_phrases.yaml`: osobna lista dla Telegrama (sygnały, VIP, kopiuj transakcje), wealth management / family office dla WWW.
- **C.** Osobny limit fraz na przebieg w module 3, żeby szybciej rotować nazwy podmiotów.
- **D.** Moduł klasyfikacji (osobny serwis), korzystający z:
  - `firms.name_norm`, `other_names`, `domains`;
  - `brand_aliases.json` (`word_boundary_aliases`);
  - `posts.outbound_links`, `transcript`, `post_hits`.
- **E.** Opcjonalnie: Whisper jako fallback transkrypcji (za flagą), lista agentów firm inwestycyjnych.

## Uruchomienie i test

```bash
cp .env.example .env    # ustaw hasła; DATABASE_URL musi mieć to samo hasło co POSTGRES_PASSWORD
docker compose up --build db migrations redis minio searxng scraper scraper-worker

curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_sync"}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_ads","source":"youtube","limit":3}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"shadow_advisory","source":"web","limit":5}'
curl localhost:8001/jobs/<id>
curl 'localhost:8001/posts?task=shadow_advisory&source=web'
```

Dostęp do danych:
- Postgres: `localhost:5432`, dane logowania z `.env`.
- MinIO: http://localhost:9001, bucket `investwatch-media`; `media.object_key` to ścieżka pliku.
- Swagger: http://localhost:8001/docs.

Cron: `SCHEDULER_ENABLED=true`, `SCRAPE_CRON` (domyślnie co 6 h, UTC), `REGISTRY_SYNC_CRON` (codziennie 3:00 UTC).
Na start crona: `DEFAULT_LIMIT=5`, `MAX_QUERIES_PER_RUN=30`, `SCRAPE_SOURCES=youtube,telegram,web`.

## Aktualizacja 2026-11-21 (wieczór): moduł 2 i poprawki

- **Nowy task `firm_marketing` (moduł 2):** materiały publikowane przez same firmy z `brand_aliases.json`.
  - Konfiguracja: `scraper/config/m2_sources.yaml` (oficjalne domeny i strony startowe 49 marek; ścieżek nie sprawdzano ręcznie).
  - WWW: strony startowe pobierane bezpośrednio, potem `site:<domena> <fraza>`. Zapisywane są tylko strony z domen firmy.
    Każda strona jest renderowana przez Playwright (desktop i mobile). Przy 403 strona jest pobierana przez przeglądarkę.
  - Dowody pod reguły 4–8 i 13: `media.kind = screenshot` (JPEG w MinIO) oraz `posts.raw.layout.<desktop|mobile>`
    (dominująca czcionka i bloki o ryzyku/zysku ze stylem, pozycją i widocznością).
  - YouTube: tylko filmy z kanału, którego nazwa zawiera alias marki. Przy sortowaniu po dacie wyniki to głównie
    kanały osób trzecich (`skipped_not_owner`), więc uzysk jest niski. Do poprawy: wyszukiwanie po trafności albo listy oficjalnych kanałów.
  - Cron (`run-all`): `firm_marketing` tylko dla `web` i `youtube`.
- **Poprawka:** `common/investwatch_common/db.py` resetuje pulę połączeń po forku RQ (wcześniej `DuplicatePreparedStatement` przy włączonym cronie).
- **Zakres modułu 2 (opcja A):** 49 marek + 26 podmiotów zarejestrowanych w Polsce, dopisanych do `brand_aliases.json`
  (`scope: registered_in_poland`), więc moduł 1 też ich szuka (495 zapytań). Pokryte w całości: `brokerage_banks` (10), `brokerage_firms` (28),
  `foreign_investment_firms` (10). Strony sprawdzone na żywo 2026-11-21. Strony z 403 pobiera fallback przez przeglądarkę,
  ale Trading 212 i podobne pokazują przeglądarce stronę Cloudflare (odpada na filtrze języka).
- **Wykluczenie podmiotów z rejestru (moduły 1 i 3):** `scraper/app/owners.py`. Odrzucane są strony z domen firm z rejestru
  i kanały nazwane jak firma (`stats.skipped_registered_owner`). Zapytania modułu 3 pomijają nazwy i domeny z ostrzeżeń, które
  należą do firm z rejestru (dziś: patronfx.com, teletrade.eu, Crowd Tech Ltd, Forex TB Ltd).
  Ograniczenie: domeny zna tylko ~160 z ~1430 podmiotów autoryzowanych w bazie oraz 75 marek z configu.
- **Zakres według definicji z załączników (2026-11-22):** firma inwestycyjna = DM, bank maklerski, zagraniczna firma
  inwestycyjna (oddział lub transgranicznie), zagraniczna instytucja kredytowa tylko z usługami MiFID
  (`credit_institutions_cross_border`: `mifid_services` i bez adnotacji o zakończeniu działalności; oddziały: zakres z MiFID).
  Tabela per moduł w `scraper/README.md`.
- **Agenci firm inwestycyjnych:** nowe listy `investment_firm_agents_legal` (26) i `investment_firm_agents_natural` (235),
  pobierane przez `registry_sync`. Moduł 3 ich wyklucza (np. F-TRUST IWEALTH = agent Caspar AM), moduł 1 ich zostawia
  (agent reklamujący firmę to podmiot trzeci). Z osób fizycznych zapisujemy tylko imię i nazwisko, firmę i datę wpisu.
- **Domeny firm:** `scraper/config/firm_domains.json` z `python -m app.registry.domains`. Wyszukiwanie idzie przez lokalny SearXNG
  (Google, a gdy odmawia: Bing / DuckDuckGo), bez płatnego API. Moduł 2 dostaje `site:<domena> inwestycje` dla każdej firmy
  inwestycyjnej spoza listy marek, która ma znaną domenę.
- **Nowe źródło: Substack** (`scraper/app/collectors/substack.py`, `Platform.SUBSTACK`). Publiczne API JSON bez klucza:
  `top/search` służy do znajdowania polskich postów i publikacji, `archive` daje najnowsze posty publikacji, a `posts/<slug>`
  pełną treść (posty płatne: tylko zajawka). Moduły 1 i 3. Wyszukiwarka Substacka jest słaba (dopasowuje pojedyncze słowa),
  więc ogólne frazy często nic nie dają. Najlepiej działają nazwy marek („xtb”) i frazy w rodzaju „portfel modelowy”.
- **Zrzuty ekranu:** każda strona WWW i każdy post Substack (wszystkie moduły) ma PNG pierwszego ekranu, desktop 1366×768
  i mobile 390×844 (2x), bez przewijania. `raw.layout` zbiera tylko moduł 2. Rozszerzenie na pozostałe moduły jest w `scraper/TODO.md`.
- **Wynik wyszukiwania domen (2026-11-22):** 846 firm inwestycyjnych i 25 agentów (osoby prawne). Google szybko zaczął odmawiać
  (84 zapytania), resztę obsłużył Bing. Wynik: 66 firm i 17 agentów z domeną zweryfikowaną na żywo (strona główna zawiera
  wyróżniające słowa nazwy). Surowych trafień było 290, ale około połowa była fałszywa (np. national-geographic.pl dla
  National Australia Bank). Większość z ~650 firm transgranicznych bez domeny to podmioty instytucjonalne bez polskich stron.
  Uzupełnienie: ponowne uruchomienie `app.registry.domains`, gdy Google przestanie odmawiać (to samo `--lists`, potem `--merge ... --verify`).
- **Podgląd danych:** http://localhost:8001/browse (`scraper/app/static/browse.html`). Strona korzysta z `/posts` (nowy filtr `q`),
  `/posts/{id}/details`, `/stats`, `/jobs`, a obrazy dostaje przez `/media/<key>`. Na tym Macu port `127.0.0.1:9000` (i 9010) przechwytuje
  ZscalerTunnel, więc bezpośrednie linki do MinIO z hosta nie działają. Porty MinIO na hoście są konfigurowalne w compose
  (`MINIO_API_HOST_PORT`, `MINIO_CONSOLE_HOST_PORT`).
- **Banery cookies:** przed zrzutem przeglądarka akceptuje baner (`accept_cookies` w `layout.py`: znane systemy zgód, a potem przycisk
  „Akceptuj…”/„Accept…”, także w iframe). Informacja, co kliknięto, trafia do `raw.consent`. Na teście: XTB, mBank, ING, Pekao, Bossa,
  capital.com i Substack zaakceptowane. eToro pokazuje baner z opóźnieniem albo wcale.
- **Filtry treści (wszystkie moduły):** `app/lang.py` odrzuca teksty, w których większość liter nie jest łacińska (arabski, chiński, cyrylica),
  niezależnie od długości. Lingua zna teraz ok. 29 języków. Kanał Telegrama jest oceniany w całości i pomijany, jeśli nie jest polski.
  `app/relevance.py` odrzuca treści bez słownictwa inwestycyjnego (kupony, zwykłe konta bankowe, terminale płatnicze) jako `skipped_off_topic`.
- **Udostępnianie danych:** `scraper/app/dataset.py` (eksport i import). Pierwszy eksport jest w `data/scraped/2026-11-22/`
  (17 postów, 30 jobów, 42 pliki, 12 MB). Instrukcja importu jest w `data/scraped/README.md`. Import przetestowany na tymczasowej bazie i buckecie.
