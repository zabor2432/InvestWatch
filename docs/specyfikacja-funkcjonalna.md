# InvestWatch: specyfikacja funkcjonalna

| | |
|---|---|
| Wersja | 0.1 (stan na 2026-11-22) |
| Gałąź | `main` |
| Źródła wymagań | `UKNF/UKNF - Pełna treść zadania konkursowego.pdf` (§2-§8), `UKNF/UKNF - Regulamin Zadania Konkursowego.pdf`, `UKNF/zasoby/*` (kryteria oceny informacji o ryzyku), `UKNF/analiza/pytania-do-klienta.md` |
| Powiązane | `docs/architecture.md`, `docs/scraper-integration.md`, `TODO.md`, `AGENTS.md` |

Statusy: **Zrealizowane** (działa i zweryfikowane w tym repo), **Częściowo** (działa z ograniczeniem opisanym w uwagach),
**Planowane** (nie ma jeszcze), **Odstępstwo** (świadoma różnica względem wymagania UKNF).
Wymagania niezweryfikowane w tym repo (głównie scraper, autor: współpracownik) oznaczono "wg dokumentacji".

## 1. Cel i zakres

System wspiera UKNF w monitorowaniu treści w sieci i ochronie inwestorów. Automatycznie zbiera materiały promocyjne i oferty dotyczące
instrumentów i usług finansowych, ocenia je trzema modułami analitycznymi, a analitykowi pokazuje wyniki w dashboardzie z alertami
w czasie rzeczywistym i panelem kalibracji progu.

| Moduł | Zakres | Wynik |
|---|---|---|
| **M1** Finfluencerzy i podmioty trzecie | reklamy zarejestrowanych firm inwestycyjnych publikowane przez osoby trzecie | prawdopodobieństwo 0-1, że materiał jest reklamą |
| **M2** Zgodność i informacja o ryzyku | materiały marketingowe samych firm inwestycyjnych | 18 wyników 0-1 (reguły 2-18 z 12a i 12b), prawdopodobieństwo naruszenia każdej reguły |
| **M3** Shadow advisory | oferty doradztwa inwestycyjnego podmiotów bez zezwolenia | prawdopodobieństwo 0-1 oferowania doradztwa |

Poza zakresem tej wersji: analiza wideo i dźwięku (ASR), logowanie użytkowników i role, retencja danych osobowych (otwarte pytania klienta, §8).

## 2. Aktorzy

| Aktor | Rola |
|---|---|
| Analityk UKNF | przegląda wyniki, zmienia statusy, ocenia ręcznie, kalibruje próg, czyta raport |
| Operator | uruchamia przetwarzanie (Dagster), konfiguruje model i źródła |
| System | scraper, pipeline Dagster, model decyzyjny, backend |

## 3. Wymagania funkcjonalne według wymagań UKNF

### 3.0 Macierz zgodności z zadaniem (UKNF §3): co jest, jak działa, gdzie

