"""Jedyne miejsce, które zna dostawcę modelu: model decyzyjny (System One), protokół POST /v1/systemone.

Domyślnie OpenJev hostowany przez Codiv (wystarczy TYPESAFE_API_KEY). Ten sam model lokalnie na GPU
(github.com/razorback16/openjev) to tylko zmiana TYPESAFE_BASE_URL. Kontrakt:
classify(state, {pytanie: opis | {instructions, criteria}}, images) -> {pytanie: P(tak) 0-1}.
"""

import os
import time

import httpx

DEFAULT_URL = "https://api.codiv.ai"
DEFAULT_MODEL = "openjev-latest"


def model_id() -> str:
    return os.environ.get("JEV_MODEL", DEFAULT_MODEL)


def _error_type(r: httpx.Response) -> str:
    try:
        return r.json()["detail"]["error_type"]
    except Exception:  # noqa: BLE001
        return ""


def classify(
    state: str,
    questions: dict[str, str | dict],
    images: list[str] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, float]:
    """`questions`: opis (str) albo {"instructions": ..., "criteria": {"true": ..., "false": ...}};
    `images`: obrazy jako data-URI (np. screenshot reklamy)."""
    base = os.environ.get("TYPESAFE_BASE_URL", DEFAULT_URL).rstrip("/")
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key and base.startswith("https://"):
        raise RuntimeError(
            "Ustaw TYPESAFE_API_KEY w .env (darmowy klucz: https://codiv.ai/dashboard)"
        )
    body = {
        "model": model_id(),
        "state": state,
        "questions": {
            k: {"type": "noul", **(q if isinstance(q, dict) else {"instructions": q})}
            for k, q in questions.items()
        },
    }
    if images:
        body["images"] = images
    headers = {"Authorization": f"Bearer {key}"} if key else {}  # lokalny serwer nie wymaga klucza
    http = client or httpx.Client(timeout=120)
    for attempt in range(4):
        r = http.post(f"{base}/v1/systemone", json=body, headers=headers)
        retryable = r.status_code in (429, 529) and _error_type(r) != "quota_exceeded_error"
        if not retryable or attempt == 3:
            break
        try:
            delay = float(r.headers["retry-after"])
        except (KeyError, ValueError):
            delay = 2**attempt
        time.sleep(delay)
    if r.status_code in (401, 403):
        raise RuntimeError(f"API odrzuciło klucz (HTTP {r.status_code}): sprawdź TYPESAFE_API_KEY")
    if _error_type(r) == "quota_exceeded_error":
        raise RuntimeError("Wyczerpany limit tokenów konta w API modelu")
    r.raise_for_status()
    answers = {k: float(a["noul"]) for k, a in r.json()["answers"].items()}
    missing = set(questions) - set(answers)
    if missing or any(not 0 <= v <= 1 for v in answers.values()):
        raise ValueError(f"niepoprawna odpowiedź modelu (brak: {sorted(missing)}): {answers}")
    return answers
