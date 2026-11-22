"""Zbiera materiały z publicznych stron wg `sources.yaml` do `demo/collected/` (poza gitem), w formacie źródłowym seeda:
tekst strony oraz zrzuty komputera (1440 px) i telefonu (390 px), dla M2 także warianty zmanipulowane (manipulate.py).

    cd demo/collect && uv run playwright install chromium && uv run python collect.py [id ...]

Ponowne uruchomienie zbiera te same adresy jeszcze raz: zmieniona treść to nowa wersja dokumentu w pipeline'ie (obserwowanie)."""

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

import manipulate

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "collected"
VIEWPORTS = {
    "desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
    "mobile": {
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
}
CONSENT = re.compile(r"^(akceptuj|zgadzam|accept|allow all|przejdź do serwisu|rozumiem|ok)", re.I)
MODULES = {"third_party_ads", "self_promotion", "non_investment_companies"}


def load_sources(path: Path = HERE / "sources.yaml") -> list[dict]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in sources.yaml")
    for e in entries:
        if e["module"] not in MODULES:
            raise ValueError(f"{e['id']}: unknown module {e['module']}")
        if bad := [r for r in e.get("manipulate", []) if r not in manipulate.RECIPES]:
            raise ValueError(f"{e['id']}: unknown recipes {bad}")
    return entries


def record(
    entry: dict, external_id: str, title: str, text: str, images: list[dict], recipe: str | None
) -> dict:
    """Rekord w formacie źródłowym seeda (kontrakt v2 bez szczegółów storage)."""
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", entry["url"]).split("/")[0])
    adv = entry.get("advertiser") or {"handle": host, "name": host}
    return {
        "platform": entry.get("platform", "web"),
        "external_id": external_id,
        "module": entry["module"],
        "url": entry["url"],
        "advertiser": adv,
        "advertised_firm": entry.get("firm", ""),
        "published_at": entry.get("published_at"),
        "captured_at": datetime.now(UTC).isoformat(),
        "title": title[:200],
        "text": text,
        # wariant zmanipulowany ma znaną etykietę (celowo złamana reguła); oryginał: etykieta z manifestu (ocena autora)
        "label": True if recipe else entry.get("label"),
        "images": images,
        "manipulated": {"rules": list(manipulate.RECIPES[recipe].rules), "recipe": recipe}
        if recipe
        else None,
        "meta": {"label_basis": entry.get("basis", "")}
        if not recipe
        else {"derived_from": entry["id"]},
    }


def dismiss_consent(page) -> None:
    for b in page.get_by_role("button").all()[:40]:
        try:
            if CONSENT.match((b.inner_text(timeout=200) or "").strip()) and b.is_visible():
                b.click(timeout=1000)
                page.wait_for_timeout(500)
                return
        except Exception:  # noqa: BLE001, S112  (baner zgód bywa nietypowy; brak kliknięcia nie jest błędem)
            continue


def capture(browser, entry: dict, recipe: str | None) -> tuple[str, str, list[dict]] | None:
    """Jedna wersja strony (oryginał albo z przepisem): tytuł, tekst i obrazy obu ekranów. None, gdy przepis nie pasuje."""
    ident = entry["id"] + (f"--{recipe}" if recipe else "")
    images, title, text = [], "", ""
    for variant, opts in VIEWPORTS.items():
        ctx = browser.new_context(locale="pl-PL", **opts)
        page = ctx.new_page()
        try:
            page.goto(entry["url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            dismiss_consent(page)
            changed = 0
            if recipe and (variant == "mobile" or not manipulate.RECIPES[recipe].mobile_only):
                changed = page.evaluate(manipulate.script(recipe))
                if not changed and variant == "desktop":
                    return None
            if (
                recipe
                and manipulate.RECIPES[recipe].mobile_only
                and variant == "mobile"
                and not changed
            ):
                return None
            page.evaluate(manipulate.MARK_RISK)
            if variant == "desktop":
                title, text = page.title(), re.sub(r"\s+", " ", page.inner_text("body")).strip()
            (OUT / "images").mkdir(parents=True, exist_ok=True)
            shot = f"{ident}-{variant}-page.png"
            page.screenshot(path=OUT / "images" / shot)
            images.append({"file": shot, "variant": variant, "focus": "page"})
            risk = page.locator("[data-iw-risk]")
            if risk.count() and risk.first.is_visible():
                risk.first.scroll_into_view_if_needed()
                crop = f"{ident}-{variant}-risk.png"
                risk.first.screenshot(path=OUT / "images" / crop)
                images.append({"file": crop, "variant": variant, "focus": "risk"})
        finally:
            ctx.close()
    return title, text, images


def main(only: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    entries = [e for e in load_sources() if not only or e["id"] in only]
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for e in entries:
            for recipe in [None, *e.get("manipulate", [])]:
                ident = e["id"] + (f"--{recipe}" if recipe else "")
                try:
                    got = capture(browser, e, recipe)
                except Exception as err:  # noqa: BLE001  (strona niedostępna: pomijamy, reszta się zbiera)
                    print(f"SKIP {ident}: {str(err)[:90]}")
                    break
                if got is None:
                    print(f"skip {ident}: przepis nie pasuje do strony")
                    continue
                records.append(record(e, ident, *got, recipe))
                print(f"ok   {ident} ({len(got[2])} obrazów)")
                time.sleep(1.5)
        browser.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"zapisano {len(records)} rekordów w {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
