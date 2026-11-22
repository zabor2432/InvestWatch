# AGENTS.md

Instructions for AI coding agents (and humans) working in this repo. The closest `AGENTS.md` to the file you edit wins:
see `orchestrator/`, `backend/`, `frontend/`. User instructions in chat override this file.

## Project

**InvestWatch** (UKNF HackNation 2026): monitors online content and flags investor-protection risks in three modules:
1. third-party ads of KNF-listed firms (finfluencers), 2. compliance of firms' own marketing with the risk-information rules
(18 rules, KNF/MiFID II), 3. unauthorised investment advice ("shadow advisory").
Pipeline: **data → object storage (MinIO) → Dagster assets (preprocess → per-module AI) → PostgreSQL → backend (REST + WebSocket) → React dashboard**.
Every model answer is a probability 0-1; the threshold is applied only when reading. Functional scope: `docs/specyfikacja-funkcjonalna.md`,
architecture: `docs/architecture.md`, open items: `TODO.md`.

## Repo map

| Path | What |
|---|---|
| `orchestrator/` | Dagster code location (assets, model client, rules); see its AGENTS.md |
| `backend/` | FastAPI: `/api/records`, `/api/report`, annotations, image preview, `/ws/alerts` |
| `frontend/` | React 18 + TypeScript + Tailwind dashboard (nginx in Docker) |
| `db/` | `init.sql`: tables `documents`, `results`, `annotations`, `model_calls` + the `dagster` database |
| `demo/` | demo data, seed service, mock LLM, helper tools (nothing here is production code) |
| `scraper/`, `common/`, `migrations/`, `searxng/` | scraper stack owned by a teammate; off by default (`COMPOSE_PROFILES=scraper`). Ours inside it: the contract hand-over (`scraper/app/landing.py`, `common/investwatch_common/landing.py`), the rest only by agreement |
| `docs/`, `specs/`, `UKNF/` | documentation, task specs, the contest materials and requirement analysis |

## Setup and commands

Runtime: Docker Compose v2 or Podman (`podman-compose`); `cp .env.example .env` first (the only place for secrets).

```bash
docker compose up --build                                   # whole project; front starts empty, run "Materialize all" in Dagster (:3001)
docker compose -f docker-compose.yml -f demo/mock-llm/mock.yml up --build   # same, with a mock model (no API key)
docker compose down -v                                      # wipe volumes (schema is created only on an empty database)
# podman-compose: add --force-recreate after rebuilding an image

scripts/check.sh                                            # all local gates in one go (lint, tests, typecheck, builds)
cd orchestrator && uv run ruff check . && uv run pytest -q
cd backend      && uv run ruff check . && DATABASE_URL=postgresql://x uv run pytest -q
cd demo/seed    && uv run ruff check . && uv run pytest -q
cd frontend     && npm run typecheck && npm test && npm run build
scripts/audit.sh                                            # dependency scan (npm audit + pip-audit)
COMPOSE=podman-compose scripts/smoke.sh                     # e2e smoke test in its own Compose project (stop your stack first: same host ports)
python3 scripts/third_party.py                              # regenerate THIRD_PARTY.md (libraries and licences) after dependency changes
```

Python packages are managed with **uv only** (`pyproject.toml` + `uv.lock`; after changing dependencies run `uv lock`). No pip, no requirements.txt.

## Code style (only what differs from defaults)

- KISS and DRY. Small modules, no speculative abstractions, no dead code. A diff should be as small as the change allows.
- Python 3.12, ruff (`E,F,I,UP,B,S`, line length 100, `E501` ignored), `ruff format`. Pydantic at every boundary; type hints on public functions.
- SQL is always parameterised (`%s`); never build SQL from request input.
- Code identifiers in English. UI text is Polish. Comments and docs may be Polish; explain *why*, not *what*.
- Never leave `console.log` in the frontend (judged by UKNF): use `src/lib/log.ts` (`debug`, behind `VITE_DEBUG`).
- Commits: `type(scope): short description` (`feat`, `fix`, `refactor`, `docs`, `chore`), body says what was verified; AI-authored commits end with the `Co-Authored-By` trailer.

## Testing

- CI (`.github/workflows/ci.yml`) runs on every pull request and on `main`: security gate first (`scripts/audit.sh`, gitleaks, Trivy), then ruff + pytest per Python project and
  typecheck + vitest + build for the frontend, then image build and `scripts/smoke.sh`. Keep it green; fix the cause, do not weaken a check.