| Wymaganie UKNF (§3) | Status | Jak działa | Gdzie |
|---|---|---|---|
| Moduł zbierania danych (kolejka, Playwright/httpx, rotacja UA i proxy, JSON) | Częściowo (brak FB, IG, TikTok) | scraper współpracownika (RQ, Playwright, zrzuty desktop/mobile); po każdym jobie oddaje posty do pipeline'u w kontrakcie v2 bez duplikatów; wyłączony domyślnie, uruchamiany ad hoc | `scraper/`, `scraper/app/landing.py`, `docs/scraper-integration.md` |
| Baza metadanych SQL, baza treści (SQL + object storage) | Zrealizowane | Postgres: obserwacje, dokumenty, wersje, wyniki; MinIO: obiekty landing i obrazy | `db/init.sql`, MinIO `investwatch` |
| Harmonogram lub orchestrator | Zrealizowane | Dagster (assety), start ręczny z UI albo przyciskiem w aplikacji | `orchestrator/pipeline/` (`definitions.py`, `ingest.py`, `prepare.py`, `scoring.py`), http://localhost:3001 |
| Preprocessing: HTML, normalizacja, duplikaty | Zrealizowane | `documents` czyści i normalizuje (NFKC, encje), `preprocessed_batch` wykrywa duplikaty tekstu | `orchestrator/pipeline/preprocess.py` |
| Preprocessing: tokeny i embeddingi | Częściowo | tokeny i wektor cech (feature hashing) do deduplikacji; brak embeddingów neuralnych (nie są potrzebne modelowi decyzyjnemu) | `preprocess.py` (`tokens`, `embed`) |
| Silnik inferencji, model open source | Częściowo | OpenJev przez `/v1/systemone` (hostowany przez Codiv, lokalnie przez zmianę `TYPESAFE_BASE_URL`) | `orchestrator/pipeline/llm.py` |
| Klasyfikacja ryzyka funkcją scoringową | Zrealizowane | odpowiedź modelu to P(tak) 0-1; M1 jeden wynik, M2 18 wyników reguł, M3 jeden | `analyze.py`, `rules.py`, tabela `results` |
| Agregator wyników 1, 2, 3 | Zrealizowane | jeden model `Record` w API | `backend/app/records.py` |
| Dashboard: filtry (data, źródło, ryzyko, moduł), wykresy trendów | Zrealizowane | widoki Wyniki i Przegląd | `frontend/src/pages/` |
| Zmiana statusu, alerty WebSocket | Zrealizowane | `NOTIFY high_risk` → backend → `/ws/alerts` → toast | `orchestrator/pipeline/store.py`, `backend/app/alerts.py` |
| Panel kalibracji: próg wpływa na FP/FN | Zrealizowane | suwak globalny plus progi per reguła M2 z sugestią z ocen analityków | `frontend/src/components/CalibrationPanel.tsx`, `RuleThresholds.tsx` |
| UI na bibliotekach OSS, architektura propsowa | Zrealizowane | React, Tailwind, Radix, Recharts | `frontend/` |
| Docker Compose, jedna komenda | Zrealizowane | `docker compose up --build`; zweryfikowane pod Podmanem (Docker: patrz README) | `docker-compose.yml` |
| Skanowanie zależności, sekrety w `.env` | Zrealizowane | `npm audit`, `pip-audit`, gitleaks, Trivy w CI | `scripts/audit.sh`, `.github/workflows/ci.yml` |
| README (Quick Start, sprzęt, konfiguracja) | Zrealizowane | minimalne, z mapą "gdzie podejrzeć" | `README.md` |

Próbki zebrane przez scraper (`data/scraped/`) są w dashboardzie obok danych demo.

Poza zadaniem UKNF dodano: obserwacje z historią, ręczną ocenę z trybem ślepym i raport odchyleń, statyczne demo z wygenerowanymi ocenami (`demo/dashboard-static/`), zbiór z publicznych stron z wariantami testowymi.
Specyfikacje, na których praca była oparta: `specs/spec-investwatch/`.

### 3.1 Zbieranie danych (§2, §3.1)

