"""Etap 1 grafu: obiekty landing -> dokumenty w bazie -> batch do modelu (intake_items, documents, analysis_batch)."""

import base64
import mimetypes
import os

import dagster as dg
from pydantic import ValidationError

from pipeline import contract, llm, preprocess, s3, store

MODULES = contract.MODULES


class IngestConfig(dg.Config):
    """Parametry wyboru dokumentów do modelu (Launchpad w UI Dagstera; domyślne z env)."""

    batch_size: int = int(os.environ.get("BATCH_SIZE", "50"))
    reprocess_lookback_days: int = int(os.environ.get("REPROCESS_LOOKBACK_DAYS", "30"))
    modules: list[str] = list(MODULES)


def _data_uri(key: str) -> str:
    """Obraz ze storage jako data-URI (tak przyjmują go modele decyzyjne)."""
    mime = mimetypes.guess_type(key)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(s3.get(key)).decode()}"


@dg.asset(
    description="Nowe obiekty landing (raw/**/*.json) spoza ledgera, zwalidowane kontraktem v2; niepoprawne trafiają do kwarantanny."
)
def intake_items(context: dg.AssetExecutionContext) -> dg.MaterializeResult[list[dict]]:
    s3.ensure_bucket()
    known = store.known_object_keys()
    keys = sorted(k for k in s3.list_keys("raw/") if k.endswith(".json") and k not in known)
    items, rejected = [], 0
    for key in keys:
        try:
            items.append({"key": key, "item": contract.parse(s3.get(key))})
        except (ValueError, ValidationError) as e:  # ValidationError dziedziczy po ValueError
            store.reject(key, str(e)[:500])
            context.log.warning(f"kwarantanna {key}: {e}")
            rejected += 1
    items.sort(
        key=lambda x: (x["item"].captured_at, x["key"])
    )  # wersje stosujemy w kolejności zebrania
    context.log.info(f"nowych obiektów: {len(items)}, odrzuconych: {rejected}")
    return dg.MaterializeResult(
        value=items, metadata={"new_objects": len(items), "rejected": rejected}
    )


@dg.asset(
    description="Obserwacje, dokumenty (wersje treści) i obrazy w Postgresie wg ledgera ingestii; każdy nowy materiał to nowy dokument."
)
def documents(
    context: dg.AssetExecutionContext, intake_items: list[dict]
) -> dg.MaterializeResult[dict]:
    outcomes = {"new": 0, "changed": 0, "unchanged": 0, "stale": 0}
    for entry in intake_items:
        item = entry["item"]
        text = preprocess.clean_text(item.text)
        digest = preprocess.content_hash(text, [i.sha256 for i in item.images])
        outcome = store.ingest(item, entry["key"], text, digest, context.run.run_id)
        outcomes[outcome] += 1
        context.log.info(f"{item.source_key}: {outcome}")
    return dg.MaterializeResult(value=outcomes, metadata=dict(outcomes))


@dg.asset(
    description="Dokumenty do przeliczenia bieżącym modelem: nowe i zmienione zawsze, stare po zmianie modelu tylko z okna wstecz."
)
def analysis_batch(
    context: dg.AssetExecutionContext, config: IngestConfig, documents: dict
) -> dg.MaterializeResult[list[dict]]:
    model = llm.model_id()
    docs, counts = store.select_batch(
        model, config.modules, config.batch_size, config.reprocess_lookback_days
    )
    for d in docs:  # obrazy ładujemy dopiero dla wybranych dokumentów
        for img in d["images"]:
            img["uri"] = _data_uri(img["image_key"])
    context.log.info(f"model {model}: {counts}")
    return dg.MaterializeResult(value=docs, metadata={**counts, "model": model})
