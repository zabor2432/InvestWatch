"""IOSCO I-SCAN: investor alerts of securities regulators (https://www.iosco.org/i-scan/).

Public HTML listing, filterable by regulator (NCA_ID) and validation date; 50 rows per page.
"""

import html as htmllib
import re
from datetime import date, timedelta

from app.http import HttpClient
from app.log import log

URL = "https://www.iosco.org/i-scan/"
MAX_PAGES = 100


def _txt(fragment: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", htmllib.unescape(s)).strip()


def parse_page(page: str) -> list[dict]:
    i = page.find("<tbody")
    if i < 0:
        return []
    body = page[i: page.find("</tbody>", i)]
    entries = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, flags=re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        if len(tds) < 5:
            continue
        full_name = _txt(tds[0])
        # e.g. "TRDnavigator; https://www.trdnavigator.com/", "X S.A. currently: Y S.A."
        name = re.split(r";|,|\s+currently:|\s+formerly|\s+with its|\s+\(|https?://", full_name, maxsplit=1)[0].strip(" ,.")
        name = re.sub(r"^an? identified (?:person|entity)[^:]*:\s*", "", name, flags=re.I) or full_name
        other = [x.strip() for x in _txt(tds[1]).split("\n") if x.strip()]
        websites = [x.strip() for x in re.split(r"[\s,;]+", _txt(tds[2])) if x.strip()]
        reg_link = re.search(r'href="([^"]+)"', tds[3])
        iscan_id = re.search(r"\?id=(\d+)", tr)
        entries.append({
            "name": name,
            "full_name": full_name,
            "other_names": other,
            "websites": websites,
            "regulator": _txt(tds[3]),
            "regulator_url": htmllib.unescape(reg_link.group(1)) if reg_link else None,
            "validation_date": _txt(tds[4]),
            "iscan_id": iscan_id.group(1) if iscan_id else None,
        })
    return entries


def fetch(http: HttpClient, nca_ids: list[str], months: int) -> list[dict]:
    start = (date.today() - timedelta(days=round(months * 30.44))).isoformat()
    out: dict[str, dict] = {}
    for nca in nca_ids:
        for page_no in range(1, MAX_PAGES + 1):
            resp = http.get(URL, params={"SUBSECTION": "main", "NCA_ID": nca, "ValidationDateStart": start, "page": page_no})
            resp.raise_for_status()
            rows = parse_page(resp.text)
            new = [r for r in rows if (r["iscan_id"] or r["name"]) not in out]
            for r in new:
                out[r["iscan_id"] or r["name"]] = r
            if not new or f"page={page_no + 1}" not in htmllib.unescape(resp.text):
                break
        log.info("iscan_fetched", nca_id=nca, total=len(out))
    return list(out.values())
