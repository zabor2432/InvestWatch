"""Zapis i odczyt Postgresa: obserwacje, dokumenty (wersje), ledger ingestii, wyniki 0-1, log wywołań modelu."""

import logging
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pipeline.contract import IntakeItem


def _connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


# --- ingestia -------------------------------------------------------------------------------------------------


def known_object_keys() -> set[str]:
    """Obiekty landing, które już przeszły przez ledger albo zostały odrzucone (nie wchodzą ponownie)."""
    with _connect() as c:
        rows = c.execute(
            "SELECT object_key FROM ingestions UNION SELECT object_key FROM intake_rejections"
        ).fetchall()
    return {r["object_key"] for r in rows}


def reject(object_key: str, reason: str) -> None:
    with _connect() as c:
        c.execute(
            "INSERT INTO intake_rejections (object_key, reason) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (object_key, reason),
        )


def ingest(
    item: IntakeItem, object_key: str, text: str | None, content_hash: str, run_id: str
) -> str:
    """Upsert obserwacji i dokumentu z obiektu landing. Zwraca 'new' (nowy materiał), 'changed' (nowa wersja),
    'unchanged' (ta sama treść) albo 'stale' (starsza wersja niż bieżąca: tylko ledger)."""
    obs = item.observation
    with _connect() as c:
        obs_id = c.execute(
            "INSERT INTO observations (platform, advertiser_handle, advertiser_name, advertiser_url, advertised_firm) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (platform, advertiser_handle, advertised_firm) DO UPDATE SET "
            "advertiser_name = COALESCE(EXCLUDED.advertiser_name, observations.advertiser_name), "
            "advertiser_url = COALESCE(EXCLUDED.advertiser_url, observations.advertiser_url) RETURNING id",
            (
                item.source.platform,
                obs.advertiser.handle,
                obs.advertiser.name,
                obs.advertiser.url,
                obs.advertised_firm,
            ),
        ).fetchone()["id"]
        existing = c.execute(
            "SELECT id, content_hash, captured_at FROM documents WHERE source_key = %s",
            (item.source_key,),
        ).fetchone()
        if existing and existing["content_hash"] == content_hash:
            outcome, doc_id = "unchanged", existing["id"]
        elif existing and existing["captured_at"] > item.captured_at:
            outcome, doc_id = "stale", existing["id"]
        else:
            outcome = "changed" if existing else "new"
            doc_id = c.execute(
                "INSERT INTO documents (source_key, platform, external_id, module, observation_id, source_url, title, "
                "text, lang, published_at, captured_at, content_hash, ground_truth, manipulated) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (source_key) DO UPDATE SET module = EXCLUDED.module, observation_id = EXCLUDED.observation_id, "
                "source_url = EXCLUDED.source_url, title = EXCLUDED.title, text = EXCLUDED.text, lang = EXCLUDED.lang, "
                "published_at = EXCLUDED.published_at, captured_at = EXCLUDED.captured_at, "
                "content_hash = EXCLUDED.content_hash, ground_truth = EXCLUDED.ground_truth, "
                "manipulated = EXCLUDED.manipulated RETURNING id",
                (
                    item.source_key,
                    item.source.platform,
                    item.source.external_id,
                    item.module,
                    obs_id,
                    item.source.url,
                    item.title,
                    text,
                    item.lang,
                    item.published_at,
                    item.captured_at,
                    content_hash,
                    item.label,
                    Jsonb(item.manipulated.model_dump()) if item.manipulated else None,
                ),
            ).fetchone()["id"]
            c.execute("DELETE FROM document_images WHERE document_id = %s", (doc_id,))
            for img in item.images:
                c.execute(
                    "INSERT INTO document_images (document_id, variant, focus, image_key, sha256, width, height) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (doc_id, img.variant, img.focus, img.key, img.sha256, img.width, img.height),
                )
        c.execute(
            "INSERT INTO ingestions (document_id, object_key, content_hash, run_id) VALUES (%s, %s, %s, %s)",
            (doc_id, object_key, content_hash, run_id),
        )
    return outcome


# --- wybór batcha do modelu -----------------------------------------------------------------------------------


NEEDS_ANALYSIS = """
    SELECT d.id, d.source_key, d.module, d.source_url, d.title, d.text, d.content_hash, d.ground_truth,
           coalesce(d.published_at, d.captured_at) AS ref_at,
           NOT EXISTS (SELECT 1 FROM results r WHERE r.document_id = d.id AND r.content_hash = d.content_hash) AS fresh
    FROM documents d
    WHERE d.module = ANY(%(modules)s)
      AND NOT EXISTS (SELECT 1 FROM results r WHERE r.document_id = d.id AND r.model = %(model)s
                      AND r.content_hash = d.content_hash)
"""


