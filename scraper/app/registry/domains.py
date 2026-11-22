"""Find the websites of registered investment firms and of agents that are legal persons (the KNF registry
has none) - one-off enrichment.

    docker compose exec scraper python -m app.registry.domains --out /tmp/firm_domains.json
    docker compose cp scraper:/tmp/firm_domains.json scraper/config/firm_domains.json

Searches every registered firm without a known domain through the local SearXNG (Google engine first - no API key,
no paid service; Bing / DuckDuckGo when Google refuses) and keeps a result host only when its domain label contains a
distinctive word of the firm's name ("ipopemasecurities.pl" for IPOPEMA SECURITIES S.A.). Aggregators, regulators and
review sites are skipped. Firms without a confident match get no domain (never guessed).
"""

import argparse
import json
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from investwatch_common.db import session_scope
from investwatch_common.enums import RegistryList
from investwatch_common.models import Firm
from investwatch_common.text import normalize_name

from app.log import configure, log
from app.owners import is_investment_firm, registry
from app.settings import settings

ENGINES = ("google", "bing", "duckduckgo")
GENERIC = {
    "bank", "banca", "banco", "banque", "bancaria", "banka", "bankas", "banken", "sparkasse", "kasse", "the", "and", "of",
    "de", "des", "du", "la", "le", "di", "del", "und", "et", "y", "investment", "investments", "investimento", "invest",
    "capital", "markets", "market", "securities", "financial", "finance", "finanz", "financiere", "services", "service",
    "europe", "european", "international", "global", "group", "groupe", "holding", "asset", "assets", "management",
    "gestion", "trading", "trade", "fund", "funds", "partners", "company", "companies", "wealth", "advisors", "advisory",
    "brokers", "broker", "brokerage", "limited", "cyprus", "luxembourg", "ireland", "malta", "germany", "deutschland",
    "france", "italia", "espana", "nederland", "austria", "sweden", "denmark", "norway", "finland", "estonia", "latvia",
    "lithuania", "polska", "poland", "branch", "oddzial", "spolka", "societe", "sociedad", "valores", "anonyme",
    "aktiengesellschaft", "public", "plc", "ltd", "gmbh", "corp", "corporation", "agency", "inc", "llc", "kft", "zrt",
    "ab", "as", "asa", "oyj", "nv", "bv", "sa", "ag", "se", "spa", "srl", "sas", "sarl", "eu", "fx", "cfd", "online",
    "dom", "maklerski", "maklerskie", "inwestycyjny", "inwestycyjne", "towarzystwo", "biuro", "zarzadzajacy",
}
SKIP_HOST = re.compile(
    r"(knf\.gov|esma\.europa|europa\.eu|\.gov\b|gov\.|cysec|fca\.org|bafin|amf-france|consob|cnmv|afm\.nl|centralbank|"
    r"mfsa|cssf|finansinspektionen|finanstilsynet|fi\.se|fin-fsa|fktk|lb\.lt|mnb\.hu|cnb\.cz|nbs\.sk|bnb\.bg|asfromania|"
    r"iosco|gleif|lei-|opencorporates|northdata|dnb\.com|bloomberg|reuters|crunchbase|zoominfo|wikipedia|wikidata|"
    r"linkedin|facebook|instagram|youtube|twitter|x\.com|tiktok|glassdoor|indeed|kompass|companieshouse|company-information|"
    r"companyhouse|creditreform|cylex|aleo|krs|rejestr|emis|pitchbook|craft\.co|dealroom|bankier|money\.pl|"
    r"forexbrokers|brokerchooser|fxempire|investing\.com|tradingview|trustpilot|reddit|myfxbook|forexpeacearmy|wikifx|"
    r"fxverify|brokersview|banks\.eu|bankrate|swift|bic|iban|thebanks|relbanks|scam|review|opinie|rating|compare)",
    re.IGNORECASE,
)


def _tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", normalize_name(name))
    return [w for w in words if len(w) >= 3 and w not in GENERIC]