| ID | Wymaganie | Źródło | Status | Uwagi / kryterium akceptacji |
|---|---|---|---|---|
| FR-SC-01 | Centralny silnik zbierający dane z internetu i social mediów | §2 | Częściowo | scraper: YouTube, Telegram, web, Reddit, Wykop, Substack; **Facebook, Instagram, X to atrapy, TikTok brak** (zadanie wymienia je jako przykłady); wpięty do pipeline'u przez kontrakt v2 (FR-SC-13), wyłączony domyślnie (`COMPOSE_PROFILES=scraper`) |
| FR-SC-02 | Kolejka zadań (open source) | §3.1 | Zrealizowane (wg dokumentacji) | RQ na Redisie |
| FR-SC-03 | Playwright/httpx, kolektory API, rotacja User-Agent i proxy | §3.1 | Zrealizowane (wg dokumentacji) | `scraper/config/user_agents.txt`, `PROXY_LIST`; brak darmowego źródła proxy (otwarte, §6 analizy) |
| FR-SC-04 | Ekstrakcja HTML do JSON | §3.1 | Zrealizowane (wg dokumentacji) | tabele `posts`, `post_versions`, `media` |
| FR-SC-05 | Zasilanie M1 i M3 wg rejestru firm (KNF, I-SCAN) | §2 M1, M3 | Zrealizowane (wg dokumentacji) | `registry_sync`, zadania `registry_ads`, `shadow_advisory` |
| FR-SC-06 | Zbieranie materiałów samych firm dla M2 | §2 M2 | Zrealizowane (wg dokumentacji) | zadanie `firm_marketing` scrapera (strony firm z rejestru, zrzuty desktop i mobile) |
| FR-SC-07 | Okresowa aktualizacja | §2 M1 | Częściowo | cron scrapera (`SCRAPE_CRON`); pipeline uruchamiany ręcznie (decyzja operacyjna) |
| FR-SC-08 | Dane demo jako zamiennik scrapera | n/a | Zrealizowane | `demo/` (16 rekordów z fikcyjnymi firmami w kontrakcie v2, w tym para desktop/mobile i obserwowany podmiot z historią; prawdziwe reklamy z `demo/real/`) |
| FR-SC-09 | Obserwowanie: dla pary (podmiot, firma) każdy nowy materiał to kolejny rekord z historią | §2.1 | Zrealizowane | tabela `observations`; w szczegółach rekordu lista "Historia obserwacji"; ponowne zebranie zmienionej treści tworzy nową wersję dokumentu |
| FR-SC-10 | Zbiór z publicznych stron dla M1, M2, M3 (do testów) | §2 | Zrealizowane (narzędzie dev) | `demo/collect/` (manifest `sources.yaml`, Playwright: tekst, zrzuty komputer 1440 px i telefon 390 px, bloki z ryzykiem); wyniki w `demo/collected/` poza gitem |
| FR-SC-11 | Kontrolowane warianty z celowo złamaną regułą M2 | n/a | Zrealizowane (narzędzie dev) | 14 przepisów DOM/CSS w `demo/collect/manipulate.py`; wariant ma `manipulated {rules, recipe}` i znacznik w UI, nie jest prawdziwym materiałem |
| FR-SC-12 | Kontrakt danych wejściowych niezależny od źródła | n/a | Zrealizowane | `docs/data-contract.md`, `orchestrator/pipeline/contract.py`, JSON Schema; scraper dostosuje się adapterem (patrz `docs/scraper-integration.md`) |
| FR-SC-13 | Oddanie danych scrapera do pipeline'u bez duplikatów | n/a | Zrealizowane | `scraper/app/landing.py` + `common/investwatch_common/landing.py`: klucze zależą od treści, istniejące obiekty i obrazy pomijane, nowa wersja posta = jeden nowy obiekt; hook po jobie, `POST /landing/sync`, import z eksportu; próbki `data/scraped/` ładuje `seed` |

### 3.2 Składowanie (§3.1)

| ID | Wymaganie | Status | Uwagi |
|---|---|---|---|
| FR-ST-01 | Baza metadanych (SQL) | Zrealizowane | PostgreSQL: `observations`, `documents`, `document_images`, `ingestions` (ledger), `intake_rejections`, `results`, `annotations`, `model_calls` (`db/init.sql`) + tabele scrapera (Alembic) |
| FR-ST-02 | Baza treści (SQL + object storage) | Zrealizowane | treść po preprocessingu w `documents.text`, surowe rekordy i obrazy w MinIO (bucket `investwatch`) |
| FR-ST-03 | Harmonogram: cron lub orchestrator | Zrealizowane | Dagster (assety, UI, retry modułów AI: 2 ponowienia); start ręczny z UI |
| FR-ST-04 | Retencja surowych danych i trwałe dowody | **Planowane** | `raw/` nie wygasa; trwałe `evidence/` niezaimplementowane |

### 3.3 Moduły analityczne AI (§3.2)

