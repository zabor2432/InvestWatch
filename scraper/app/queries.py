"""Query lists for the scraping tasks, built from the config files and the registry.

A job runs at most MAX_QUERIES_PER_RUN queries; a rotating offset (in Redis, per task+source)
makes consecutive runs cover the rest of the list.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

import yaml
from redis import Redis
from sqlalchemy import select

from investwatch_common.db import session_scope
from investwatch_common.enums import FirmKind, RegistryList, Task
from investwatch_common.models import Firm
from investwatch_common.text import fold

from app.settings import settings

# order of entity lists in shadow_advisory: revoked licences first, then the KNF list, then I-SCAN
ENTITY_ORDER = [RegistryList.REVOKED_LICENCES, RegistryList.KNF_PUBLIC_WARNINGS, RegistryList.ISCAN_WARNINGS]


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for q in items:
        key = " ".join(q.casefold().split())
        if key and key not in seen:
            seen.add(key)
            out.append(" ".join(q.split()))
    return out


@lru_cache
def brand_aliases() -> list[dict]:
    data = json.loads((settings().config_dir / "brand_aliases.json").read_text())
    return [b for b in data["brands"] if b.get("query", True)]


def registry_ads_queries() -> list[str]:
    templates = yaml.safe_load((settings().config_dir / "ad_phrases.yaml").read_text())["templates"]
    out = []
    for b in brand_aliases():
        for alias in b["aliases"] + b.get("manual_aliases", []):
            out += [t.format(alias=alias) for t in templates]
    return _dedupe(out)


# words a firm's own channel adds to its name ("XTB Polska", "mBank TV", "IG Official")
CHANNEL_SUFFIXES = {"polska", "poland", "pl", "official", "oficjalny", "oficjalnie", "tv", "online", "channel",
                    "kanal", "group", "grupa", "sa", "s.a.", "markets", "trading", "invest", "inwestycje", "eu", "europe"}


def _channel_core(name: str) -> str:
    words = re.findall(r"[a-z0-9&.+/-]+", fold(name))
    while words and words[-1] in CHANNEL_SUFFIXES:
        words.pop()
    return " ".join(words)


@dataclass(frozen=True)
class M2Brand:
    """A KNF-listed firm: its own domains and the aliases its own channel may be named after."""

    name: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...]

    def owns_host(self, host: str) -> bool:
        host = host.lower().removeprefix("www.")
        return any(host == d or host.endswith("." + d) for d in self.domains)

    def owns_channel(self, *names: str | None) -> bool:
        """Channel named after the firm: the alias itself, optionally + a suffix ("XTB Polska"), not a channel
        that merely mentions it ("Inwestuję z XTB")."""
        cores = {_channel_core(n) for n in names if n}
        return any(fold(a) in cores for a in self.aliases)


@lru_cache
def _m2_config() -> dict:
    return yaml.safe_load((settings().config_dir / "m2_sources.yaml").read_text())


@lru_cache
def registered_brands() -> list[M2Brand]:
    """Every brand of brand_aliases.json with its own domains (brand_aliases + m2_sources.yaml + landing pages)."""
    sites = _m2_config().get("sites") or {}
    out = []
    for b in brand_aliases():
        site = sites.get(b["brand"]) or {}
        pages = site.get("pages") or []
        domains = [*(site.get("domains") or []), *b.get("domains", []),
                   *(urlparse(p).netloc.lower().removeprefix("www.") for p in pages)]
        out.append(M2Brand(b["brand"], tuple(dict.fromkeys(domains)), tuple(b["aliases"] + b.get("manual_aliases", []))))
    return out


def _other_registered_firms(covered: set[str]) -> list[M2Brand]:
    """Registered investment firms outside brand_aliases.json that have a known domain (registry or
    config/firm_domains.json), as owners for module 2."""
    from app.owners import _found_domains, is_investment_firm  # owners imports this module

    found = _found_domains()
    with session_scope() as db:
        rows = db.execute(
            select(Firm.registry_list, Firm.name, Firm.domains, Firm.kind, Firm.details)
            .where(Firm.removed_at.is_(None)).order_by(Firm.registry_list, Firm.name)
        ).all()
    out = []
    for lst, name, domains, kind, details in rows:
        if not is_investment_firm(lst, kind, details or {}):
            continue
        own = [d.lower().removeprefix("www.") for d in [*(domains or []), *found.get((lst, name), [])]]
        own = [d for d in dict.fromkeys(own) if d not in covered]
        if own:
            covered.update(own)
            out.append(M2Brand(name, tuple(own), (name,)))
    return out


def _first_alias(firm: M2Brand) -> str:
    return firm.aliases[0] if firm.aliases else firm.name


@lru_cache
def m2_queries(source: str) -> dict[str, M2Brand]:
    """firm_marketing queries for `source` (ordered) mapped to the brand that must own the result."""
    cfg = _m2_config()
    sites = cfg.get("sites") or {}
    out: dict[str, M2Brand] = {}
    brands = [(firm, (sites.get(firm.name) or {}).get("pages") or [], _first_alias(firm)) for firm in registered_brands()]
    if source == "web":
        for brand, pages, _ in brands:
            for page in pages:
                out.setdefault(page, brand)
        for phrase in cfg.get("site_phrases") or []:  # phrase-major: a rotation window covers many brands
            for brand, _, _ in brands:
                if brand.domains:
                    out.setdefault(f"site:{brand.domains[0]} {phrase}", brand)
        # the rest of the registered investment firms (mostly cross-border): one query per firm, last in the
        # rotation; the language filter keeps only their Polish pages
        covered = {d for brand, _, _ in brands for d in brand.domains}
        for firm in _other_registered_firms(covered):
            for phrase in cfg.get("registry_site_phrases") or []:
                out.setdefault(f"site:{firm.domains[0]} {phrase}", firm)
    elif source == "youtube":
        for tpl in cfg.get("youtube_templates") or []:
            for brand, _, alias in brands:
                out.setdefault(" ".join(tpl.format(alias=alias).split()), brand)
    return out


def m3_phrases() -> list[str]:
    return _dedupe(yaml.safe_load((settings().config_dir / "m3_phrases.yaml").read_text())["phrases"])


def m3_entity_queries() -> list[str]:
    """Names and domains of revoked / warned entities still listed at the source."""
    with session_scope() as db:
        rows = db.execute(
            select(Firm.registry_list, Firm.name, Firm.domains)
            .where(Firm.kind.in_([FirmKind.REVOKED, FirmKind.WARNED]), Firm.removed_at.is_(None))
            .order_by(Firm.id)
        ).all()
    from app.owners import is_registered_name, registered_domain  # owners imports this module

    # a warned entity sharing a name or a domain with a registered firm (clones, impersonation) would steer
    # the search to the registered firm itself: such names / domains are not queried
    by_list: dict[str, list[str]] = {}
    for lst, name, domains in rows:
        keep = [] if is_registered_name(name) else [name]
        keep += [d for d in domains if registered_domain(d) is None]
        by_list.setdefault(lst, []).extend(keep)
    out: list[str] = []
    for lst in ENTITY_ORDER:
        out += by_list.get(lst, [])
    return _dedupe(out)


def _window(items: list[str], budget: int, key: str, redis: Redis) -> list[str]:
    if budget <= 0 or not items:
        return []
    if len(items) <= budget:
        return items
    start = int(redis.get(key) or 0) % len(items)
    redis.set(key, (start + budget) % len(items))
    return [items[(start + i) % len(items)] for i in range(budget)]


def queries_for_run(task: Task, source: str, redis: Redis) -> list[str]:
    budget = settings().max_queries_per_run
    key = f"investwatch:query_offset:{task}:{source}"
    if task == Task.REGISTRY_ADS:
        return _window(registry_ads_queries(), budget, key, redis)
    if task == Task.SHADOW_ADVISORY:
        phrases = _window(m3_phrases(), budget, key + ":phrases", redis)
        return phrases + _window(m3_entity_queries(), budget - len(phrases), key + ":entities", redis)
    if task == Task.FIRM_MARKETING:
        return _window(list(m2_queries(source)), budget, key, redis)
    raise ValueError(f"no queries for task {task}")
