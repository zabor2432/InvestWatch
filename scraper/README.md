# Scraper

Collects posts for module 1 (`registry_ads`: ads of KNF-listed firms), module 2 (`firm_marketing`: marketing
published by the KNF-listed firms themselves, with screenshots and layout) and module 3
(`shadow_advisory`: unauthorised advisory offers), and keeps the firm registry up to date (`registry_sync`).
The API only enqueues jobs; `scraper-worker` (RQ) runs them. Interactive docs: http://localhost:8001/docs

## Operations (step by step)

Everything below runs from the repository root. The scraper API (`scraper`, :8001) only enqueues jobs; the
`scraper-worker` container executes them one by one (RQ) and, when enabled, also runs the cron scheduler.

### 0. Show it working (demo, no waiting)

`scripts/demo-scraper.sh` starts the stack with the scraper, loads the sample export `data/scraped/` (30 jobs, 17 posts with desktop and mobile screenshots)
and hands the posts to the pipeline; then open http://localhost:8001/browse (posts, screenshots, jobs, filters) and the worker logs.
`LIVE=1 scripts/demo-scraper.sh` also runs one small real job and prints its progress. Safe to repeat (nothing is duplicated). `COMPOSE=podman-compose` for Podman.

### 1. First start

```bash
cp .env.example .env                 # once; set passwords - DATABASE_URL must use POSTGRES_PASSWORD
docker compose up -d --build db migrations redis minio searxng scraper scraper-worker
curl localhost:8001/health           # {"status":"ok"}
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_sync"}'
```

`registry_sync` fills the firm registry (`firms`, ~2,200 rows: KNF registers, agents, KNF warnings, I-SCAN); the
first run seeds from `docs/firm_registry` and then refreshes every list live (~3 min). Modules 1 and 3 build their
queries and the "registered firm" filter from it - run it before scraping. Optional: load a teammate's data
(`data/scraped/README.md`).

### 2. Run jobs manually

| Task (module) | What it collects | Sources |
|---|---|---|
| `registry_ads` (module 1) | ads of KNF-listed firms posted by third parties (finfluencers) | `youtube`, `telegram`, `web`, `substack`, `reddit`*, `wykop`* |
| `firm_marketing` (module 2) | marketing published by the investment firms themselves, with screenshots + layout | `web`, `youtube` |
| `shadow_advisory` (module 3) | advisory / wealth-management offers of entities without a licence | `youtube`, `telegram`, `web`, `substack`, `reddit`*, `wykop`* |
| `registry_sync` | refresh of the firm registry | - |

\* needs free API keys in `.env` (`REDDIT_CLIENT_ID/SECRET`, `WYKOP_APP_KEY/SECRET`); without them the job finishes
at once with a "collector skipped" warning. `facebook`, `instagram`, `x` are stubs.

```bash
# one job: task + source, limit = max results per query (default DEFAULT_LIMIT)
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_ads","source":"youtube","limit":3}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"firm_marketing","source":"web","limit":2}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"shadow_advisory","source":"substack","limit":3}'

# every source in SCRAPE_SOURCES x every task it supports (exactly what one cron run does)
curl -X POST localhost:8001/jobs/run-all -H 'content-type: application/json' -d '{"limit":3}'
```

- Each job runs at most `MAX_QUERIES_PER_RUN` queries; the next job of the same task + source continues with the
  following queries (offset in Redis). Calling `run-all` three times = three different queries per task + source.
- Rough durations: YouTube ~20 s per video, web / Substack ~10 s per page (browser render + screenshots),
  Telegram ~2 s per post. One worker runs jobs sequentially; a job is killed after 3 h.
- Posts that are not Polish, not about investing, or published by a registered firm (modules 1, 3) are dropped and
  counted in the job's `stats.skipped_*`.

### 3. Watch progress and results

- **http://localhost:8001/browse** - posts with screenshots, details of every record, the job list (tab "Joby").
- `curl localhost:8001/jobs` (latest jobs), `curl localhost:8001/jobs/<id>` (status, counters, `stats`, `errors`),
  `curl localhost:8001/stats` (counts per module / source).