- Services never import each other (the link is the data contract: MinIO + Postgres), so knowledge repeated across projects (module names, table names, rule ids)
  is guarded by `orchestrator/tests/test_consistency.py`. Add a check there when you repeat a constant in a new place.
- `demo/dashboard-static` is committed build output (`cd frontend && npm run build:demo`, stable file names); CI fails when it is stale. `scripts/check.sh` runs every local gate.
- Every change ships with a test; external services (model API, S3, DB) are mocked in unit tests, never called.
- A change is not done until verified end to end: containers up, job run, UI checked (headless browser) when the UI changed.
- Model-quality claims need measurements on real examples (`demo/real`), not intuition. State what was and was not verified.

## Security

- Secrets only in `.env` (gitignored); never print, log, commit or paste them. `.env.example` holds names and safe defaults only.
- Never commit `.env`, `demo/real/` (third-party ads) or other people's material.
- The backend never accepts storage keys or paths from clients (images are served by record id).
- External paid APIs are not allowed (UKNF). The only exception: Codiv hosted OpenJev (free) as a temporary step; local run is the target.
- Pin image tags and keep lockfiles committed; run `scripts/audit.sh` before releases and fix findings.
- Destructive commands (`down -v`, `rm -r`, `git reset --hard`) only on this project's dev data and only when asked.

## Project requirements (UKNF HackNation 2026, "InvestWatch")

Source: `UKNF/UKNF - Pełna treść zadania konkursowego.pdf`, analysis: `UKNF/analiza/pytania-do-klienta.md`.

**Section 5, technical requirements (checklist, all mandatory):**
- [ ] Modular, lightweight services; frontend, backend and AI engine separated; no heavy monorepo.
- [ ] Containerised: the whole stack on-premise with **one command** (Docker Compose), reproducible for several people.
- [ ] Open source and on-prem only: free open models (Ollama/vLLM style), open databases and libraries; **no external paid APIs**.
- [ ] Verifiable supply chain: mandatory dependency scanning (npm, pip; Snyk or `npm audit`/`pip-audit`), secrets isolated in `.env`.
- [ ] Documentation: **README is the bare minimum**: Quick Start, hardware requirements, service configuration. No filler ("no AI slop").
- [ ] Scoring: probabilities 0-1, threshold calibration shows the FP/FN trade-off; dashboard with filters (date, source, risk, module), trend charts,
      record status changes, WebSocket alerts for high risk, props-based UI.

**Section 6, what the jury tests:** scraper effectiveness, classification accuracy and the effect of the threshold in the calibration panel,
UI stability and real-time alerts, libraries and their security, console output.

**Section 8, evaluation criteria (0-10, weights):**
1. technology and demo readiness, 30%;
2. **innovation of the development process: is it based on existing standards and is the standardised process of building software with AI assistants described, 20%** (see below);
3. architecture: modules, scalability, openness to extension, 20%;
4. fit to the task specification and preferred technologies, 20%;
5. attractiveness and originality, 10%.
Winning needs at least 5/10. Deliverables: title and description, PDF presentation, README, repository (optional 3-minute video).

## AI-assisted development process (criterion 8.2)

The process used in this repo, to be followed by agents and humans:
1. **Analyse requirements first**: read the contest materials, record hard rules, inconsistencies and open questions with default assumptions (`UKNF/analiza/`).
2. **Write the spec before code**: `specs/spec-investwatch/*.md` with a human-owned, frozen intent, boundaries, an I/O and edge-case matrix and a code map.
3. **Design the architecture and get approval** before multi-file changes (`docs/architecture.md`; use the agent's plan mode, list options, recommend one).
4. **Implement in small verified steps**: one concern per commit; tests with the change; mocks for external services; use the official skills of the tools involved
   (e.g. `dagster-io/skills`, `dagster-expert`) instead of guessing APIs.
5. **Verify**: unit tests, then containers, then the UI in a headless browser; measure model quality on real examples before claiming improvements.
6. **Review**: self-review of the diff and a final check against the requirement checklist above; report honestly what was not verified.
7. **Keep docs in step**: update `docs/specyfikacja-funkcjonalna.md`, `docs/architecture.md`, `TODO.md` and the README only when behaviour or setup changed.

Human decision gates (the agent asks, never decides alone): scope changes, external services or paid APIs, licences, data handling and retention,
choice of model or storage, changes in `scraper/` (teammate-owned), anything destructive or outward-facing (pushes, PRs).
