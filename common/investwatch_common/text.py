"""Name normalisation shared by the scraper and the analytic modules.

Every comparison is case- and diacritic-insensitive: "ŚLĄSKI" == "slaski".
"""

import re

from unidecode import unidecode

# Longest first, so "sp. z o.o." is removed before "sp.".
LEGAL_FORMS = sorted(
    [
        "spolka akcyjna", "s.a.", "sa", "sp. z o.o.", "sp. z o. o.", "sp.z o.o.", "sp. k.", "sp.k.",
        "sp. j.", "s.k.a.", "dom maklerski", "dm", "gmbh", "ag", "se", "ltd.", "ltd", "limited", "plc",
        "n.v.", "nv", "b.v.", "bv", "s.p.a.", "spa", "s.a.s.", "sas", "s.r.l.", "srl", "a.s.", "as",
        "ab", "oy", "a/s", "aps", "uab", "o.c.p.", "inc.", "inc", "llc", "s.l.", "sl", "s.a.u.",
        "e.u.", "kg", "co.", "corp.",
    ],
    key=len,
    reverse=True,
)
# a legal form is only stripped after the first word ("APS Financial" keeps "aps", "XTB S.A." loses "s.a.")
_LEGAL_RE = re.compile(
    r"(?<=\S)(\s+)(" + "|".join(re.escape(f) for f in LEGAL_FORMS) + r")(?![\w])"
)
_SPACES_RE = re.compile(r"\s+")
_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|pl|eu|net|org|io|co|uk|de|cy|cz|sk|hu|it|es|fr|"
    r"nl|ee|lt|lv|ro|bg|hr|se|dk|no|fi|at|ch|be|ie|pt|gr|lu|mt|si|info|biz|club|news|exchange|trade|"
    r"markets|finance|capital|invest|online|app|to|xyz|top|pro|ltd|global|me|us|cc))\b(?:/[^\s,;)]*)?",
    re.IGNORECASE,
)


def fold(text: str) -> str:
    """Lower-case and strip diacritics."""
    return unidecode(text or "").casefold()


def normalize_name(name: str) -> str:
    """Folded name without legal forms and punctuation noise, e.g. 'XTB S.A.' -> 'xtb'."""
    s = fold(name)
    s = re.sub(r"\(.*?\)", " ", s)  # "(PKO BP S.A.)", "(formerly ...)"
    s = re.sub(r"<[^>]+>", " ", s)
    prev = None
    while prev != s:  # "dom maklerski banku ... s.a." -> several forms
        prev, s = s, _LEGAL_RE.sub(" ", s)
    s = re.sub(r"[\"'„”«»,;:]+", " ", s)
    s = _SPACES_RE.sub(" ", s).strip(" .-&")
    return s


def extract_domains(text: str) -> list[str]:
    """Bare domains (no scheme, no www) found in free text."""
    found: list[str] = []
    for m in _DOMAIN_RE.finditer(text or ""):
        d = m.group(1).lower()
        if d.startswith("www."):
            d = d[4:]
        if d not in found:
            found.append(d)
    return found
