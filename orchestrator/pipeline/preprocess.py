"""Preprocessing tekstu przed modelem (UKNF §3 pkt 2): usuwanie tagów HTML, normalizacja, usuwanie duplikatów,
reprezentacja wektorowa (tokeny i wektor cech). Czysty Python, bez zależności; wektor służy do wykrywania
(prawie) powtórzonych materiałów, a nie do klasyfikacji (tę robi model decyzyjny)."""

import hashlib
import html
import math
import re
import unicodedata
import zlib

DIM = 256
NEAR_DUPLICATE = 0.95  # podobieństwo cosinusowe, od którego dwa teksty uznajemy za ten sam materiał
_TAGS = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.S | re.I)
_INVISIBLE = re.compile(r"[​-‏⁠﻿\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(text: str | None, limit: int = 6000) -> str | None:
    """HTML -> zwykły tekst: bez tagów i skryptów, encje rozwinięte, Unicode NFKC, bez znaków niewidocznych, białe znaki zwinięte."""
    if not text:
        return None
    text = unicodedata.normalize("NFKC", html.unescape(_TAGS.sub(" ", text)))
    text = _INVISIBLE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()[:limit] or None


def content_hash(text: str | None, image_digests: list[str] | None = None) -> str:
    """Hash wersji dokumentu: tekst i skróty wszystkich obrazów. Zmiana któregokolwiek = nowa wersja."""
    parts = [(text or "").lower(), *sorted(image_digests or [])]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def tokens(text: str | None) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())


def embed(toks: list[str]) -> list[float]:
    """Wektor cech (feature hashing, znak z hasha, normalizacja L2): deterministyczny, bez modelu i bez pobierania wag."""
    vec = [0.0] * DIM
    for t in toks:
        h = zlib.crc32(t.encode())
        vec[h % DIM] += 1.0 if (h >> 16) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def find_duplicates(docs: list[dict], threshold: float = NEAR_DUPLICATE) -> dict[int, int]:
    """{id duplikatu: id reprezentanta} w obrębie modułu. Duplikat to materiał bez obrazów, którego tekst jest taki sam
    albo prawie taki sam (cosinus >= threshold) jak wcześniejszego. Materiały z obrazami oceniamy zawsze osobno."""
    reps: list[tuple[dict, list[float]]] = []
    out: dict[int, int] = {}
    for d in docs:
        if d.get("images") or not d.get("text"):
            continue
        vec = embed(tokens(d["text"]))
        match = next(
            (r for r, v in reps if r["module"] == d["module"] and cosine(vec, v) >= threshold), None
        )
        if match:
            out[d["id"]] = match["id"]
        else:
            reps.append((d, vec))
    return out