| ID | Wymaganie | Status | Uwagi / kryterium akceptacji |
|---|---|---|---|
| FR-AI-01 | Preprocessing: usuwanie tagów HTML, normalizacja, deduplikacja | Zrealizowane | assety `intake_items` (walidacja kontraktem, kwarantanna) i `documents`; hash wersji = tekst + sumy wszystkich obrazów; ten sam hash = nic się nie zmienia, inny = nowa wersja dokumentu |
| FR-AI-02 | Reprezentacja wektorowa (tokeny, embeddingi) | **Częściowo** | `preprocessed_batch`: tokeny i wektor cech (feature hashing, 256 wymiarów) do wykrywania duplikatów tekstu; model decyzyjny ocenia tekst i obraz wprost, więc embeddingi neuralne nie są potrzebne (docelowo dedupe semantyczny, patrz architektura docelowa) |
| FR-AI-03 | Silnik inferencji vLLM / llama.cpp / Ollama, model open source (np. Gemma, BERT) | **Częściowo** | OpenJev (oparty na DiffusionGemma) przez protokół `/v1/systemone`; teraz hostowany przez Codiv (darmowy), lokalnie na GPU przez zmianę `TYPESAFE_BASE_URL` (ten sam model, vLLM/MLX) |
| FR-AI-04 | Klasyfikacja ryzyka funkcją scoringową do kategorii | Zrealizowane | surowy wynik 0-1 w `results.score`; próg stosowany dopiero przy odczycie |
| FR-AI-05 | M1: ocena, czy materiał jest reklamą | Zrealizowane | asset `ad_scores`, 1 wynik 0-1 |
| FR-AI-06 | M2: 18 wyników per rekord (reguły 2-18, 12a, 12b), podstawa prawna | Częściowo | asset `rule_scores`; reguły tekstowe przez model, wizualne 4, 5, 6 osobnym przebiegiem na bloku z ryzykiem (albo stopce obrazu), **reguła 8 tylko dla rekordu z obrazami `desktop` i `mobile`** (model porównuje czytelność ryzyka na obu ekranach; bez pary "nie dotyczy"), reguła 7 ocenia tylko tekst i obraz (wymaga DOM); reguły z opisem UKNF i kryteriami (`orchestrator/pipeline/rules.py`) |
| FR-AI-07 | M3: podejrzenie doradztwa bez uprawnień | Zrealizowane | asset `advisory_scores`, 1 wynik 0-1 |
| FR-AI-08 | Obraz jako wejście (reguły wizualne) | Częściowo | obraz + wycinek stopki; kontrast, rozmiar i położenie tekstu mierzone tylko przez model (pomiary deterministyczne: Planowane, patrz `TODO.md`) |
| FR-AI-09 | Agregator łączący wyniki 1, 2, 3 w ujednolicone obiekty | Zrealizowane | model `Record` w backendzie (`/api/records`): moduł, źródło, score, status, reguły, dowody |
| FR-AI-10 | Idempotencja i ponowna analiza | Zrealizowane | wynik unikalny per (dokument, moduł, model, wersja treści); nowe i zmienione wersje zawsze trafiają do modelu, a po zmianie modelu stare dokumenty tylko z okna wstecz (`reprocess_lookback_days`, domyślnie 30); błąd jednego dokumentu nie traci reszty |
| FR-AI-11 | Parametryzowana ingestia: co trafia do modelu | Zrealizowane | `IngestConfig` w Dagsterze (`batch_size`, `reprocess_lookback_days`, `modules`), domyślne z `.env`; metadane runu pokazują liczniki (nowe, przeliczane w oknie, pominięte) |
| FR-AI-12 | Duplikaty tekstu nie powodują drugiego wywołania modelu | Zrealizowane | cosinus wektora cech ≥ 0.95 w obrębie modułu; duplikat dostaje wynik oryginału (`details.duplicate_of`); materiały z obrazami zawsze osobno |
| FR-AI-13 | Opcjonalna transkrypcja audio/wideo na tekst (lokalny Whisper) | Planowane (krok w grafie, domyślnie pominięty) | asset `transcribed_batch`, `pipeline/transcribe.py`; brak źródeł audio, więc wyłączony; włączenie wymaga doinstalowania torch/transformers/ffmpeg |

### 3.4 Aplikacja webowa (§3.3)

