"""Przygotowanie obrazów dla modelu. Model czyta każdy obraz w stałym budżecie (~280 tokenów), więc drobny
tekst (stopka z ryzykiem) ocenia się lepiej na osobnym wycinku niż na całym obrazie."""

import base64
import io

from PIL import Image

MAX_SIDE = 1024  # zalecenie dostawcy: dłuższy bok ~1024 px
FOOTER_FRACTION = 0.35  # informacja o ryzyku zwykle jest w dolnej części reklamy


def _load(data_uri: str) -> Image.Image:
    """Spłaszcza przezroczystość do bieli (inaczej tło wychodzi czarne i obraz różni się nie tylko treścią)."""
    img = Image.open(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1])))
    if img.mode in ("RGBA", "LA", "P"):
        img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img.convert("RGBA"))
    return img.convert("RGB")


def _png_uri(img: Image.Image) -> str:
    img = img.copy()
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def full(data_uri: str) -> str:
    return _png_uri(_load(data_uri))


def footer(data_uri: str) -> str:
    """Dolny pas obrazu (ze stopką o ryzyku)."""
    img = _load(data_uri)
    w, h = img.size
    return _png_uri(img.crop((0, int(h * (1 - FOOTER_FRACTION)), w, h)))
