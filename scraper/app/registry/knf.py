"""Parsers of the KNF register pages (knf.gov.pl).

Each parser returns entries shaped like the JSON files in docs/firm_registry (`name` + list-specific fields),
so seed files and live pages go through the same mapping (app.registry.records).
"""

import html as htmllib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

from investwatch_common.enums import RegistryList
from investwatch_common.text import fold

from app.http import HttpClient
from app.log import log

KNF = "https://www.knf.gov.pl"
FI = f"{KNF}/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych"
BANKING = f"{KNF}/podmioty/Podmioty_sektora_bankowego"

URLS: dict[RegistryList, str] = {
    RegistryList.BROKERAGE_BANKS: f"{FI}/Banki_prowadzace_dzialalnosc_maklerska",
    RegistryList.BROKERAGE_FIRMS: f"{FI}/domy_maklerskie",
    RegistryList.FOREIGN_BRANCHES: f"{FI}/notyfikowane_firmy_inwestycyjne_oddzialy",
    RegistryList.FOREIGN_NO_BRANCH: f"{FI}/notyfikowane_zagraniczne_firmy_inwestycyjne",
    RegistryList.CREDIT_INSTITUTIONS_BRANCHES: f"{BANKING}/zestawienie_notyfikacji_dot_dzialnosci_instucji_kredytowych_na_terytorium_RP_poprzez_oddzial",
    RegistryList.CREDIT_INSTITUTIONS_CROSS_BORDER: f"{BANKING}/zestawienie_notyfikacji_instytucji_kredytowych_na_terytorium_RP",
    RegistryList.REVOKED_LICENCES: f"{FI}/rejestr_firm_inwestycyjnych_ktorym_cofnieto_zezwolenie_na_dzialalnosc_maklerska",
    RegistryList.KNF_PUBLIC_WARNINGS: f"{KNF}/dla_konsumenta/ostrzezenia_publiczne",
    RegistryList.AGENTS_LEGAL: f"{FI}/agenci_firm_inwestycyjnych_osoby_prawne",
    RegistryList.AGENTS_NATURAL: f"{FI}/agenci_firm_inwestycyjnych_osoby_fizyczne",
}


# ---------------------------------------------------------------- HTML helpers

def _lines(fragment: str) -> list[str]:
    s = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", fragment)
    s = re.sub(r"<[^>]+>", "", s)
    return [re.sub(r"\s+", " ", x).strip() for x in htmllib.unescape(s).split("\n") if x.strip()]


def _cell(fragment: str) -> tuple[list[str], list[str]]:
    """(current lines, struck-through lines). KNF marks former names/addresses with <strike>."""
    # KNF formatting noise: "<strike> <br />B</strike>iuro Maklerskie" - a 1-2 character strike is not a former name
    fragment = re.sub(
        r"<strike>(.*?)</strike>",
        lambda m: m.group(1) if len("".join(_lines(m.group(1)))) <= 2 else m.group(0),
        fragment,
        flags=re.S,
    )
    struck = [ln for part in re.findall(r"<strike>(.*?)</strike>", fragment, flags=re.S) for ln in _lines(part)]
    current = _lines(re.sub(r"<strike>.*?</strike>", "", fragment, flags=re.S))
    return current, struck


def card_tables(page: str) -> list[dict[str, tuple[list[str], list[str]]]]:
    """KNF 'card' tables: one <table> per entity with <th>label</th><td>value</td> rows."""
    out = []
    for tb in re.findall(r'<table class="rounded-default tooltip-table-parent">(.*?)</table>', page, flags=re.S):
        rows = re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", tb, flags=re.S)
        out.append({" ".join(_lines(k)): _cell(v) for k, v in rows})
    return out


def _codes(lines: list[str]) -> list[str]:
    return [c.strip() for c in ", ".join(lines).split(",") if c.strip() and c.strip() != "-"]


def _iso(date: str) -> str:
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", date.strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else date.strip()