- Worker log: `docker compose logs -f scraper-worker | grep -E "job_started|query_done|job_finished|job_failed|cron_fired"`.
- Swagger: http://localhost:8001/docs. MinIO console: http://localhost:9001.

### 4. Set up the cron

The scheduler is a thread in `scraper-worker`, configured only through `.env` (times in **UTC**, standard
5-field cron syntax; an empty expression disables that schedule):

| Variable | Meaning | Production default |
|---|---|---|
| `SCHEDULER_ENABLED` | `true` = run the scheduler | `true` |
| `SCRAPE_CRON` | when to run `run-all` (every source x task) | `0 */6 * * *` (every 6 h) |
| `REGISTRY_SYNC_CRON` | when to refresh the firm registry | `0 3 * * *` (03:00 UTC daily) |
| `SCRAPE_SOURCES` | sources included in `run-all` | `youtube,telegram,web,reddit,wykop,substack` |
| `DEFAULT_LIMIT` | results per query when the job has no `limit` | `20` |
| `MAX_QUERIES_PER_RUN` | queries per job (rotating) | `30` |
| `SINCE_DAYS` | skip dated posts older than this | `90` |
| `TELEGRAM_CHANNELS_PER_QUERY`, `SUBSTACK_PUBLICATIONS_PER_QUERY` | channels / publications read per query | `3` |

Apply a change - `.env` is read at container start, so recreate the worker (no rebuild needed):

```bash
docker compose up -d scraper scraper-worker
docker compose logs scraper-worker | grep -E "worker_started|scheduler_started"
# worker_started: "scheduler": true, "sources": [...]; scheduler_started: next_runs per schedule
```

Quick test (new data every 3 minutes), then revert to the production values:

```dotenv
SCHEDULER_ENABLED=true
SCRAPE_CRON=*/3 * * * *
SCRAPE_SOURCES=web,telegram,substack
DEFAULT_LIMIT=2
MAX_QUERIES_PER_RUN=1
```

Each firing logs `cron_fired` followed by one `job_enqueued` per job. Make sure one run finishes before the next
starts, or the queue grows: with YouTube and the defaults a run can take hours - lower the limits, space the cron, or
add workers (`docker compose up -d --scale scraper-worker=3`; a Redis lock makes only one of them fire the cron).
Disable: `SCHEDULER_ENABLED=false` (jobs can still be run manually).

### 5. Rebuild or just recreate?

| You changed | Run |
|---|---|
| `.env` | `docker compose up -d scraper scraper-worker` |
| code in `scraper/`, `common/`, files in `scraper/config/` (baked into the image) | `docker compose up -d --build scraper scraper-worker` |
| `migrations/` (schema) | `docker compose up -d --build migrations scraper scraper-worker` |

### 6. Share the collected data

```bash
mkdir -p data/scraped
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.dataset export /data/scraped/$(date +%F)
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.dataset import /data/scraped/<name>
```

Details: `data/scraped/README.md`.

### 7. Hand-over to the InvestWatch pipeline

Every post (and every new content version) is also written, after each job, to the pipeline bucket `PIPELINE_S3_BUCKET` (default `investwatch`)
as a contract v2 object (`docs/data-contract.md`); the dashboard's **Odśwież dane** then scores it. Nothing is ever duplicated: objects and images
are content-addressed, what already is in the bucket is skipped. Switch off with `LANDING_SYNC=false`; run by hand:

```bash
curl -X POST localhost:8001/landing/sync                       # everything in the scraper database
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.landing from-export /data/scraped/<name>   # an export, no database needed
```

Code: `app/landing.py` (+ `common/investwatch_common/landing.py`, shared with the demo seed).

