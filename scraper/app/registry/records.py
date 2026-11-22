"""Map a register entry (seed file or live page) to the columns of `firms`."""

import re
from dataclasses import dataclass, field

from investwatch_common.enums import RegistryList
from investwatch_common.text import extract_domains, fold, normalize_name

TRADE_NAME_RE = re.compile(r"nazw[ay] handlow[ae]\s*[:\-–]?\s*(.+)", re.IGNORECASE)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# fields whose text may contain websites
DOMAIN_FIELDS = ("additional_info", "former_additional_info", "websites", "full_name", "info", "name", "other_names")
DATE_FIELDS = ("registered_on", "license_date", "krs_entry_date", "notification_received", "notification_history", "validation_date")


@dataclass
class FirmRecord:
    registry_list: RegistryList
    name: str
    name_norm: str
    other_names: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    country: str | None = None
    listed_at: str | None = None
    details: dict = field(default_factory=dict)
    source_url: str | None = None


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [x for x in v if isinstance(x, str)]


def to_record(lst: RegistryList, entry: dict, source_url: str | None) -> FirmRecord | None:
    name = (entry.get("name") or "").strip()
    if not name:
        return None
    other: list[str] = []
    for key in ("other_names_as_listed", "former_names", "other_names"):
        other += _as_list(entry.get(key))
    # "nazwa handlowa: Admirals, Admiral Markets" may continue on the next line
    info = _as_list(entry.get("additional_info")) + _as_list(entry.get("former_additional_info"))
    for i, line in enumerate(info):
        m = TRADE_NAME_RE.search(line)
        if m:
            value = m.group(1).strip() or (info[i + 1] if i + 1 < len(info) else "")
            other += [x.strip(" -()") for x in re.split(r",|;", value) if x.strip(" -()")]
    other = [o for o in dict.fromkeys(other) if fold(o) != fold(name) and not o.lower().startswith(("www.", "http"))]

    domains: list[str] = []
    for key in DOMAIN_FIELDS:
        for text in _as_list(entry.get(key)):
            for d in extract_domains(text):
                if d not in domains:
                    domains.append(d)

    listed_at = None
    for key in DATE_FIELDS:
        if (v := entry.get(key)) and (m := DATE_RE.search(str(v))):
            listed_at = m.group(0)
            break

    country = entry.get("home_country") or entry.get("country")
    return FirmRecord(
        registry_list=lst,
        name=name,
        name_norm=normalize_name(name) or fold(name),
        other_names=other,
        domains=domains,
        country=country,
        listed_at=listed_at,
        details=entry,
        source_url=source_url,
    )