def _get(t: dict, label: str) -> tuple[list[str], list[str]]:
    return t.get(label, ([], []))


def next_payload(page: str) -> str:
    """Concatenated Next.js flight data (`self.__next_f.push([1, "..."])`)."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>', page, flags=re.S)
    return "".join(json.loads(p) for p in parts)


def next_entities(page: str) -> list[dict]:
    """Entities embedded as JSON objects {"id", "name", "attributes": [{"name", "value"}...]}."""
    s, dec, out, seen = next_payload(page), json.JSONDecoder(), [], set()
    for m in re.finditer(r'\{"id":\d+,"name":', s):
        try:
            obj, _ = dec.raw_decode(s, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and "attributes" in obj and obj["id"] not in seen:
            seen.add(obj["id"])
            out.append(obj)
    return out


# ---------------------------------------------------------------- per-list parsers

def parse_domestic(page: str) -> list[dict]:
    """Banks conducting brokerage activity and brokerage houses (same layout)."""
    entries = []
    for t in card_tables(page):
        cur, old = _get(t, "Nazwa")
        if not cur:
            continue
        contact = " ".join(_get(t, "Dane Teleadresowe")[0])
        e = {
            "name": cur[0],
            "contact": contact,
            "license_date": _iso(" ".join(_get(t, "Data zezwolenia")[0])),
            "scope_codes": [int(c) for c in _codes(_get(t, "Zakres działalności")[0]) if c.isdigit()],
        }
        if cur[1:]:
            e["other_names_as_listed"] = cur[1:]
        if old:
            e["former_names"] = old
        entries.append(e)
    return entries


def parse_foreign_branches(page: str) -> list[dict]:
    entries = []
    for t in card_tables(page):
        cur, old = _get(t, "Nazwa podmiotu")
        if not cur:
            continue
        e = {
            "name": " ".join(cur),
            "registered_address": ", ".join(_get(t, "Adres siedziby")[0]),
            "home_country": " ".join(_get(t, "Państwo macierzyste")[0]),
            "supervisor": " ".join(_get(t, "Organ nadzoru")[0]),
            "krs_entry_date": " ".join(_get(t, "Data wpisu do KRS")[0]) or None,
            "financial_instruments_C": _codes(_get(t, "Instrumenty finansowe (C)")[0]),
            "investment_services_A": _codes(_get(t, "Usługi inwestycyjne (A)")[0]),
            "additional_services_B": _codes(_get(t, "Usługi dodatkowe (B)")[0]),
            "polish_branch_address": ", ".join(_get(t, "Dane teleadresowe oddziału w Polsce - adres")[0]),
            "polish_branch_phone": " ".join(_get(t, "Dane teleadresowe oddziału w Polsce - telefon")[0]),
            "notification_received": " ".join(_get(t, "Data wpływu zawiadomienia")[0]),
        }
        if old:
            e["former_names"] = old
        entries.append({k: v for k, v in e.items() if v not in (None, "", [])})
    return entries


SEC = {
    "C": "C - Instrumenty finansowe z sekcji C załącznika I Dyrektywy 2014/65/UE",
    "A": "A - Usługi inwestycyjne i działalność inwestycyjna z sekcji A załącznika I Dyrektywy 2014/65/UE",
    "B": "B - Usługi dodatkowe z sekcji B załącznika I Dyrektywy 2014/65/UE",
}


def parse_foreign_no_branch(page: str, letter: str | None = None) -> list[dict]:
    entries = []
    for t in card_tables(page):
        name, former = _get(t, "Nazwa podmiotu")
        if not name:
            continue
        e = {
            "name": " ".join(name),
            "registered_address": ", ".join(_get(t, "Adres siedziby")[0]),
            "home_country": " ".join(_get(t, "Państwo macierzyste")[0]),
            "supervisor_website": " ".join(_get(t, "Organ nadzoru")[0]),
            "financial_instruments_C": _codes(_get(t, SEC["C"])[0]),
            "investment_services_A": _codes(_get(t, SEC["A"])[0]),
            "additional_services_B": _codes(_get(t, SEC["B"])[0]),
            "notification_history": re.sub(r":\s*;", ":", "; ".join(_get(t, "Data wpływu zawiadomienia")[0])),
            "letter_filter": letter,
            "former_names": former,
            "former_addresses": _get(t, "Adres siedziby")[1],
            "additional_info": _get(t, "Dodatkowe informacje")[0],
            "former_additional_info": _get(t, "Dodatkowe informacje")[1],
            "via_agent": _get(t, "Za pośrednictwem agenta")[0],
            "former_agents": _get(t, "Za pośrednictwem agenta")[1],
        }
        old_scope = {k: _codes(_get(t, v)[1]) for k, v in SEC.items()}
        if any(old_scope.values()):
            e["former_scope"] = old_scope
        entries.append({k: v for k, v in e.items() if v not in (None, "", [])})
    return entries


def parse_ci_branches(page: str) -> list[dict]:
    entries = []
    for t in card_tables(page):
        cur, old = _get(t, "Nazwa instytucji kredytowej")
        if not cur:
            continue
        e = {
            "name": " ".join(cur),
            "home_country": " ".join(_get(t, "Kraj pochodzenia")[0]),
            "supervisor": " ".join(_get(t, "Nazwa nadzoru macierzystego")[0]),
            "polish_branch": _get(t, "Nazwa Oddziału, adres Oddziału, telefon")[0],
            "krs": " ".join(_get(t, "Numer KRS")[0]),
            "notification_received": " ".join(_get(t, "Data wpływu notyfikacji")[0]),
            "operations_start": " ".join(_get(t, "Data rozpoczęcia działalności operacyjnej")[0]),
            "scope": _get(t, "Zakres przedmiotowy notyfikacji")[0],
            "former_names": old,
        }
        entries.append({k: v for k, v in e.items() if v not in (None, "", [])})
    return entries


def parse_ci_cross_border(page: str) -> list[dict]:
    entries = []
    for ent in next_entities(page):
        attrs = ent.get("attributes") or []
        get = lambda label, attrs=attrs: next((a.get("value") for a in attrs if a.get("name") == label), None)  # noqa: E731
        mods = []
        pending_date = None
        for a in attrs:
            if a.get("name") == "Data wpływu modyfikacji notyfikacji do nadzoru polskiego":
                pending_date = a.get("value")
            elif a.get("name") == "Zakres przedmiotowy notyfikacji po modyfikacji":
                mods.append({"date": pending_date, "scope": a.get("value")})
        raw_name = get("Nazwa instytucji kredytowej") or ent.get("name") or ""
        remark = " ".join(_lines(" ".join(re.findall(r"<small>(.*?)</small>", raw_name, flags=re.S))))
        name, _, ceased = re.sub(r"<small>.*?</small>", "", raw_name, flags=re.S).partition("→")
        name = " ".join(_lines(name))
        scope = get("Zakres przedmiotowy notyfikacji") or ""
        latest_scope = mods[-1]["scope"] if mods else scope
        entries.append({
            "name": name,
            "home_country": get("Kraj pochodzenia"),
            "supervisor": get("Nazwa nadzoru macierzystego"),
            "notification_received": get("Data wpływu notyfikacji do nadzoru polskiego"),
            "scope": scope,
            "scope_modifications": mods,
            # MiFID (2004/39/WE, 2014/65/UE) in scope = the bank may provide investment services in Poland
            "mifid_services": bool(re.search(r"2014/65|2004/39", latest_scope or "")),
            "remark": " ".join(x for x in (remark, ceased.strip()) if x) or None,
        })
    return entries


def parse_revoked(page: str) -> list[dict]:
    body = re.sub(r"<script.*?</script>", "", page, flags=re.S)
    text = "\n".join(_lines(body))
    start = text.find("Data aktualizacji")
    end = text.find("Urząd Komisji Nadzoru Finansowego", start)
    chunk = text[start:end] if start >= 0 else ""
    entries: list[dict] = []
    for line in chunk.split("\n"):
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            entries.append({"name": m.group(2).strip(), "description": ""})
        elif entries:
            entries[-1]["description"] = (entries[-1]["description"] + " " + line).strip()
    upd = re.search(r"Data aktualizacji:\s*\n?(.+)", text)
    for e in entries:
        e["page_updated"] = upd.group(1).strip() if upd else None
    return entries


_SHORT_NAME_SPLIT = re.compile(
    r"\s+(?:z\s+siedzibą|prowadząc\w*|działając\w*|działalność|administrator\w*|w związku|oferując\w*|"
    r"posługując\w*|pod nazwą|będąc\w*|zarejestrowan\w*|wykonując\w*|za pośrednictwem|poprzez|przy użyciu|"
    r"oraz|with its|registered|ul\.)(?!\w)|,|;|\s+\(|\s+[–-]\s+",
    re.IGNORECASE,
)


def _short_name(full: str) -> str:
    s = re.sub(r"^\d+\.\s*", "", full).strip()
    s = re.sub(r"[„”“\"]", "", s)
    s = _SHORT_NAME_SPLIT.split(s, maxsplit=1)[0]
    return s.strip(" „”\"'.;:")


def _split_numbered(lines: list[str]) -> list[str]:
    """'1. A', '2. B' -> ['A', 'B']; unnumbered multi-line cell -> one joined item."""
    if lines and all(re.match(r"^\d+\.\s", ln) for ln in lines):
        return [re.sub(r"^\d+\.\s*", "", ln) for ln in lines]
    return [" ".join(lines)] if lines else []


def parse_knf_warnings(page: str, sections: list[str] | None = None) -> list[dict]:
    """Rows of the KNF public warning list. `sections`: substrings of the section titles to keep."""
    body = re.sub(r"<script.*?</script>", "", page, flags=re.S)
    entries = []
    for m in re.finditer(r"<table.*?</table>", body, flags=re.S):
        before = body[max(0, m.start() - 4000): m.start()]
        heads = [" ".join(_lines(h)) for h in re.findall(r"<(?:h[1-6]|button|p)[^>]*>(.*?)</(?:h[1-6]|button|p)>", before, flags=re.S)]
        section = next((h for h in reversed(heads) if h.startswith(("Zawiadomienia", "Postępowania")) or "art." in h), "")
        if sections and not any(fold(s) in fold(section) for s in sections):
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), flags=re.S):
            tds = [_lines(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            if len(tds) < 3:
                continue
            lp = " ".join(tds[0]).rstrip(".").strip()
            names = _split_numbered(tds[1])
            ids = _split_numbered(tds[2]) if len(tds) > 2 else []
            for i, full in enumerate(names):
                short = _short_name(full)
                if not short:
                    continue
                entries.append({
                    "name": short,
                    "full_name": full,
                    "identifier": ids[i] if len(ids) == len(names) else " ".join(tds[2]),
                    "prosecutor": " ".join(tds[3]) if len(tds) > 3 else None,
                    "final_rulings": " ".join(tds[4]) if len(tds) > 4 else None,
                    "info": " ".join(tds[5]) if len(tds) > 5 else None,
                    "section": section,
                    "lp": lp,
                })
    return entries


# ---------------------------------------------------------------- fetching

@dataclass
class FetchedList:
    registry_list: RegistryList
    source_url: str
    entries: list[dict]


def parse_agents_legal(page: str) -> list[dict]:
    """Agents of investment firms - legal persons: name, the firm they act for, registration date."""
    entries = []
    for t in card_tables(page):
        cur, _ = _get(t, "Nazwa")
        if not cur:
            continue
        entries.append({
            "name": cur[0],
            "investment_firm": " ".join(_get(t, "Nazwa firmy inwestycyjnej na rzecz której działa agent")[0]),
            "address": " ".join(_get(t, "Dane Teleadresowe")[0]),
            "registered_on": _iso(" ".join(_get(t, "Data wpisu do rejestru agentów firm inwestycyjnych")[0])),
        })
    return entries


def parse_agents_natural(page: str) -> list[dict]:
    """Agents of investment firms - natural persons. Only what identifies the agent and its firm is kept
    (name as listed "Surname Name", firm, date); licence numbers and contact data are not stored."""
    entries = []
    for t in card_tables(page):
        cur, _ = _get(t, "Imię i nazwisko agenta firmy inwestycyjnej")
        if not cur:
            continue
        entries.append({
            "name": cur[0],
            "investment_firm": " ".join(_get(t, "Nazwa firmy inwestycyjnej")[0]),
            "registered_on": _iso(" ".join(_get(t, "Data uzyskania wpisu do rejestru")[0])),
        })
    return entries


def _fetch(http: HttpClient, url: str) -> str:
    resp = http.get(url)
    resp.raise_for_status()
    return resp.text


def _paged(http: HttpClient, url: str, parse: Callable[[str], list[dict]], max_pages: int = 20) -> list[dict]:
    """Follow ?page=N while pages bring new names."""
    out, names = [], set()
    for n in range(1, max_pages + 1):
        entries = parse(_fetch(http, url if n == 1 else f"{url}?page={n}"))
        new = [e for e in entries if e["name"] not in names]
        if not new:
            break
        out += new
        names.update(e["name"] for e in new)
    return out


def fetch_foreign_no_branch(http: HttpClient) -> list[dict]:
    url = URLS[RegistryList.FOREIGN_NO_BRANCH]
    base = _fetch(http, url)  # unfiltered page shows only the first 20; every letter filter shows all its firms
    letters = sorted({unquote(htmllib.unescape(m)) for m in re.findall(r'firstLetter=([^"&]+)"', base)})
    out: dict[tuple[str, str], dict] = {}
    for letter in letters:
        if not letter.strip():
            continue
        page = _fetch(http, f"{url}?firstLetter={letter}")
        for e in parse_foreign_no_branch(page, letter):
            out.setdefault((e["name"].lower(), e.get("registered_address", "")), e)
    log.info("knf_letters_fetched", letters=len(letters), entries=len(out))
    return sorted(out.values(), key=lambda e: e["name"].casefold())


def fetch_list(http: HttpClient, lst: RegistryList, warning_sections: list[str]) -> FetchedList:
    url = URLS[lst]
    match lst:
        case RegistryList.BROKERAGE_BANKS:
            entries = parse_domestic(_fetch(http, url))
        case RegistryList.BROKERAGE_FIRMS:
            entries = _paged(http, url, parse_domestic)
        case RegistryList.FOREIGN_BRANCHES:
            entries = _paged(http, url, parse_foreign_branches)
        case RegistryList.FOREIGN_NO_BRANCH:
            entries = fetch_foreign_no_branch(http)
        case RegistryList.CREDIT_INSTITUTIONS_BRANCHES:
            entries = _paged(http, url, parse_ci_branches)
        case RegistryList.CREDIT_INSTITUTIONS_CROSS_BORDER:
            entries = parse_ci_cross_border(_fetch(http, url))
        case RegistryList.REVOKED_LICENCES:
            entries = parse_revoked(_fetch(http, url))
        case RegistryList.KNF_PUBLIC_WARNINGS:
            entries = parse_knf_warnings(_fetch(http, url), warning_sections)
        case RegistryList.AGENTS_LEGAL:
            entries = _paged(http, url, parse_agents_legal, max_pages=100)
        case RegistryList.AGENTS_NATURAL:
            entries = _paged(http, url, parse_agents_natural, max_pages=300)
        case _:
            raise ValueError(lst)
    return FetchedList(lst, url, entries)
