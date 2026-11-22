"""Polish-only filter.

1. Script: a text whose letters are mostly not Latin (Arabic, Chinese, Cyrillic, ...) is not Polish, whatever its
   length - lingua cannot be asked about scripts it was not built for, and short texts ("326期 彩图") skip it.
2. Language: lingua over Polish and the Latin-script languages that turn up in the sources, so a Dutch or Indonesian
   text is recognised as such instead of "unsure".
Texts too short for lingua (and without a non-Latin script) are kept: too little signal to reject them.
"""

import unicodedata
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

_LANGS = [
    Language.POLISH, Language.ENGLISH, Language.GERMAN, Language.CZECH, Language.SLOVAK, Language.SPANISH,
    Language.FRENCH, Language.ITALIAN, Language.PORTUGUESE, Language.DUTCH, Language.ROMANIAN, Language.HUNGARIAN,
    Language.SWEDISH, Language.DANISH, Language.BOKMAL, Language.FINNISH, Language.CROATIAN, Language.SLOVENE,
    Language.LITHUANIAN, Language.LATVIAN, Language.ESTONIAN, Language.TURKISH, Language.INDONESIAN, Language.MALAY,
    Language.VIETNAMESE, Language.TAGALOG, Language.CATALAN, Language.RUSSIAN, Language.UKRAINIAN,
]
MIN_CHARS = 25  # shorter texts: lingua is not asked
MAX_NON_LATIN = 0.3  # share of non-Latin letters above which a text is rejected
SCRIPT_CODES = {"ARABIC": "ar", "CJK": "zh", "HIRAGANA": "ja", "KATAKANA": "ja", "HANGUL": "ko", "CYRILLIC": "cyrillic",
                "HEBREW": "he", "GREEK": "el", "THAI": "th", "DEVANAGARI": "hi"}


@lru_cache
def _detector():
    return LanguageDetectorBuilder.from_languages(*_LANGS).build()


def _script(ch: str) -> str:
    name = unicodedata.name(ch, "")
    return name.split(" ", 1)[0] if name else ""


def non_latin(text: str) -> str | None:
    """Code of the dominant non-Latin script ("ar", "zh", ...) when most letters are not Latin, else None."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    other = [_script(c) for c in letters if _script(c) != "LATIN"]
    if len(other) / len(letters) <= MAX_NON_LATIN:
        return None
    top = max(set(other), key=other.count)
    return SCRIPT_CODES.get(top, top.lower() or "non-latin")


def detect(text: str) -> str | None:
    """ISO 639-1 code (or script code) of the text, None when unsure."""
    text = (text or "").strip()
    if script := non_latin(text[:5000]):
        return script
    if len(text) < MIN_CHARS:
        return None
    lang = _detector().detect_language_of(text[:5000])
    return lang.iso_code_639_1.name.lower() if lang else None


def is_polish(text: str) -> tuple[bool, str | None]:
    code = detect(text)
    return (code in (None, "pl"), code)