### 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker compose up --build` fails with `429 Too Many Requests` from docker.io | Docker Hub pull limit: start without `--build` (images exist), `docker login`, or wait |
| images / files at `localhost:9000` do not load | port 9000 taken on the host (e.g. Zscaler); `/browse` serves files through the API anyway; or set `MINIO_API_HOST_PORT` / `MINIO_CONSOLE_HOST_PORT` in `.env` |
| `.env` change has no effect | recreate the containers (step 5) - a running container keeps its old environment |
| Telegram / web find nothing, log shows `searxng_retry_blocked`, `CAPTCHA`, `too many requests` | search engines in SearXNG rate-limit; wait (Google recovers in hours) or adjust engines in `searxng/settings.yml` |
| YouTube `transcript_status = unavailable` | YouTube blocks subtitle requests (429); set `PROXY_LIST` |
| a job stays `running` forever | the worker was restarted mid-job; harmless, run the job again |
| `firm_marketing` + `telegram` rejected by the API | module 2 supports only `web` and `youtube` |

## Data browser

**http://localhost:8001/browse** - read-only HTML page over the API: posts as cards (module, source, author, dates,
text, thumbnails of screenshots / images), filters (module, source, text, date), a details view per record (all
fields, full text, transcript, outbound links, `post_hits`, `post_versions`, media files, `raw` JSON), the job list
and counters; optional auto-refresh. Images are served through the API (`/media/<key>`), so the page works even
when the MinIO API port is not reachable from the host (on some machines 9000 is taken by a VPN client, e.g. Zscaler;
`MINIO_API_HOST_PORT` / `MINIO_CONSOLE_HOST_PORT` in `.env` change the host ports).

## Development

`cd scraper && uv sync && uv run pytest -q`. Lint: `uv run ruff check app tests` (config in `pyproject.toml`); format-check only our own files, `uv run ruff format --check app/landing.py tests`.
Tests cover the decisions that decide what reaches the pipeline (`tests/test_logic.py`: language, topic, ownership, name matching, registry parsing) and the hand-over (`tests/test_landing.py`).

## Endpoints

### `GET /health`
`{"status": "ok"}` when the API is up.

### `POST /jobs` → 202
Enqueue one job.

| Field    | Type   | Required | Values |
|----------|--------|----------|--------|
| `task`   | string | yes      | `registry_ads`, `firm_marketing`, `shadow_advisory`, `registry_sync` |
| `source` | string | for scraping tasks | `youtube`, `telegram`, `web`, `reddit`, `wykop`, `substack` (`facebook`, `instagram`, `x` are stubs); `firm_marketing`: only `web`, `youtube` |
| `limit`  | int    | no       | max results per query, 1–500 (default `DEFAULT_LIMIT`) |

```bash
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_sync"}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_ads","source":"youtube","limit":5}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"firm_marketing","source":"web","limit":3}'
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"shadow_advisory","source":"web","limit":5}'
```

Returns the job (see `GET /jobs/{id}`) with `status: "queued"`. A job runs at most `MAX_QUERIES_PER_RUN`
queries; the next job of the same task + source continues with the following queries.
A collector without its API keys (Reddit, Wykop) finishes at once with a `collector skipped` warning in `errors`.

### `POST /jobs/run-all` → 202
Enqueue every source in `SCRAPE_SOURCES` × every scraping task (`firm_marketing` only for `web` / `youtube`) (what `SCRAPE_CRON` does). Optional body `{"limit": 5}`.
Returns the list of created jobs.

### `GET /jobs?limit=50`
Recent jobs, newest first.

### `GET /jobs/{id}`
Job status and counters.

| Field | Meaning |
|-------|---------|
| `status` | `queued`, `running`, `finished`, `failed` |
| `queries_total`, `queries_done` | progress |
| `posts_seen`, `posts_new`, `posts_changed` | posts stored in this job (`changed` = new version of a known post) |
| `stats.per_query` | posts per query |
| `stats.skipped_language` | non-Polish posts dropped (not stored): mostly non-Latin script (Arabic, Chinese, Cyrillic...) at any length, or another language per lingua |
| `stats.skipped_off_topic` | posts without investment vocabulary dropped (shop coupons, plain bank accounts, payment terminals); `app/relevance.py` |
| `stats.skipped_registered_owner` | `registry_ads` / `shadow_advisory`: results published by a registered firm itself (its domain / its channel), dropped |
| `stats.skipped_not_owner` | `firm_marketing`: results not published by the firm itself (other domain / channel), dropped |
| `stats` (registry_sync) | per list: `upserted`, `new`, `removed` (+ `seed` on first run) |
| `errors` | failed queries or collector warnings |

