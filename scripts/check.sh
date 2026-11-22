#!/usr/bin/env bash
# Every local quality gate in one go: what CI runs minus the security scanners (scripts/audit.sh) and the container smoke test (scripts/smoke.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$*"; }

for d in backend orchestrator demo/seed demo/collect; do
  step "$d"
  (cd "$d" && uv run ruff check . && uv run ruff format --check . && DATABASE_URL=postgresql://x uv run pytest -q)
done

step scraper  # lint everything, format-check only our own files (the rest predates our formatting)
(cd scraper && uv run ruff check app tests && uv run ruff format --check app/landing.py tests && uv run pytest -q)

step frontend
(cd frontend && npm run typecheck && npm test && npm run build && npm run build:demo)
test -z "$(git status --porcelain -- demo/dashboard-static)" || { git status --short -- demo/dashboard-static; echo "demo/dashboard-static differs from a fresh build:demo: commit the rebuilt files"; exit 1; }

echo; echo "ALL CHECKS PASSED"
