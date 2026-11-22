-- Schemat NASZYCH tabel (pusta baza). Tabele scrapera (firms, scrape_jobs, posts, ...) tworzy Alembic z ../common/models.py;
-- nazwy się nie nakładają (pilnuje tego orchestrator/tests/test_consistency.py), a migrations/alembic/env.py chroni nasze tabele przed --autogenerate.

-- Osobna baza na metadane Dagstera
CREATE DATABASE dagster;

-- Obserwacja = śledzona para (podmiot publikujący, reklamowana firma). Każdy nowy materiał tej pary to kolejny
-- dokument, więc zachowujemy historię (§2.1 zadania: "mechanizm okresowej aktualizacji").
CREATE TABLE observations (
    id                bigserial PRIMARY KEY,
    platform          text NOT NULL,
    advertiser_handle text NOT NULL,
    advertiser_name   text,
    advertiser_url    text,
    advertised_firm   text NOT NULL DEFAULT '',   -- '' gdy nie dotyczy (np. moduł 3)
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (platform, advertiser_handle, advertised_firm)
);

-- Jeden dokument na materiał (platform:external_id). Pola opisują jego AKTUALNĄ wersję; historia wersji w `ingestions`.
CREATE TABLE documents (
    id             bigserial PRIMARY KEY,
    source_key     text NOT NULL UNIQUE,         -- platform:external_id
    platform       text NOT NULL,
    external_id    text NOT NULL,
    module         text NOT NULL CHECK (module IN ('third_party_ads', 'self_promotion', 'non_investment_companies')),
    observation_id bigint NOT NULL REFERENCES observations(id),
    source_url     text NOT NULL,
    title          text,
    text           text,                         -- treść po czyszczeniu
    lang           text,
    published_at   timestamptz,                  -- kiedy opublikowano u źródła (jeśli znane)
    captured_at    timestamptz NOT NULL,         -- kiedy zebrano tę wersję
    content_hash   text NOT NULL,                -- hash tekstu i obrazów aktualnej wersji
    status         text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'in_review', 'confirmed', 'false_positive')),
    ground_truth   boolean,                      -- etykieta referencyjna (jeśli znana), do kalibracji progu
    manipulated    jsonb,                        -- {"rules": [...], "recipe": "..."} dla kontrolowanych wariantów testowych
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_observation ON documents (observation_id, published_at DESC);

-- Obrazy aktualnej wersji: wariant ekranu (desktop/mobile/...) i ostrość (cała strona albo wycięty blok z ryzykiem)
CREATE TABLE document_images (
    document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    variant     text NOT NULL CHECK (variant IN ('desktop', 'mobile', 'tablet', 'original')),
    focus       text NOT NULL DEFAULT 'page' CHECK (focus IN ('page', 'risk')),
    image_key   text NOT NULL,
    sha256      text NOT NULL,
    width       int,
    height      int,
    PRIMARY KEY (document_id, variant, focus)
);

-- Ledger ingestii (append-only): jeden wiersz na obiekt landing; wersje dokumentu = kolejne wiersze
CREATE TABLE ingestions (
    id           bigserial PRIMARY KEY,
    document_id  bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    object_key   text NOT NULL UNIQUE,
    content_hash text NOT NULL,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    run_id       text
);
-- Obiekty landing niezgodne z kontraktem (nie są ponownie walidowane w kółko)
CREATE TABLE intake_rejections (
    object_key  text PRIMARY KEY,
    reason      text NOT NULL,
    rejected_at timestamptz NOT NULL DEFAULT now()
);

-- Surowy wynik 0-1 per (dokument, moduł, model, wersja treści); próg stosowany dopiero przy odczycie.
-- details: {} (moduły 1, 3) albo {"rules": {"2": 0.1, ..., "18": 0.9}} (moduł 2: 18 wyników, null = nie dotyczy)
CREATE TABLE results (
    id           bigserial PRIMARY KEY,
    document_id  bigint NOT NULL REFERENCES documents(id),
    module       text NOT NULL,
    model        text NOT NULL,
    content_hash text NOT NULL,
    score        real NOT NULL CHECK (score BETWEEN 0 AND 1),
    details      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, module, model, content_hash)
);

-- Podgląd wywołań modelu: co poszło do API (state), co wróciło (answers), ile trwało, błędy
CREATE TABLE model_calls (
    id          bigserial PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    document_id bigint REFERENCES documents(id),
    module      text NOT NULL,
    model       text NOT NULL,
    state       text,
    answers     jsonb,            -- {"score": ..., "rules": {...}}; NULL przy błędzie
    score       real,
    latency_ms  int NOT NULL,
    error       text
);

-- Ręczne oceny: każde zatwierdzenie to osobny wiersz (jeden dokument może oceniać wielu użytkowników,
-- a jeden użytkownik wielokrotnie), więc bez unikalności.
-- answers: {"czynnik": 1 (oflagowane: naruszenie/reklama/doradztwo) | 0 (zgodne) | null (nie dotyczy)};
-- czynniki: moduł 1 "is_ad", moduł 3 "offers_advisory", moduł 2 identyfikatory reguł ("2", "12a", ...)
CREATE TABLE annotations (
    id          bigserial PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES documents(id),
    annotator   text NOT NULL,
    answers     jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX annotations_document ON annotations (document_id, created_at DESC);