def _registrable(host: str) -> str:
    host = host.lower().split(":")[0].removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in {"co", "com", "org", "net", "gov", "ac"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _label(host: str) -> str:
    """Registrable label without TLD: 'www.ipopema-securities.co.uk' -> 'ipopemasecurities'."""
    return re.sub(r"[^a-z0-9]", "", _registrable(host).split(".")[0])


def _acronym(name: str) -> str:
    return "".join(w[0] for w in re.findall(r"[a-z0-9]+", normalize_name(name)) if w not in {"of", "the", "and", "de"})


def match(name: str, host: str) -> bool:
    """Domain label made of the firm's own words: at least two distinctive words of the name (or its leading one),
    or the name's acronym; whatever is left of the label may only be generic words ("bank", "group").
    'bankofchina' ok for Bank of China, 'nationalcar' / 'credit-agricole' / 'smbc-comics' rejected."""
    if SKIP_HOST.search(host):
        return False
    label = _label(host)
    toks = _tokens(name)
    if not toks or len(label) < 3:
        return False
    acr = _acronym(name)
    if any(label in (acr[:k], acr[:k] + "bank", acr[:k] + "group") for k in range(3, len(acr) + 1)):
        return True
    matched = [t for t in sorted(toks, key=len, reverse=True) if t in label]
    # one word is enough only when it is the name's leading distinctive word ("f-trust" for F-TRUST IWEALTH)
    if len(matched) < min(2, len(toks)) and not (matched == [toks[0]] and len(toks[0]) >= 4 and len(toks) <= 2):
        return False
    rest = label
    for w in matched + sorted(GENERIC | set(re.findall(r"[a-z0-9]+", normalize_name(name))), key=len, reverse=True):
        rest = rest.replace(w, "")
    return len(rest) <= 2


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml", "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def _name_words(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_name(name))


def strong_label(name: str, domain: str) -> bool:
    """Label is exactly several words of the name ('goldmansachs', 'bankofchina') or its acronym of 4+ letters
    ('pkobp'). A single-word label ('wise', 'today', 'swiss') is never strong: everyday words."""
    label, toks, acr = _label(domain), _tokens(name), _acronym(name)
    words = [w for w in _name_words(name) if w not in {"the"}]
    multi = {"".join(toks)} if len(toks) >= 2 else set()
    multi |= {"".join(words[:k]) for k in range(2, len(words) + 1)}
    return label in multi or (len(label) >= 4 and any(label == acr[:k] for k in range(4, len(acr) + 1)))


def _phrases(name: str) -> list[str]:
    """What the home page must contain: every distinctive word; a one-word name ("SKY Asset Management") needs
    that word next to a neighbour of the name ("sky asset") - "sky", "luna", "atlantic" alone are everyday words."""
    toks, words = _tokens(name), _name_words(name)
    if len(toks) != 1:
        return toks
    i = words.index(toks[0]) if toks[0] in words else -1
    if i < 0 or len(words) == 1:
        return toks
    return [" ".join(words[i:i + 2]) if i + 1 < len(words) else " ".join(words[i - 1:i + 1])]


def _page_text(client: httpx.Client, domain: str) -> str | None:
    """Folded text of the home page, None when it cannot be read (refused, JS-only, not HTML)."""
    try:
        r = client.get(f"https://{domain}/", headers=BROWSER_HEADERS, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        return None
    from selectolax.lexbor import LexborHTMLParser

    tree = LexborHTMLParser(r.text)
    title = tree.css_first("title")
    raw = (title.text() if title else "") + " " + (tree.body.text(separator=" ") if tree.body else "")
    text = " ".join(re.findall(r"[a-z0-9]+", normalize_name(raw)))
    return text if len(text) >= 200 else None


def verify(client: httpx.Client, name: str, domain: str) -> bool:
    text = _page_text(client, domain)
    if text is None:  # unreadable page: trust only an exact name / acronym label
        return strong_label(name, domain)
    return all(f" {p} " in f" {text} " for p in _phrases(name))


def search(client: httpx.Client, q: str) -> tuple[list[str], str | None]:
    for engine in ENGINES:
        try:
            r = client.get(f"{settings().searxng_url}/search", params={"q": q, "format": "json", "engines": engine})
            results = r.json().get("results", []) if r.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            results = []
        if results:
            return [x["url"] for x in results[:10]], engine
        time.sleep(1)
    return [], None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0, help="max firms to search (0 = all)")
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--lists", default="", help="comma-separated registry lists to search (default: all in scope)")
    p.add_argument("--refilter", default="", help="re-apply the matching rule to the candidates of an earlier output")
    p.add_argument("--merge", nargs="*", default=[], help="earlier outputs to merge into --out (later wins)")
    p.add_argument("--verify", action="store_true", help="with --refilter/--merge: keep only domains whose home page "
                                                         "names the firm (fetched live)")
    args = p.parse_args()
    configure(settings().log_level)
    if args.refilter or args.merge:
        firms_out: dict[tuple[str, str], dict] = {}
        for path in [args.refilter, *args.merge] if args.refilter else args.merge:
            for f in json.load(open(path))["firms"]:
                f["domains"] = list(dict.fromkeys(_registrable(h) for h in f["candidates"] if h and match(f["name"], h)))[:3]
                firms_out[(f["registry_list"], f["name"])] = f
        out = list(firms_out.values())
        if args.verify:
            from concurrent.futures import ThreadPoolExecutor

            with httpx.Client(timeout=15) as client, ThreadPoolExecutor(8) as pool:
                for f in out:
                    if f["domains"]:
                        ok = list(pool.map(lambda d, n=f["name"]: verify(client, n, d), f["domains"]))
                        f["unverified"] = [d for d, k in zip(f["domains"], ok, strict=True) if not k]
                        f["domains"] = [d for d, k in zip(f["domains"], ok, strict=True) if k]
        _write(args.out, out, sum(bool(f["domains"]) for f in out))
        return
    known = registry().domains
    with session_scope() as db:
        firms = [
            (f.registry_list, f.name, f.country, f.details or {})
            for f in db.scalars(select(Firm).where(Firm.removed_at.is_(None)).order_by(Firm.id))
            if (is_investment_firm(f.registry_list, f.kind, f.details or {})
                or f.registry_list == RegistryList.AGENTS_LEGAL) and not f.domains
        ]
    if args.lists:
        wanted = set(args.lists.split(","))
        firms = [f for f in firms if f[0] in wanted]
    out, found = [], 0
    todo = firms[: args.limit] if args.limit else firms
    with httpx.Client(timeout=40) as client:
        for i, (lst, name, country, _details) in enumerate(todo, 1):
            q = f"{name} {country or ''}".strip()
            urls, engine = search(client, q)
            domains: list[str] = []
            for u in urls:
                host = urlparse(u).netloc
                reg = _registrable(host)
                if host and match(name, host) and reg not in domains:
                    domains.append(reg)
            domains = domains[:3]
            found += bool(domains)
            out.append({"registry_list": lst, "name": name, "domains": domains, "engine": engine, "query": q,
                        "candidates": [urlparse(u).netloc for u in urls]})
            log.info("firm_domain", progress=f"{i}/{len(todo)}", name=name, domains=domains, engine=engine,
                     already_known=[d for d in domains if d in known])
            if i % 25 == 0 or i == len(todo):
                _write(args.out, out, found)
            time.sleep(args.delay)
    _write(args.out, out, found)


def _write(path: str, out: list[dict], found: int) -> None:
    meta = {
        "description": "Websites of registered investment firms found by search (python -m app.registry.domains); "
                       "the KNF registry lists none. Used by app/owners.py to recognise the firms' own pages.",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "method": "SearXNG, engines google > bing > duckduckgo; a result host is kept only if its domain label "
                  "contains a distinctive word of the firm name; aggregators / regulators skipped; max 3 per firm",
        "searched": len(out), "with_domains": found,
    }
    with open(path, "w") as fh:
        json.dump({"meta": meta, "firms": out}, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
