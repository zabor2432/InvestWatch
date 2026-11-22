"""Who published a result: a registered investment firm, or someone else.

Module 1 (registry_ads) wants ads posted by third parties and module 3 (shadow_advisory) wants advisers that are
not authorised investment firms, so both drop content published by registered investment firms themselves
(that content is module 2's).

"Investment firm" as defined in the task attachments (Tematy 1-2): brokerage house, bank conducting brokerage
activity, foreign investment firm conducting brokerage activity in Poland (branch or cross-border) - which includes
a foreign credit institution providing investment services. Hence (see is_investment_firm):
  brokerage_banks, brokerage_firms, foreign_investment_firms, foreign_investment_firms_without_branches: all;
  credit_institutions_cross_border: only `mifid_services` and no remark (remarks = ceased activity / Brexit);
  credit_institutions_branches: only when the listed scope covers investment services (MiFID 2004/39 or 2014/65,
  "sekcja A"); the definition counts a foreign credit institution only if it conducts brokerage activity.
Not registered: revoked licences and warned entities (module 3 targets), and every firm no longer listed.

Agents of investment firms (KNF registers of agents, legal and natural persons) act on behalf of an authorised
firm: module 3 drops them too (they are not unauthorised advisers). Module 1 keeps them - an agent advertising
the firm it works for is a third party, exactly what module 1 looks for.
Domains: the registry (few), brand_aliases.json / m2_sources.yaml, config/firm_domains.json (found by search,
python -m app.registry.domains).
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from sqlalchemy import select

from investwatch_common.db import session_scope
from investwatch_common.enums import FirmKind, Platform, RegistryList
from investwatch_common.models import Firm
from investwatch_common.text import normalize_name

from app.models import RawPost
from app.queries import _channel_core, registered_brands
from app.settings import settings

MIN_NAME_CHARS = 4
ALL_LISTED = {RegistryList.BROKERAGE_BANKS, RegistryList.BROKERAGE_FIRMS, RegistryList.FOREIGN_BRANCHES,
              RegistryList.FOREIGN_NO_BRANCH}
MIFID_SCOPE = re.compile(r"2004/39|2014/65|MiFID|sekcj\w* A", re.IGNORECASE)


def is_investment_firm(registry_list: str, kind: str, details: dict) -> bool:
    if kind != FirmKind.AUTHORIZED:
        return False
    if registry_list in ALL_LISTED:
        return True
    if registry_list == RegistryList.CREDIT_INSTITUTIONS_CROSS_BORDER:
        return bool(details.get("mifid_services")) and not details.get("remark")
    if registry_list == RegistryList.CREDIT_INSTITUTIONS_BRANCHES:
        return bool(MIFID_SCOPE.search(json.dumps(details.get("scope"), ensure_ascii=False)))
    return False


def _found_domains() -> dict[tuple[str, str], list[str]]:
    path = settings().config_dir / "firm_domains.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {(f["registry_list"], f["name"]): f["domains"] for f in data.get("firms", []) if f.get("domains")}


@dataclass(frozen=True)
class Registry:
    domains: frozenset[str]  # own domains of registered firms
    names: frozenset[str]  # normalised names of registered firms (exact match only)
    agent_domains: frozenset[str] = frozenset()
    agent_names: frozenset[str] = frozenset()  # agents: legal names + natural persons in both word orders


def _norm_host(host: str) -> str:
    return host.lower().split(":")[0].removeprefix("www.")


@lru_cache
def registry() -> Registry:
    domains: set[str] = set()
    names: set[str] = set()
    agent_domains: set[str] = set()
    agent_names: set[str] = set()
    found = _found_domains()
    with session_scope() as db:
        for lst, name, name_norm, firm_domains, kind, details in db.execute(
            select(Firm.registry_list, Firm.name, Firm.name_norm, Firm.domains, Firm.kind, Firm.details)
            .where(Firm.removed_at.is_(None))
        ):
            own = [_norm_host(d) for d in [*(firm_domains or []), *found.get((lst, name), [])]]
            if kind == FirmKind.AGENT:
                agent_domains.update(own)
                agent_names.add(name_norm)
                if lst == RegistryList.AGENTS_NATURAL:  # listed "Surname Name"; channels use "Name Surname"
                    agent_names.add(" ".join(reversed(name_norm.split())))
            elif is_investment_firm(lst, kind, details or {}):
                names.add(name_norm)
                domains.update(own)
    for brand in registered_brands():
        domains.update(brand.domains)
        names.update(normalize_name(a) for a in brand.aliases)
    # exact-name matching only for names of 4+ characters: "tom", "man", "dm" would hit unrelated channels;
    # short brands (XTB, IG, XM) are still recognised by M2Brand.owns_channel via their aliases
    names = {n for n in names if len(n) >= MIN_NAME_CHARS}
    return Registry(frozenset(domains), frozenset(names), frozenset(agent_domains),
                    frozenset(n for n in agent_names if len(n) >= MIN_NAME_CHARS))


def _domain_in(host: str, reg: frozenset[str]) -> str | None:
    parts = _norm_host(host).split(".")
    for i in range(len(parts) - 1):
        if ".".join(parts[i:]) in reg:
            return ".".join(parts[i:])
    return None


def registered_domain(host: str, agents: bool = False) -> str | None:
    """The registered domain `host` belongs to (subdomains included), else None. `agents`: also agents' domains."""
    r = registry()
    return _domain_in(host, r.domains) or (_domain_in(host, r.agent_domains) if agents else None)


def is_registered_name(name: str | None, agents: bool = False) -> bool:
    if not name:
        return False
    n, r = normalize_name(name), registry()
    return n in r.names or (agents and n in r.agent_names)


def published_by_registered_firm(raw: RawPost, agents: bool = False) -> bool:
    """Web: page on a registered firm's domain. Channels (YouTube, Telegram, ...): channel named after a
    registered firm ("XTB Polska") - a channel that only mentions a firm is kept. `agents` (module 3): the same
    for registered agents of investment firms."""
    if raw.platform == Platform.WEB:
        return registered_domain(urlparse(raw.url).netloc, agents) is not None
    for name in (raw.author_display_name, raw.author_handle):
        if name and (is_registered_name(name, agents) or is_registered_name(_channel_core(name), agents)):
            return True
    return any(b.owns_channel(raw.author_display_name, raw.author_handle) for b in registered_brands())