| ID | Wymaganie | Status | Uwagi / kryterium akceptacji |
|---|---|---|---|
| FR-UI-01 | Wyniki z filtrowaniem po dacie, źródle, poziomie ryzyka i module | Zrealizowane | widok **Wyniki**; filtry w URL; dodatkowo status i szukanie tekstowe |
| FR-UI-02 | Wykresy trendów (liczba incydentów w czasie) | Zrealizowane | widok **Przegląd** (Recharts), KPI i rozkłady |
| FR-UI-03 | Zmiana statusu rekordu | Zrealizowane | nowy / w analizie / potwierdzony / fałszywy alarm; optymistyczna aktualizacja z cofnięciem przy błędzie |
| FR-UI-04 | Powiadomienia WebSocket o wysokim ryzyku w czasie rzeczywistym | Zrealizowane | `NOTIFY high_risk` → backend → `/ws/alerts`; toast, centrum powiadomień, auto-reconnect |
| FR-UI-05 | Panel kalibracji progu (wpływ na FP/FN) | Zrealizowane | suwak (domyślnie 0.5), precision/recall/F1 na rekordach z etykietą referencyjną; progi per reguła M2 w osobnej tabeli (FR-UI-10) |
| FR-UI-06 | UI na bibliotekach open source, architektura oparta o propsy | Zrealizowane | React, Tailwind, Radix, TanStack Table, Recharts; komponenty prezentacyjne sterowane propsami |
| FR-UI-07 | Szczegóły rekordu: treść, reguły, dowody, **podgląd obrazów** | Zrealizowane | obrazy z MinIO przez `GET /api/records/{id}/images/{variant}?focus=`; komputer i telefon obok siebie, blok z ryzykiem osobno |
| FR-UI-08 | Przycisk "Odśwież dane" uruchamia przetwarzanie | Zrealizowane | `POST /api/refresh` → Dagster GraphQL (`process_batch`), jeden run naraz, status przez `GET /api/refresh/{run_id}`, toast i przeładowanie listy po sukcesie |
| FR-UI-09 | Historia obserwacji, platforma, data publikacji, znacznik wariantu testowego | Zrealizowane | szczegóły rekordu: podmiot i firma z obserwacji, lista pozostałych materiałów pary, znacznik "zmanipulowany" z listą celowo złamanych reguł |
| FR-UI-10 | Progi per reguła modułu 2 z sugestią z ocen analityków | Zrealizowane | sugestia = maks. F1 względem ocen (siatka 0.05, min. 5 ocen); progi w przeglądarce, liczone przy odczycie w liście, szczegółach, raporcie i kalibracji; zapis na serwerze: Planowane |
| FR-UI-11 | Statyczna kopia dashboardu z wygenerowanymi ocenami (demo) | Zrealizowane | `npm run build:demo` → `demo/dashboard-static/`; mocki i deterministyczne oceny 3 analityków; dane nieprawdziwe |

### 3.5 Wymagania formalne i techniczne (§4, §5)

