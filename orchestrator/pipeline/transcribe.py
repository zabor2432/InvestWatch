"""Opcjonalna transkrypcja mowy na tekst, lokalnie (Whisper przez Hugging Face), wg specs/spec-investwatch/local-speech-to-text.md.

Zależności (torch, transformers, accelerate, ffmpeg) NIE są w obrazie ani w lockfile: dopiero włączenie kroku wymaga ich doinstalowania.
Model ładowany raz (`_asr`), osobno od samej transkrypcji (`transcribe`); MPS gdy dostępny, inaczej CPU. Bez zewnętrznego API."""

import os
from functools import lru_cache

MODELS = (
    "openai/whisper-large-v3-turbo",
    "bardsai/whisper-small-pl",
)  # domyślny pierwszy; drugi lżejszy, gorszy


def model_id() -> str:
    return os.environ.get("TRANSCRIBE_MODEL", MODELS[0])


@lru_cache
def _asr(model: str):
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    except ImportError as e:
        raise RuntimeError(
            "Transkrypcja wymaga doinstalowania torch, transformers i accelerate oraz ffmpeg "
            "(patrz specs/spec-investwatch/local-speech-to-text.md)"
        ) from e
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.float16 if device == "mps" else torch.float32
    net = AutoModelForSpeechSeq2Seq.from_pretrained(
        model, torch_dtype=dtype, low_cpu_mem_usage=True, use_safetensors=True
    ).to(device)
    proc = AutoProcessor.from_pretrained(model)  # z tego samego repozytorium co model
    return pipeline(
        "automatic-speech-recognition",
        model=net,
        tokenizer=proc.tokenizer,
        feature_extractor=proc.feature_extractor,
        torch_dtype=dtype,
        device=device,
    )


def transcribe(audio_path: str) -> dict:
    """-> {"text": ..., "chunks": [{"timestamp": (od, do), "text": ...}]}; polski wybrany jawnie, pliki dłuższe niż 30 s obsługuje return_timestamps."""
    return _asr(model_id())(
        audio_path,
        return_timestamps=True,
        generate_kwargs={"language": "polish", "task": "transcribe"},
    )
