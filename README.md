# InvestWatch

Monitors online content and flags investor-protection risks (UKNF HackNation 2026): third-party ads of KNF-listed firms (M1),
firms' own marketing vs. the risk-information rules (M2), unauthorised investment advice (M3).
Scope: [docs/specyfikacja-funkcjonalna.md](docs/specyfikacja-funkcjonalna.md). Architecture: [docs/architecture.md](docs/architecture.md).

## How it works

1. **Collect**: the scraper searches YouTube, Telegram, Reddit, Wykop, Substack and websites (job queue on Redis, search through a local SearXNG) and drops each post into object storage (MinIO).
2. **Process**: a Dagster pipeline validates, cleans and de-duplicates the posts, then sends each one to the module it belongs to.
3. **Score**: an open model answers yes/no questions, so every result is a probability 0-1 (M2: one per rule). Scores are stored raw; the threshold is applied only when reading.
4. **Review**: the dashboard shows the results with filters, trends and a threshold calibration panel; high-risk results raise a real-time alert (WebSocket).

Without the scraper the pipeline runs on the bundled demo data and scraped samples (`demo/`, `data/scraped/`).

## Quick Start

```bash
cp .env.example .env        # set TYPESAFE_API_KEY (free key: https://codiv.ai/signup)
docker compose up --build   # Podman: podman-compose up --build
```

1. Open the dashboard http://localhost:3000. It starts **empty**: nothing is processed automatically.
2. Click **Odśwież dane** (or Dagster http://localhost:3001 → **Assets** → **Materialize all**). The list reloads when the run finishes.

No API key: use the mock model, `docker compose -f docker-compose.yml -f demo/mock-llm/mock.yml up --build`.

Data lives in Docker volumes, so it **survives a restart**: `docker compose down` keeps records, ratings (the Report) and storage; **`docker compose down -v` wipes everything** (start from an empty dashboard).

With the live scraper (off by default):

```bash
COMPOSE_PROFILES=scraper docker compose up --build -d
curl -X POST localhost:8001/jobs -H 'content-type: application/json' -d '{"task":"registry_sync"}'   # firm registry first
curl -X POST localhost:8001/jobs/run-all -H 'content-type: application/json' -d '{"limit":3}'       # one scraping round
```

New posts land in the pipeline bucket by themselves; then click **Odśwież dane**. The scraper also runs on its own every 6 hours(configurable) (`SCRAPE_CRON`).

## Where to look

| What | Where |
|---|---|
| Dashboard | http://localhost:3000 |
| Pipeline runs, logs, per-document metadata | Dagster http://localhost:3001 |
| Files in storage (`raw/…` landing objects, `images/…`) | MinIO http://localhost:9001, bucket `investwatch` (login: `MINIO_ROOT_*` from `.env`) |
| Model results and every model call | `GET :8000/api/records`, `GET :8000/api/model-calls` (tables `results`, `model_calls`); API docs `:8000/docs` |
| Database | `localhost:5432`, schema in [db/init.sql](db/init.sql) (`documents`, `results`, `annotations`, `model_calls`, …) |
| Scraper jobs and collected posts (profile `scraper`) | http://localhost:8001/docs, browser http://localhost:8001/browse |
| Static demo dashboard with generated analyst ratings (no backend) | `cd demo/dashboard-static && python3 -m http.server 8080` |

## Requirements

- Docker Compose v2 **with BuildKit** (the `buildx` plugin; included in Docker Desktop, with Colima run `brew install docker-buildx` and link it into `~/.docker/cli-plugins/`),
  or Podman with `podman-compose` (add `--force-recreate` after rebuilding an image).
- About 4 GB RAM and 5 GB disk for the containers; the scraper profile adds a Chromium image. No GPU (the model is hosted).
- Model on your own hardware instead: NVIDIA GPU with 24 GB+ or Apple Silicon with about 16 GB free, see the model spec linked below.

## Configuration

Everything lives in `.env` (template: `.env.example`); never commit it.

| Variable | Meaning |
|---|---|
| `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `JEV_MODEL` | decision model: key, server, model id. Choosing a model and running it on your own GPU: [specs/spec-investwatch/model-selection-and-self-hosting.md](specs/spec-investwatch/model-selection-and-self-hosting.md) |
| `BATCH_SIZE`, `REPROCESS_LOOKBACK_DAYS` | documents per run; days back that are re-scored after a model change (new and changed ones are always scored) |
| `ALERT_THRESHOLD` | score from which a result raises a real-time alert (0.9) |
| `POSTGRES_*`, `DATABASE_URL`, `MINIO_*`, `S3_ENDPOINT_URL`, `PIPELINE_S3_BUCKET` | database and object storage |
| `MINIO_API_HOST_PORT`, `MINIO_CONSOLE_HOST_PORT` | MinIO host ports (change if 9000 is taken, e.g. by a VPN client) |
| `COMPOSE_PROFILES=scraper` | also start the scraper (off by default) |

## Checks

```bash
scripts/audit.sh                          # dependency scan: npm audit + pip-audit
scripts/smoke.sh                          # end-to-end test in a separate Compose project (stop your stack first; Podman: COMPOSE=podman-compose)
```

CI (`.github/workflows/ci.yml`) runs the scan, gitleaks, Trivy, tests and the smoke test.
Libraries and licences: [THIRD_PARTY.md](THIRD_PARTY.md).

## More

- Scraper (demo: `scripts/demo-scraper.sh`, ad hoc runs, cron, hand-over to the pipeline): [scraper/README.md](scraper/README.md), [docs/scraper-integration.md](docs/scraper-integration.md).
- Data format of the pipeline input: [docs/data-contract.md](docs/data-contract.md). Real public pages for tests: `demo/collect` ([sources.yaml](demo/collect/sources.yaml)).
- Specifications the work was based on: [specs/spec-investwatch/](specs/spec-investwatch/).