| ID | Wymaganie | Status | Uwagi |
|---|---|---|---|
| FR-OP-01 | Modułowa architektura lekkich serwisów, bez monorepo | Zrealizowane | frontend, backend, orchestrator (AI), scraper, db jako osobne katalogi i obrazy |
| FR-OP-02 | Cały stos on-premise jedną komendą (Docker Compose) | Zrealizowane | `docker compose up --build` (zweryfikowane pod Podmanem); scraper pod profilem |
| FR-OP-03 | Wyłącznie open source i on-premise, bez płatnych zewnętrznych API | **Częściowo** | wszystko lokalnie poza modelem: Codiv jest zewnętrzny (darmowy "eksperyment", bez daty końca); docelowo model lokalny |
| FR-OP-04 | Skanowanie zależności (npm, pip) | Zrealizowane | `scripts/audit.sh` (`npm audit`, `pip-audit`; 0 znanych podatności); Snyk (chmura) nie używany |
| FR-OP-05 | Sekrety w `.env` | Zrealizowane | `.env` poza repo, `.env.example` z szablonem |
| FR-OP-06 | README: Quick Start, wymagania sprzętowe, konfiguracja | Zrealizowane | minimalne, funkcje opisane tutaj |
| FR-OP-07 | Lista narzędzi i bibliotek (Załącznik 3) | Zrealizowane | `THIRD_PARTY.md` generowany z lockfile'ów |
| FR-OP-08 | Tytuł i opis projektu, prezentacja PDF, film | **Planowane** | do przygotowania przed oddaniem |
| FR-OP-09 | CI z bramką bezpieczeństwa przed budową | Zrealizowane (nieuruchomione na GitHubie) | `.github/workflows/ci.yml`: audyt zależności (`pip-audit`, `npm audit`), gitleaks (historia), Trivy (lockfile'e), potem ruff, testy, typecheck, build obrazów i test dymny (`scripts/smoke.sh`); Dependabot; składnia sprawdzona `actionlint`, kroki zweryfikowane lokalnie; SonarCloud niewłączony (wymaga konta i tokenu) |

## 4. Funkcje dodatkowe (poza wymaganiami UKNF)

| ID | Funkcja | Opis i kryterium akceptacji |
|---|---|---|
| EX-01 | **Ręczna ocena czynników** | Dla każdego czynnika (M2: każda reguła, M1 i M3: jedno pytanie) użytkownik wybiera Spełnia / Narusza / Nie dotyczy i zatwierdza; zapis jako nowy wiersz `annotations` (wielu oceniających, brak unikalności); wymagany komplet czynników |
| EX-02 | **Tryb ślepy** | Przełącznik w nagłówku (domyślnie włączony): ukrywa odpowiedzi i wynik modelu do zatwierdzenia własnej oceny; po zatwierdzeniu pokazuje porównanie i zgodność z modelem |
| EX-03 | **Raport odchyleń** | Widok **Raport**: dla wybranego modelu, modułu i oceniających zgodność, precision/recall, kappa, zgodność między oceniającymi, tabela per czynnik (z maksimum score na zgodnych jako baseline progu), histogram score, największe odchylenia, konflikty, eksport CSV |
| EX-04 | **Log wywołań modelu** | Tabela `model_calls` i `GET /api/model-calls`: wysłany `state`, odpowiedzi, czas, błędy; logi per dokument i metadane w assetach Dagstera |
| EX-05 | **Wymienny model** | Cała integracja w `orchestrator/pipeline/llm.py`; zmiana dostawcy to zmiana zmiennych; atrapa modelu do testów bez klucza (`demo/mock-llm`) |
| EX-06 | **Konkretne pytania wizualne** | Przebieg wizualny na wycinku stopki z pytaniami o to, co widać (zmierzone: reguła 5 dla nieczytelnego ryzyka 0,00 → 0,97 na parze testowej) |
| EX-07 | Dane i narzędzia demo | oryginał i wariant z nieczytelnym ryzykiem prawdziwej reklamy (`demo/tools/blur_risk.py`) |
| EX-08 | Proces wytwarzania z asystentem AI | `AGENTS.md`, `specs/`, `docs/` (kryterium 8.2) |

## 5. Wymagania niefunkcjonalne

| ID | Kategoria | Wymaganie | Status |
|---|---|---|---|
| NFR-01 | Stabilność UI | konsola przeglądarki bez błędów, brak `console.log`; błędy API z komunikatem i ponowieniem | Zrealizowane |
| NFR-02 | Bezpieczeństwo | SQL parametryzowany; walidacja wejścia (Pydantic, `Literal`, limity); obrazy po id rekordu, nigdy po ścieżce od klienta; sekrety poza repo | Zrealizowane |
| NFR-03 | Brak uwierzytelniania | brak logowania i ról; imię oceniającego deklarowane; endpointy bez autoryzacji (POC) | Odstępstwo |
| NFR-04 | Testowalność | testy jednostkowe w każdym projekcie (orchestrator, backend, demo/seed, demo/collect, frontend; w scraperze tylko adapter); zewnętrzne API mockowane | Zrealizowane |
| NFR-05 | Skalowalność | serwisy bezstanowe poza bazą i storage; batch idempotentny (`BATCH_SIZE`); kilka replik backendu możliwe (`LISTEN` w każdej) | Częściowo (niemierzone) |
| NFR-06 | Obserwowalność | UI Dagstera (runy, logi, metadane), `model_calls`, logi scrapera | Zrealizowane |
| NFR-07 | Przenośność | Docker Compose i Podman; obrazy przypięte (MinIO, Redis, SearXNG) | Zrealizowane |
| NFR-08 | Dostępność UI | ryzyko oznaczone etykietą tekstową, nie samym kolorem; skróty klawiszowe | Zrealizowane |
| NFR-09 | Licencje | wszystkie biblioteki z licencjami w `THIRD_PARTY.md`; licencja wag modelu do potwierdzenia z UKNF (pytanie 15) | Częściowo |

## 6. Model danych i interfejsy

**Wejście pipeline'u**: niezmienny obiekt `raw/{platform}/{external_id}/{hash12}.json` w MinIO w kontrakcie v2 (źródło, moduł, obserwacja = podmiot i firma,
daty, tekst, lista obrazów z wariantem ekranu, etykieta i znacznik manipulacji): `docs/data-contract.md`, `docs/intake-item.schema.json`.