def plan_batch(rows: list[dict], since, limit: int) -> tuple[list[dict], dict]:
    """Wybór z kandydatów (wiersze NEEDS_ANALYSIS): nowe i zmienione (`fresh`) zawsze, pozostałe tylko gdy
    `ref_at >= since` (okno wstecz po zmianie modelu). Nowe idą pierwsze. Zwraca (batch, liczniki)."""
    selected = [r for r in rows if r["fresh"] or r["ref_at"] >= since]
    selected.sort(
        key=lambda r: not r["fresh"]
    )  # sort stabilny: w grupie kolejność wejściowa (najnowsze pierwsze)
    batch = selected[:limit]
    counts = {
        "fresh": sum(r["fresh"] for r in rows),
        "reprocess_in_window": sum(not r["fresh"] and r["ref_at"] >= since for r in rows),
        "skipped_outside_window": sum(not r["fresh"] and r["ref_at"] < since for r in rows),
        "selected": len(batch),
        "deferred_by_batch_size": len(selected) - len(batch),
    }
    return batch, counts


def select_batch(
    model: str, modules: list[str], limit: int, lookback_days: int
) -> tuple[list[dict], dict]:
    """Dokumenty do przeliczenia bieżącym modelem (z obrazami) i liczniki; reguły wyboru w `plan_batch`."""
    with _connect() as c:
        rows = c.execute(
            NEEDS_ANALYSIS + " ORDER BY ref_at DESC, d.id", {"modules": modules, "model": model}
        ).fetchall()
        since = c.execute(
            "SELECT now() - make_interval(days => %s) AS since", (lookback_days,)
        ).fetchone()["since"]
        batch, counts = plan_batch(rows, since, limit)
        images = c.execute(
            "SELECT document_id, variant, focus, image_key FROM document_images WHERE document_id = ANY(%s)",
            ([r["id"] for r in batch],),
        ).fetchall()
    by_doc: dict[int, list[dict]] = {}
    for i in images:
        by_doc.setdefault(i["document_id"], []).append(i)
    docs = [
        {
            "id": r["id"],
            "key": r["source_key"],
            "module": r["module"],
            "source_url": r["source_url"],
            "title": r["title"],
            "text": r["text"],
            "hash": r["content_hash"],
            "label": r["ground_truth"],
            "images": by_doc.get(r["id"], []),
        }
        for r in batch
    ]
    return docs, counts


# --- wyniki ---------------------------------------------------------------------------------------------------


def done_ids(docs: list[dict], model: str) -> set[int]:
    """Dokumenty z wynikiem tego modelu dla aktualnej wersji treści."""
    with _connect() as c:
        rows = c.execute(
            "SELECT r.document_id FROM results r JOIN unnest(%s::bigint[], %s::text[]) AS t(id, h) "
            "ON r.document_id = t.id AND r.content_hash = t.h WHERE r.model = %s",
            ([d["id"] for d in docs], [d["hash"] for d in docs], model),
        ).fetchall()
    return {r["document_id"] for r in rows}


def save_result(
    doc_id: int, module: str, model: str, content_hash: str, score: float, details: dict
) -> int:
    with _connect() as c:
        result_id = c.execute(
            "INSERT INTO results (document_id, module, model, content_hash, score, details) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (document_id, module, model, content_hash) "
            "DO UPDATE SET score = EXCLUDED.score, details = EXCLUDED.details, created_at = now() "
            "RETURNING id",
            (doc_id, module, model, content_hash, score, Jsonb(details)),
        ).fetchone()["id"]
        if score >= float(os.environ.get("ALERT_THRESHOLD", "0.9")):
            c.execute("SELECT pg_notify('high_risk', %s)", (str(result_id),))
        return result_id


def log_call(
    doc_id: int,
    module: str,
    model: str,
    state: str,
    answers: dict | None,
    score: float | None,
    latency_ms: int,
    error: str | None = None,
) -> None:
    """Zapis wywołania modelu do podglądu. Najlepsze starania: błąd logowania nie psuje przetwarzania."""
    try:
        with _connect() as c:
            c.execute(
                "INSERT INTO model_calls (document_id, module, model, state, answers, score, latency_ms, error) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    doc_id,
                    module,
                    model,
                    state,
                    Jsonb(answers) if answers is not None else None,
                    score,
                    latency_ms,
                    error,
                ),
            )
    except Exception:
        logging.getLogger(__name__).warning("nie zapisano model_calls", exc_info=True)
