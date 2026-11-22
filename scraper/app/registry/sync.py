"""registry_sync: seed `firms` from docs/firm_registry when empty, then refresh every list from its source."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from investwatch_common.db import session_scope
from investwatch_common.enums import FIRM_KIND_BY_LIST, RegistryList
from investwatch_common.models import Firm

from app.http import HttpClient
from app.log import log
from app.registry import iscan, knf
from app.registry.records import FirmRecord, to_record
from app.settings import settings

ISCAN_URL = iscan.URL


def upsert_records(db: Session, records: list[FirmRecord], mark_removed: bool) -> dict:
    """Upsert one list. With mark_removed, rows of that list missing from `records` get removed_at."""
    if not records:
        return {"upserted": 0, "removed": 0}
    lst = records[0].registry_list
    now = datetime.now(UTC)
    existing = {f.name_norm: f for f in db.scalars(select(Firm).where(Firm.registry_list == lst))}
    seen: set[str] = set()
    new = 0
    for r in records:
        if r.name_norm in seen:  # same firm listed twice on one page: merge names and domains
            f = existing[r.name_norm]
            f.other_names = list(dict.fromkeys(f.other_names + r.other_names + [r.name]))
            f.domains = list(dict.fromkeys(f.domains + r.domains))
            continue
        seen.add(r.name_norm)
        f = existing.get(r.name_norm)
        if f is None:
            f = Firm(registry_list=lst, name_norm=r.name_norm, first_seen_at=now)
            db.add(f)
            existing[r.name_norm] = f
            new += 1
        f.kind = FIRM_KIND_BY_LIST[lst]
        f.name, f.other_names, f.domains = r.name, r.other_names, r.domains
        f.country, f.listed_at, f.details, f.source_url = r.country, r.listed_at, r.details, r.source_url
        f.last_seen_at, f.removed_at = now, None
    removed = 0
    if mark_removed:
        for norm, f in existing.items():
            if norm not in seen and f.removed_at is None:
                f.removed_at = now
                removed += 1
    return {"upserted": len(seen), "new": new, "removed": removed}


def seed_from_files(seed_dir: Path) -> dict:
    stats = {}
    for path in sorted(seed_dir.glob("*.json")):
        try:
            lst = RegistryList(path.stem)
        except ValueError:
            continue  # scope_codes.json and other reference files
        data = json.loads(path.read_text())
        url = (data.get("meta") or {}).get("url")
        records = [r for e in data.get("entries", []) if (r := to_record(lst, e, url))]
        with session_scope() as db:
            stats[lst.value] = upsert_records(db, records, mark_removed=False)
    log.info("registry_seeded", dir=str(seed_dir), stats=stats)
    return stats


def fetch_all(http: HttpClient) -> list[tuple[RegistryList, str, list[dict]]]:
    """Fetch every list; a failing list is logged and skipped. Returns (list, url, entries)."""
    s = settings()
    out = []
    for lst in knf.URLS:
        try:
            fl = knf.fetch_list(http, lst, s.knf_warning_sections)
            out.append((lst, fl.source_url, fl.entries))
        except Exception as exc:
            log.error("registry_fetch_failed", registry_list=lst.value, error=str(exc)[:300])
    try:
        out.append((RegistryList.ISCAN_WARNINGS, ISCAN_URL, iscan.fetch(http, s.iscan_nca_ids, s.iscan_months)))
    except Exception as exc:
        log.error("registry_fetch_failed", registry_list=RegistryList.ISCAN_WARNINGS.value, error=str(exc)[:300])
    return out


def run_registry_sync() -> dict:
    s = settings()
    stats: dict = {}
    with session_scope() as db:
        empty = db.scalar(select(func.count()).select_from(Firm)) == 0
    if empty and s.registry_seed_dir.is_dir():
        stats["seed"] = seed_from_files(s.registry_seed_dir)
    http = HttpClient()
    try:
        for lst, url, entries in fetch_all(http):
            if not entries:
                log.warning("registry_list_empty", registry_list=lst.value)  # page layout changed? keep old rows
                stats[lst.value] = {"upserted": 0, "error": "no entries parsed"}
                continue
            records = [r for e in entries if (r := to_record(lst, e, url))]
            with session_scope() as db:
                stats[lst.value] = upsert_records(db, records, mark_removed=True)
            log.info("registry_list_synced", registry_list=lst.value, **stats[lst.value])
    finally:
        http.close()
    return stats