### `GET /posts`
Collected posts, newest first: `{"total": n, "items": [...]}`.

| Query param | Meaning |
|-------------|---------|
| `task` | posts found by this task |
| `source` | platform |
| `since` | ISO datetime; `published_at` (or `scraped_at` when undated) ≥ since |
| `q` | text in title / content / URL / author (case-insensitive) |
| `limit`, `offset` | paging (limit ≤ 500) |

```bash
curl 'localhost:8001/posts?task=shadow_advisory&source=web&limit=10'
```

### `GET /posts/{id}/details`
Everything stored for one post: the fields of `GET /posts/{id}` plus `first_task` / `first_query` / `first_job_id`,
`content_hash`, `raw`, `hits` (module, query, job, first / last seen), `versions`, `media_files` (kind, type, size, URL).

### `GET /stats`
Counters: posts, posts per module (task) and platform, media per kind, jobs per status.

### `GET /posts/{id}`
One post. Main fields: `platform`, `url`, `media_type` (`text`/`image`/`video`), `author_*`, `title`, `content`,
`transcript` + `transcript_status` (YouTube), `outbound_links`, `engagement`, `lang`, `published_at`,
`tasks` / `queries` (what found it), `media` (`url` = file in MinIO, `source_url` = original).

## Configuration

- Queries: `config/brand_aliases.json` (firms + aliases, module 1), `config/ad_phrases.yaml` (templates),
  `config/m3_phrases.yaml` (module 3 phrases); module 3 also queries names/domains of warned and revoked entities.
- Environment: see the scraper section of `../.env.example`.
- Registry seed files: `../docs/firm_registry/*.json`; refresh them with
  `docker compose exec scraper python -m app.registry.export /tmp/out [list ...]`, then
  `docker compose cp scraper:/tmp/out ./registry-export` and copy the files you want into `docs/firm_registry`.

## Data

