# orchestrator/ (Dagster)

Applies on top of the root `AGENTS.md`. Python + uv; run `uv run ruff check . && uv run pytest -q` here.

- **Assets, not ops/jobs.** Graph: `intake_items → documents → analysis_batch → module_splits → ad_scores / rule_scores / advisory_scores`
  (`pipeline/definitions.py` assembles the stages: `ingest.py` → `prepare.py` → `scoring.py`). `analysis_batch` takes `IngestConfig` (`batch_size`, `reprocess_lookback_days`, `modules`): what goes to the model is a run parameter. Name assets with nouns, annotate return types, return `MaterializeResult` with metadata, retry with `RetryPolicy`.
  No sensors or schedules by default: processing starts manually (Materialize all / job `process_batch`). Check the `dagster-expert` skill before using an API.
- **Optional transcription (skipped).** `transcribed_batch` (between `analysis_batch` and `preprocessed_batch`) turns audio/video into text with local Whisper
  (`pipeline/transcribe.py`, spec `specs/spec-investwatch/local-speech-to-text.md`); it is off (`TRANSCRIBE_ENABLED=false`, or `enabled` in the run config) because no source delivers audio yet.
  Turning it on also needs `torch`, `transformers`, `accelerate` and `ffmpeg` installed (not in the image) and documents carrying an `audio_key` in the pipeline bucket.
- **One model client.** Only `pipeline/llm.py` knows the model provider (`POST /v1/systemone`, `noul` questions, answers are P(yes) 0-1).
  Config: `TYPESAFE_API_KEY`, optional `TYPESAFE_BASE_URL`, `JEV_MODEL`. Provider swaps must not touch other files.
- **Prompts are data.** Module 2 questions live in `pipeline/rules.py` (`RULES` with violation/compliance criteria and examples, `SPEC` = UKNF wording,
  `VISUAL_QUESTIONS` for image rules). Visual rules are asked separately on the footer crop (`pipeline/images.py`); rule 8 is asked only for a desktop+mobile image pair (else n/a).
  Concrete questions about what is visible beat abstract "does it violate X" (measured, see `TODO.md`).
- **Idempotent, versioned.** Results are unique per (document, module, model, content hash). New and changed versions are always scored; after a model change only documents inside `reprocess_lookback_days` are re-scored. A failed document never loses the rest.
- **Storage.** Reads `S3_ENDPOINT_URL`, `MINIO_ROOT_USER/PASSWORD`, bucket `PIPELINE_S3_BUCKET`; input is the v2 contract (`pipeline/contract.py`, `docs/data-contract.md`): immutable `raw/{platform}/{external_id}/{hash12}.json`; invalid objects go to `intake_rejections`. Change the contract only together with `docs/intake-item.schema.json` (a test checks it).
- Tests stub `s3`, `store`, `analyze` and `llm` (see `tests/test_pipeline.py`); never call the real API.
