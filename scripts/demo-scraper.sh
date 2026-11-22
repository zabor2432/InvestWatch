#!/usr/bin/env bash
# Shows the scraper working, without waiting for a real run: starts the stack with the scraper profile, loads the sample export
# (data/scraped: 30 jobs, 17 posts with screenshots) into the scraper's own database, hands the posts to the pipeline and prints where to look.
#   scripts/demo-scraper.sh              # sample data only (about a minute)
#   LIVE=1 scripts/demo-scraper.sh       # plus one small real job (a few minutes), its progress printed until it finishes
# COMPOSE="podman-compose" for Podman. Safe to repeat: the import skips posts it already has, the hand-over never duplicates.
set -euo pipefail

cd "$(dirname "$0")/.."
compose="${COMPOSE:-docker compose}"
export COMPOSE_PROFILES=scraper
[ -f .env ] || { cp .env.example .env; echo "created .env from .env.example"; }

$compose up -d --build
echo "waiting for the scraper API..."
until curl -sf http://localhost:8001/health >/dev/null; do sleep 3; done

export_dir=$(ls -d data/scraped/*/ | sort | tail -1)
echo; echo "== loading the sample export $export_dir"
$compose run --rm --no-deps -v ./data:/data scraper python -m app.dataset import "/data/${export_dir#data/}"

echo; echo "== handing the posts to the pipeline (contract v2, no duplicates)"
curl -s -X POST http://localhost:8001/landing/sync; echo

if [ "${LIVE:-0}" = 1 ]; then
  echo; echo "== one small real job: substack, shadow_advisory, 1 result per query"
  job=$(curl -s -X POST http://localhost:8001/jobs -H 'content-type: application/json' \
    -d '{"task":"shadow_advisory","source":"substack","limit":1}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  while :; do
    state=$(curl -s "http://localhost:8001/jobs/$job" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["status"],d["queries_done"],d["queries_total"],d["posts_new"])')
    set -- $state
    echo "  job $job: $1, $2/$3 queries, $4 new posts"
    case "$1" in finished|failed) break ;; esac
    sleep 10
  done
fi

cat <<'MSG'

Where to look:
  http://localhost:8001/browse    collected posts, screenshots (desktop and mobile), jobs, filters
  http://localhost:8001/docs      scraper API (POST /jobs, GET /jobs, GET /stats)
  logs:                           docker compose logs -f scraper-worker      (JSON: job_started, query_done, landing_done)
  http://localhost:3001           Dagster: the posts are in storage, run "Materialize all" (or click "Odśwież dane" in the dashboard) to score them
MSG