Postgres tables (schema in `../common`, migrations in `../migrations`): `firms`, `scrape_jobs`, `posts`,
`post_versions` (snapshot on every content change), `post_hits` (task + query that found a post), `media`.
Images and video thumbnails: MinIO bucket `S3_BUCKET` (console http://localhost:9001).

## Substack (`substack`)

Public JSON API, no key. Substack's search matches single words in any language, so it is used for discovery:
Polish posts containing every query word (half of them for 3+ words; "xtb kod promocyjny" falls back to "xtb") are
taken directly, and the publications of those posts and of matching author profiles are read newest first
(`/api/v1/archive`, back to `SINCE_DAYS`, `SUBSTACK_PUBLICATIONS_PER_QUERY` publications per query). Full text from
`/api/v1/posts/<slug>`; paid posts keep only the free preview (`raw.audience = "only_paid"`, `raw.full_text = false`).
Media: the cover image + first-screen screenshots of the post page. Modules 1 and 3 (not 2).

## Web pages: rendering and screenshots

Every web page (all modules) is rendered by Playwright in two viewports; if the plain HTTP fetch is refused
(403 / bot wall), the browser render is used instead.

## Module 2 (`firm_marketing`)

Config: `config/m2_sources.yaml` - official domains and landing pages of all 75 brands of `brand_aliases.json`.
They cover all of `brokerage_banks`, `brokerage_firms` and `foreign_investment_firms` (the module 2 scope; brands
with `scope: registered_in_poland` were added for that); cross-border brands are an extension.

- **web**: landing pages are fetched directly; then `site:<domain> <phrase>` through SearXNG. Only pages on the
  firm's own domains are kept.
- **youtube**: search by brand; only videos from a channel whose name contains a brand alias are kept.

Stored per web page:

- **every module:** `media` with `kind = "screenshot"` - PNG of the **first screen only** (what the visitor sees on
  arrival, no scrolling), one desktop (1366x768) and one mobile (390x844, 2x density). The cookie banner is accepted
  before the screenshot (known consent platforms, then a button "Akceptuj" / "Zaakceptuj wszystkie" / "Accept all"...,
  also in iframes; one retry after 2.5 s); `raw.consent` = what was clicked per viewport, `null` = no banner found. `source_url` = `screenshot:<viewport>:<hash>`; a new pair only when the page text
  changes. The `og:image` of the page is still stored as `kind = "image"`.
- **module 2 only:** `posts.raw.layout.<desktop|mobile>`: `dominant_font_size`, `font_size_chars` (visible characters
  per font size), `page_height` and `blocks` - text blocks mentioning risk or profit with `font_size`, `font_weight`,
  `color`, `background` (+ `background_image`: colour unreliable for contrast), `opacity`, `visible`, position
  (`x`, `y`, `w`, `h`), `above_fold`, `in_footer`, `in_disclaimer`, `collapsed`, `in_link`. Extending it to all
  modules: see `TODO.md`.

## Content filters (every module)

- **Language** (`app/lang.py`): a text whose letters are mostly non-Latin is rejected at any length; otherwise lingua
  decides among Polish and ~28 other languages. Telegram channels are judged as a whole on the first page (title,
  description, latest messages) and skipped unless Polish (`telegram_channel_not_polish` in the log).
- **Topic** (`app/relevance.py`): kept when the text uses investment vocabulary - a strong term in the title, two
  strong terms ("akcje", "ETF", "IKE", "makler", "forex", "dywidenda"...), or one strong + two weak ("kapitał", "zysk",
  "ryzyko"...). Coupon / discount pages ("kod rabatowy", "Black Friday") need three strong terms.

## Who is included / excluded per module

"Investment firm" as defined in the task attachments (Tematy 1-2): brokerage house, bank conducting brokerage
activity, foreign investment firm conducting brokerage activity in Poland (branch or cross-border), incl. a foreign
credit institution providing investment services. `app/owners.py` (`is_investment_firm`):

| Registry list | Investment firm |
|---|---|
| `brokerage_banks`, `brokerage_firms`, `foreign_investment_firms`, `foreign_investment_firms_without_branches` | all |
| `credit_institutions_cross_border` | `mifid_services` and no remark (remarks = ceased activity / Brexit) |
| `credit_institutions_branches` | scope mentions investment services (MiFID / "sekcja A") |
| `investment_firm_agents_legal`, `investment_firm_agents_natural` | no - agents act on behalf of a firm |
| `revoked_licences`, `knf_public_warnings`, `iscan_warnings` | no |

| Module | Publisher kept | Publisher dropped (`stats`) |
|---|---|---|
| 1 `registry_ads` | third parties, incl. agents of investment firms | investment firms (`skipped_registered_owner`) |
| 2 `firm_marketing` | the investment firm the query is about | everyone else (`skipped_not_owner`) |
| 3 `shadow_advisory` | anyone not authorised (warned, revoked, ceased, unknown) | investment firms and their agents (`skipped_registered_owner`) |

Matching: web - the page host is the firm's (or agent's) domain or a subdomain; channels (YouTube, Telegram, ...) -
named after the firm / agent (exact normalised name, 4+ chars, natural persons in both word orders, or brand alias +
"Polska" / "TV"...). A channel that only mentions a firm is kept. `shadow_advisory` entity queries skip warned names /
domains that belong to an investment firm (clone warnings).

Domains: the registry lists almost none, so they come from `brand_aliases.json`, `m2_sources.yaml` and
`config/firm_domains.json`, generated by search (no API key, local SearXNG):

```bash
docker compose exec scraper python -m app.registry.domains --out /tmp/firm_domains.json
docker compose cp scraper:/tmp/firm_domains.json scraper/config/firm_domains.json   # then rebuild the image
```

A result host is kept only when its domain label is made of the firm's own words (two distinctive words, the
leading one for short names, or the acronym) - firms without a confident match get no domain.
