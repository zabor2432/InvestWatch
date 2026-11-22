#!/usr/bin/env bash
# End-to-end smoke test: start the whole stack with the mock model, run all assets in Dagster,
# check that records (and an image) reach the API. Used by CI; can be run locally.
#
# Runs in its own Compose project (investwatch-smoke): your own containers and volumes are not touched,
# but host ports (3000, 3001, 8000, 9000, 9001, 5432) must be free: stop your stack first.
# COMPOSE="podman-compose" to use Podman. Everything it created is removed at the end (down -v of the smoke project).
set -euo pipefail

cd "$(dirname "$0")/.."
compose="${COMPOSE:-docker compose}"
files=(-f docker-compose.yml -f demo/mock-llm/mock.yml)
export COMPOSE_PROJECT_NAME=investwatch-smoke
[ -f .env ] || { cp .env.example .env; created_env=1; }

dump_and_clean() {
  status=$?
  [ "$status" -ne 0 ] && $compose "${files[@]}" logs --tail 60 2>&1 | tail -n 300 || true
  $compose "${files[@]}" down -v >/dev/null 2>&1 || true
  [ "${created_env:-0}" = 1 ] && rm -f .env
  exit "$status"
}
trap dump_and_clean EXIT

wait_for() {  # wait_for <description> <timeout seconds> <command...>
  local what="$1" timeout="$2"; shift 2
  local end=$((SECONDS + timeout))
  until "$@" >/dev/null 2>&1; do
    [ "$SECONDS" -lt "$end" ] || { echo "TIMEOUT waiting for: $what"; return 1; }
    sleep 3
  done
  echo "ok: $what"
}

$compose "${files[@]}" up -d --build

wait_for "backend"  240 curl -sf http://localhost:8000/health
wait_for "dagster"  240 curl -sf http://localhost:3001/server_info
wait_for "seed done" 240 bash -c "$compose ${files[*]} logs seed 2>&1 | grep -q seeded"

total=$(curl -sf http://localhost:8000/api/records | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
[ "$total" = 0 ] || { echo "expected an empty dashboard before processing, got $total"; exit 1; }

# the same path as the dashboard's "Odśwież dane" button: backend -> Dagster GraphQL
run_id=$(curl -sf -X POST http://localhost:8000/api/refresh | python3 -c 'import sys,json;print(json.load(sys.stdin)["run_id"])')
echo "launched run $run_id"

run_status() {
  curl -sf "http://localhost:8000/api/refresh/$run_id" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])'
}
end=$((SECONDS + 300))
until [ "$(run_status)" = SUCCESS ]; do
  [ "$(run_status)" != FAILURE ] || { echo "Dagster run failed"; exit 1; }
  [ "$SECONDS" -lt "$end" ] || { echo "TIMEOUT waiting for the run"; exit 1; }
  sleep 3
done
echo "ok: run succeeded"

image_url=$(curl -sf http://localhost:8000/api/records | python3 -c '
import sys, json
d = json.load(sys.stdin)
assert d["total"] > 0, "no records after processing"
withimg = [r for r in d["items"] if r["images"]]
assert withimg, "no record with an image"
pairs = [r for r in d["items"] if {"desktop", "mobile"} <= {i["variant"] for i in r["images"]}]
assert pairs, "no record with a desktop+mobile image pair"
by_obs = {}
for r in d["items"]:
    by_obs[r["observation_id"]] = by_obs.get(r["observation_id"], 0) + 1
assert max(by_obs.values()) >= 3, "no observation with a history of 3+ items"
n, longest = d["total"], max(by_obs.values())
print(f"ok: {n} records, {len(withimg)} with images, {len(pairs)} desktop+mobile pairs, longest history {longest}", file=sys.stderr)
print(pairs[0]["images"][0]["url"])
')
code=$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "http://localhost:8000$image_url")
[ "$code" = "200 image/png" ] || { echo "image endpoint returned: $code"; exit 1; }
echo "ok: image served from object storage ($code)"

# BATCH_SIZE caps one run, so refresh until everything is scored (calls stop growing), then one more must be a no-op
calls() { curl -sf "http://localhost:8000/api/model-calls?limit=500" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))'; }
refresh() {
  run_id=$(curl -sf -X POST http://localhost:8000/api/refresh | python3 -c 'import sys,json;print(json.load(sys.stdin)["run_id"])')
  until [ "$(run_status)" = SUCCESS ]; do [ "$(run_status)" != FAILURE ] || { echo "refresh run failed"; exit 1; }; sleep 3; done
}
before=$(calls)
for _ in 1 2 3 4; do refresh; after=$(calls); [ "$after" != "$before" ] || break; before=$after; done
refresh
[ "$(calls)" = "$after" ] || { echo "a refresh with nothing new re-scored documents"; exit 1; }
echo "ok: refreshing again with nothing new is a no-op ($after model calls)"
total=$(curl -sf http://localhost:8000/api/records | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
echo "ok: $total records (demo, collected and scraper samples)"
echo "SMOKE TEST PASSED"
