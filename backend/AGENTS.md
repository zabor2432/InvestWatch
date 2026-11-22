# backend/ (FastAPI)

Applies on top of the root `AGENTS.md`. Run `uv run ruff check . && DATABASE_URL=postgresql://x uv run pytest -q` here.

- `app/schemas.py` mirrors `frontend/src/api/dto.ts` (the only wire contract): change both together.
- `app/records.py` is the only place that knows the DB schema and maps rows to API models; SQL is parameterised.
- Validate at the edge: Pydantic `Literal`s and `Query(ge, le)` bounds; path ids are `int`; unknown ids give 404.
- Images are served by record id (`GET /api/records/{id}/image`); the storage key comes from the DB, never from the client; only image content types.
- Alerts: the orchestrator writes `NOTIFY high_risk`, `app/alerts.py` listens and pushes to `/ws/alerts`.
- Reviews: `POST /api/records/{id}/annotations` needs exactly the record's factors with values 0/1/null; each submission is a new row (no uniqueness).
- Tests use `TestClient` with monkeypatched `records`/`storage`; no database in unit tests.
