---
title: 'Wybór modelu decyzyjnego i self-hosting'
type: 'guide'
created: '2026-11-22'
status: 'done'
context: ['orchestrator/pipeline/llm.py', '.env.example', 'https://github.com/razorback16/openjev']
---

# Wybór modelu decyzyjnego i self-hosting

The decision model is any [OpenJev](https://github.com/razorback16/openjev) server speaking `POST /v1/systemone` (yes/no questions → probability 0-1).
Only `orchestrator/pipeline/llm.py` knows the provider. Choose it in `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `TYPESAFE_BASE_URL` | `https://api.codiv.ai` | server to call; point it at your own server to self-host |
| `JEV_MODEL` | `openjev-latest` | model id sent to the server (also stored with every result, see below) |
| `TYPESAFE_API_KEY` | empty | needed for Codiv; for a local `http://` server leave it empty (or set it to the server's `OPENJEV_API_KEY`) |

Model ids of an OpenJev server (full list and limits: its README): `openjev-latest` (DiffusionGemma 26B-A4B, text and images),
`clef-1.0` and `clef-flash-1.0` (text and images, NVIDIA Blackwell only), and text-only `laya-1.0`, `verdict-1.4`, `clm-v0.1`, `jevk5-0.3`.
**Module 2 sends screenshots, so use a model that accepts images** (`openjev-latest` or a `clef` model); text-only models answer such requests with HTTP 400.
Whether a given id is available on Codiv's free plan is not verified here; check on codiv.ai.

Changing `JEV_MODEL` keeps old results (they are stored per model) and re-scores documents from the last `REPROCESS_LOOKBACK_DAYS` days on the next **Odśwież dane**;
the Report view has a model selector to compare models against analyst ratings.

## Self-hosting modelu

Needs an NVIDIA GPU with 24 GB or more (the `clef` models: Blackwell), or Apple silicon with about 16 GB free. Not run in this repo's tests; steps follow the OpenJev README.

```bash
# NVIDIA: prebuilt image, first start downloads about 18 GB of weights
git clone https://github.com/razorback16/openjev && cd openjev
docker compose up -d && curl localhost:8080/v1/models

# Apple silicon (no Docker): runs on the host
pip install -e '.[mlx]' && OPENJEV_BACKEND=mlx python -m openjev      # 127.0.0.1:8080

# another model (needs the shared base image first, see the OpenJev README)
docker compose --profile clef up -d        # clef-flash-1.0; add it to OPENJEV_MODEL_ROUTES
```

Then in this project's `.env`:

```bash
TYPESAFE_BASE_URL=http://host.containers.internal:8080   # Podman; Docker Desktop: host.docker.internal
JEV_MODEL=openjev-latest                                 # or clef-flash-1.0 (as routed on your server)
TYPESAFE_API_KEY=                                        # empty, unless the server sets OPENJEV_API_KEY
```

`docker compose up -d --force-recreate` and click **Odśwież dane**. The server must be reachable from the Dagster containers: OpenJev binds `127.0.0.1` by default,
so if the containers cannot connect, publish its port on the host address (or run it on another machine) and put that address in `TYPESAFE_BASE_URL`.
On Linux Docker `host.docker.internal` does not exist by default; use the host's IP.

