#!/usr/bin/env bash
# Dependency scan (UKNF requirement 5, supply chain): pip-audit for every uv project, npm audit for the frontend.
# Exit code 1 if anything is reported. Needs: uv, node/npm, network access to the advisory databases.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
failed=0

for dir in backend orchestrator demo/seed demo/collect scraper migrations; do
  [ -f "$root/$dir/uv.lock" ] || continue
  echo "== pip-audit: $dir"
  req="$(mktemp)"
  # local path dependencies (e.g. investwatch-common) are not on PyPI: skip them
  (cd "$root/$dir" && uv export --frozen --no-dev --no-hashes --no-emit-local 2>/dev/null) | grep -v '^-e' > "$req"
  uvx pip-audit -r "$req" --no-deps --disable-pip || failed=1
  rm -f "$req"
done

echo "== npm audit: frontend"
(cd "$root/frontend" && npm audit --audit-level=high) || failed=1

exit "$failed"
