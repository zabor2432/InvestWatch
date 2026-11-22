"""Etap 2 grafu: przygotowanie batcha przed modelem (opcjonalna transkrypcja, preprocessing tekstu, podział wg modułu)."""

import os
import tempfile
from pathlib import Path

import dagster as dg

from pipeline import preprocess, s3, transcribe
from pipeline.ingest import MODULES


class TranscribeConfig(dg.Config):
    """Krok opcjonalny: domyślnie wyłączony (nie ma jeszcze danych wideo/audio)."""

    enabled: bool = os.environ.get("TRANSCRIBE_ENABLED", "false").lower() == "true"


@dg.asset(
    description="Opcjonalna transkrypcja audio/wideo na tekst (Whisper, lokalnie); domyślnie pomijana, bo żadne źródło nie dostarcza jeszcze audio."
)
def transcribed_batch(
    context: dg.AssetExecutionContext, config: TranscribeConfig, analysis_batch: list[dict]
) -> dg.MaterializeResult[list[dict]]:
    if not config.enabled:
        context.log.info("transkrypcja pominięta (TRANSCRIBE_ENABLED wyłączone)")
        return dg.MaterializeResult(
            value=analysis_batch, metadata={"skipped": True, "reason": "wyłączone"}
        )
    docs, done = [], 0
    for d in analysis_batch:
        if d.get("audio_key") and not d.get("transcribed"):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / Path(d["audio_key"]).name
                path.write_bytes(s3.get(d["audio_key"]))
                text = transcribe.transcribe(str(path))["text"].strip()
            d = {**d, "text": "\n\n".join(x for x in (d["text"], text) if x), "transcribed": True}
            done += 1
        docs.append(d)
    return dg.MaterializeResult(
        value=docs, metadata={"skipped": False, "transcribed": done, "model": transcribe.model_id()}
    )


@dg.asset(
    description="Preprocessing przed podziałem na moduły (UKNF): tokeny i wektor cech, wykrywanie duplikatów tekstu; oczyszczenie HTML i normalizacja są w `documents`."
)
def preprocessed_batch(
    context: dg.AssetExecutionContext, transcribed_batch: list[dict]
) -> dg.MaterializeResult[list[dict]]:
    docs = [
        dict(d) for d in transcribed_batch
    ]  # tekst jest już oczyszczony w `documents` (to on wchodzi do hasha wersji)
    dups = preprocess.find_duplicates(docs)
    keys = {d["id"]: d["key"] for d in docs}
    for d in docs:
        if d["id"] in dups:
            d["duplicate_of"] = dups[d["id"]]
            context.log.info(
                f"{d['key']}: duplikat {keys[dups[d['id']]]}, model oceni tylko oryginał"
            )
    n_tokens = sum(len(preprocess.tokens(d["text"])) for d in docs)
    return dg.MaterializeResult(
        value=docs,
        metadata={
            "documents": len(docs),
            "tokens": n_tokens,
            "duplicates": len(dups),
            "text_documents": sum(bool(d["text"]) for d in docs),
        },
    )


@dg.multi_asset(
    outs={
        "third_party_ads_docs": dg.AssetOut(),
        "self_promotion_docs": dg.AssetOut(),
        "non_investment_docs": dg.AssetOut(),
    },
    description="Każdy moduł AI dostaje swoją część batcha (wg kolumny `module`).",
)
def module_splits(preprocessed_batch: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    return tuple([d for d in preprocessed_batch if d["module"] == m] for m in MODULES)  # type: ignore[return-value]