**Tabele** (`db/init.sql`): `observations` (para podmiot-firma), `documents` (aktualna wersja materiału: treść, daty, status, etykieta), `document_images` (obrazy wg wariantu i ostrości),
`ingestions` (ledger wersji), `intake_rejections` (kwarantanna), `results` (score 0-1 per dokument, moduł, model, wersja treści; `details` z regułami),
`annotations` (oceny ręczne), `model_calls` (log wywołań). Tabele scrapera tworzy Alembic (`firms`, `scrape_jobs`, `posts`, `post_versions`, `post_hits`, `media`).

**API backendu:** `GET /api/records`, `PATCH /api/records/{id}/status`, `GET /api/records/{id}/images/{variant}`, `GET|POST /api/records/{id}/annotations`,
`POST /api/refresh`, `GET /api/refresh/{run_id}`, `GET /api/report`, `GET /api/model-calls`, `WS /ws/alerts`.

## 7. Zgodność z kryteriami oceny (§8)

| Kryterium | Waga | Stan |
|---|---|---|
| 1. Technologia i gotowość dema | 30% | demo działa jedną komendą, dane i atrapa modelu w `demo/`; ryzyko: zależność od zewnętrznego API modelu |
| 2. Innowacyjność procesu (praca z AI) | 20% | opisany, powtarzalny proces w `AGENTS.md`, spec w `specs/`, historia commitów z trailerem `Co-Authored-By` |
| 3. Architektura | 20% | moduły, kontrakt przez dane (storage + Postgres), wymienny model i źródło danych; scraper opcjonalny |
| 4. Zgodność ze specyfikacją i technologiami | 20% | tabele z §3 powyżej; luki: `raw.layout` ze scrapera dla reguł M2, embeddingi, reguła 7, model lokalny |
| 5. Atrakcyjność | 10% | ręczna ocena z trybem ślepym, raport odchyleń, podgląd obrazów |

## 8. Znane odstępstwa, ryzyka i otwarte pytania

1. **Model hostowany zewnętrznie** (FR-OP-03): darmowy, bez gwarancji dostępności; ścieżka lokalna wymaga GPU (NVIDIA 24 GB+ lub Apple Silicon 16 GB) i potwierdzenia licencji wag.
2. **Jakość modelu nieznana na danych UKNF**: wyniki mierzone na kilku przykładach; brak zbioru z etykietami (pytanie 7 analizy). Mechanizm progów per reguła działa (FR-UI-10), ale sugestie sprawdzono tylko na ocenach wygenerowanych (demo); prawdziwe oceny analityków czekają.
3. **Polski**: żaden z rozważanych modeli nie deklaruje wsparcia dla polskiego; do zmierzenia na próbkach.
4. **Integracja ze scraperem**: działa przez adapter do kontraktu v2 (FR-SC-13); scraper nie przekazuje jeszcze układu stron (`raw.layout`) dla reguł wizualnych M2, a pipeline trzeba po scrapowaniu uruchomić ręcznie. Szczegóły: `docs/scraper-integration.md`.
   Zbiór z `demo/collect` to oceny autora (`label` + `basis` w manifeście), nie rozstrzygnięcia KNF; strony cudze, więc poza gitem.
5. **Dane osobowe** w scrapowanych treściach (finfluencerzy) i retencja: bez decyzji klienta (pytanie 14).
6. **Tryb ślepy** nie jest szczelny (filtry i sortowanie po ryzyku zdradzają kolejność).
7. **Alembic i nasze tabele** w jednej bazie: dodano `include_object`, żeby `--autogenerate` nie proponował ich usunięcia.

Backlog: `TODO.md`. Kierunek rozwoju: `docs/architecture.md`, sekcja "Architektura docelowa".
