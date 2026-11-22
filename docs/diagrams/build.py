"""Buduje docs/architecture-diagrams.pdf: stan obecny i architektura docelowa (strefy, komponenty, podpisane przepływy).

    uv run --no-project --with playwright python docs/diagrams/build.py   # wymaga: playwright install chromium
Diagramy są tu, w kodzie (SVG), więc zmiana architektury = zmiana tego pliku i ponowne uruchomienie."""

import html
import tempfile
from pathlib import Path

W, H = 1500, 960
KINDS = {  # wypełnienie, obrys, kreskowanie
    "sys": ("#e8f0fe", "#2b5bd7", ""),
    "ext": ("#f1f3f4", "#6b7177", ""),
    "new": ("#e6f6ea", "#1e8e3e", ""),
    "opt": ("#f7f9ff", "#2b5bd7", "6 4"),
    "newopt": ("#f2fbf4", "#1e8e3e", "6 4"),
}
e = html.escape


class Svg:
    def __init__(self):
        self.parts: list[str] = []

    def zone(self, x, y, w, h, title, kind="sys"):
        color = {"sys": "#2b5bd7", "ext": "#6b7177", "new": "#1e8e3e"}[kind]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="{color}" stroke-width="1.4" stroke-dasharray="7 5" opacity=".75"/>'
            f'<text x="{x + 14}" y="{y + 22}" class="zone" fill="{color}">{e(title.upper())}</text>'
        )

    def box(self, x, y, w, h, title, lines=(), kind="sys", tag=None):
        fill, stroke, dash = KINDS[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{d}/>']
        out.append(f'<text x="{x + 12}" y="{y + 22}" class="title">{e(title)}</text>')
        for i, line in enumerate(lines):
            cls = "tech" if i == 0 and line.startswith("[") else "line"
            out.append(f'<text x="{x + 12}" y="{y + 40 + i * 15}" class="{cls}">{e(line)}</text>')
        if tag:
            tw = 8 * len(tag) + 14
            col = "#1e8e3e" if tag in ("NOWE", "ZMIANA") else "#6b7177"
            out.append(f'<rect x="{x + w - tw - 8}" y="{y - 9}" width="{tw}" height="17" rx="8" fill="{col}"/>'
                       f'<text x="{x + w - tw / 2 - 8}" y="{y + 3.5}" class="tag" text-anchor="middle">{tag}</text>')
        self.parts.append("".join(out))

    def arrow(self, pts, label="", dashed=False, lx=None, ly=None, color="#3c4043", anchor="middle"):
        d = "M" + " L".join(f"{px},{py}" for px, py in pts)
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.7"{dash} marker-end="url(#a)"/>')
        if label:
            (x1, y1), (x2, y2) = pts[0], pts[1] if len(pts) > 1 else pts[0]
            mx, my = lx if lx is not None else (x1 + pts[-1][0]) / 2, ly if ly is not None else (y1 + pts[-1][1]) / 2 - 6
            for i, line in enumerate(label.split("\n")):
                self.parts.append(f'<text x="{mx}" y="{my + i * 12}" class="lbl" text-anchor="{anchor}">{e(line)}</text>')

    def text(self, x, y, s, cls="note", anchor="start"):
        for i, line in enumerate(s.split("\n")):
            self.parts.append(f'<text x="{x}" y="{y + i * 13}" class="{cls}" text-anchor="{anchor}">{e(line)}</text>')

    def render(self, title, subtitle, legend):
        head = (f'<text x="30" y="36" class="h1">{e(title)}</text><text x="30" y="58" class="h2">{e(subtitle)}</text>')
        lg = ["".join(
            f'<rect x="{30 + i * 250}" y="{H - 34}" width="26" height="14" rx="3" fill="{KINDS[k][0]}" stroke="{KINDS[k][1]}" stroke-width="1.4"'
            f'{" stroke-dasharray=%s6 4%s" % (chr(34), chr(34)) if KINDS[k][2] else ""}/>'
            f'<text x="{62 + i * 250}" y="{H - 23}" class="lbl">{e(t)}</text>' for i, (k, t) in enumerate(legend))]
        flow = (f'<path d="M{30 + len(legend) * 250},{H - 27} L{80 + len(legend) * 250},{H - 27}" stroke="#3c4043" stroke-width="1.7" marker-end="url(#a)"/>'
                f'<text x="{90 + len(legend) * 250}" y="{H - 23}" class="lbl">przepływ danych</text>'
                f'<path d="M{230 + len(legend) * 250},{H - 27} L{280 + len(legend) * 250},{H - 27}" stroke="#3c4043" stroke-width="1.7" stroke-dasharray="6 4" marker-end="url(#a)"/>'
                f'<text x="{290 + len(legend) * 250}" y="{H - 23}" class="lbl">sterowanie, wywołanie, obserwacja</text>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
                '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#3c4043"/></marker></defs>'
                f'<rect width="{W}" height="{H}" fill="#fff"/>{head}{"".join(self.parts)}{"".join(lg)}{flow}</svg>')


def pipeline(s: Svg, notes: dict[str, tuple[str, str]], kinds: dict[str, str], tags: dict[str, str]):
    """Łańcuch assetów Dagstera (wspólny dla obu diagramów)."""
    steps = [("intake_items", "walidacja kontraktu v2"), ("documents", "obserwacje, wersje, obrazy"),
             ("analysis_batch", "co trafia do modelu"), ("transcribed_batch", "audio → tekst (Whisper)"),
             ("preprocessed_batch", "tokeny, wektory, duplikaty"), ("module_splits", "podział wg modułu")]
    for i, (name, sub) in enumerate(steps):
        y = 140 + i * 70
        s.box(665, y, 235, 52, name, [sub], kinds.get(name, "sys"), tags.get(name))
        n = notes.get(name)
        if n:
            s.text(912, y + 20, "\n".join(n), "note")
        if i:
            s.arrow([(782, y - 18), (782, y)])
    return steps


def modules(s: Svg, y=600):
    for x, t, sub in ((665, "ad_scores", "M1 · reklama? 0–1"), (807, "rule_scores", "M2 · 18 reguł, 0–1"),
                      (949, "advisory_scores", "M3 · doradztwo")):
        s.box(x, y, 138, 66, t, [sub], "sys")
        s.arrow([(782, 522), (x + 69, y)])


def current() -> str:
    s = Svg()
    s.zone(30, 100, 260, 640, "Źródła danych")
    s.box(45, 135, 230, 130, "Scraper", ["[Python · RQ/Redis · Playwright]", "YouTube, Telegram, web,", "Substack, Reddit, Wykop", "po jobie: adapter landing.py"], "opt", "OPCJONALNY")
    s.box(45, 295, 230, 110, "Dane demo i testowe", ["[seed · demo/collect]", "fikcyjne rekordy, strony z netu,", "próbki scrapera (data/scraped)"], "sys")
    s.zone(340, 100, 260, 640, "Object storage · MinIO")
    s.box(355, 135, 230, 150, "bucket investwatch", ["[kontrakt danych v2]", "raw/{platforma}/{id}/{hash}.json", "images/{sha256}.png", "niezmienne, adresowane treścią"], "sys")
    s.box(355, 335, 230, 100, "bucket investwatch-media", ["[media scrapera]", "zrzuty i obrazy; adapter kopiuje", "je do investwatch"], "ext")
    s.zone(650, 100, 450, 640, "Orkiestracja · Dagster (start ręczny)")
    steps = pipeline(s, {
        "intake_items": ("niepoprawne obiekty →", "kwarantanna"), "documents": ("ledger ingestii,", "historia wersji"),
        "analysis_batch": ("nowe + zmienione; po zmianie", "modelu: okno wstecz (30 dni)"),
        "transcribed_batch": ("domyślnie pominięty", "(brak danych audio)"), "preprocessed_batch": ("duplikat tekstu dostaje", "wynik oryginału"),
        "module_splits": ("M1 / M2 / M3", "")}, {"transcribed_batch": "opt"}, {"transcribed_batch": "POMIJANY"})
    modules(s)
    s.zone(1160, 100, 310, 290, "Aplikacja webowa")
    s.box(1175, 130, 280, 112, "Frontend", ["[React 18 · TypeScript · Tailwind]", "Wyniki, Przegląd, Raport, Kalibracja", "progi per reguła, tryb ślepy,", "przycisk „Odśwież dane”"], "sys")
    s.box(1175, 272, 280, 105, "Backend", ["[FastAPI · REST · WebSocket]", "rekordy, oceny, raport, obrazy", "/ws/alerts, /api/refresh"], "sys")
    s.zone(1160, 430, 310, 150, "Dane")
    s.box(1175, 460, 280, 112, "PostgreSQL", ["[tabele]", "observations, documents, results,", "ingestions, annotations,", "model_calls (+ baza Dagstera)"], "sys")
    s.zone(1160, 600, 310, 140, "Model decyzyjny (zewnętrzny)", "ext")
    s.box(1175, 630, 280, 92, "OpenJev (hostowany, Codiv)", ["[POST /v1/systemone]", "pytania tak/nie → prawdopodobieństwo", "0–1, tekst i obrazy"], "ext")
    # przepływy
    s.arrow([(275, 175), (355, 175)], "kontrakt v2\nbez duplikatów", lx=315, ly=158)
    s.arrow([(275, 350), (315, 350), (315, 250), (355, 250)], "", False)
    s.text(322, 330, "kontrakt v2", "lbl")
    s.arrow([(585, 210), (625, 210), (625, 166), (665, 166)], "")
    s.text(560, 345, "", "lbl")
    s.arrow([(1100, 516), (1175, 516)], "zapis:\ndokumenty,\nwyniki", lx=1137, ly=488)
    s.arrow([(1075, 666), (1175, 676)], "pytania", lx=1125, ly=650)
    s.arrow([(1217, 242), (1217, 272)], "")
    s.text(1226, 262, "REST · WebSocket", "lbl")
    s.arrow([(1420, 377), (1420, 460)], "SELECT ·\nLISTEN\nhigh_risk", lx=1412, ly=410, anchor="end")
    s.arrow([(1175, 345), (1100, 345)], "Odśwież dane:\nGraphQL\nlaunchRun", dashed=True, lx=1137, ly=318)
    s.arrow([(1175, 295), (1130, 295), (1130, 78), (470, 78), (470, 100)], "obrazy po id rekordu", dashed=True, lx=800, ly=72)
    s.zone(30, 800, 1440, 100, "Gdzie podejrzeć (docker compose up)")
    for i, (t, l1) in enumerate((("Dashboard", "http://localhost:3000"), ("Dagster", "http://localhost:3001: runy, logi, metadane"),
                                 ("MinIO", "http://localhost:9001: bucket investwatch"), ("API backendu", "http://localhost:8000/docs, /api/model-calls"),
                                 ("PostgreSQL", "localhost:5432: documents, results, model_calls"))):
        s.box(45 + i * 286, 835, 270, 50, t, [l1], "ext")
    s.text(30, 765, "Zasady: serwisy łączy kontrakt przez dane (MinIO + Postgres); jedyne wywołanie HTTP na zewnątrz to model, zamknięty w jednym pliku (pipeline/llm.py).\n"
           "Wynik modelu to surowy score 0–1; progi (globalny i per reguła) są stosowane przy odczycie, więc zmiana progu niczego nie przelicza.", "note")
    return s.render("InvestWatch — architektura: stan obecny", "Moduły: M1 reklamy osób trzecich · M2 informacja o ryzyku w materiałach firm · M3 doradztwo bez uprawnień",
                    [("sys", "komponent systemu"), ("opt", "opcjonalny / domyślnie wyłączony"), ("ext", "zewnętrzny")])


def target() -> str:
    s = Svg()
    s.zone(30, 100, 260, 640, "Źródła danych")
    s.box(45, 135, 230, 140, "Scraper + cron", ["[Python · RQ · Playwright]", "przekazuje raw.layout i bloki", "z ryzykiem (focus: risk),", "więcej domen firm"], "new", "ZMIANA")
    s.box(45, 305, 230, 100, "Dane demo i testowe", ["[seed · demo/collect]", "bez zmian"], "sys")
    s.zone(340, 100, 260, 640, "Object storage · MinIO")
    s.box(355, 135, 230, 140, "bucket investwatch", ["[kontrakt danych v2]", "bez zmian; replikowany", "(MinIO rozproszone)"], "sys")
    s.box(355, 335, 230, 110, "Archiwum dowodów", ["[evidence/, retencja]", "trwałe dowody naruszeń,", "wygasanie surowych danych"], "new", "NOWE")
    s.zone(650, 100, 450, 640, "Orkiestracja · Dagster (wiele workerów)")
    pipeline(s, {
        "intake_items": ("adapter scrapera", "jako stałe źródło"), "documents": ("bez zmian", ""),
        "analysis_batch": ("bez zmian", ""), "transcribed_batch": ("Whisper lokalny,", "gdy pojawi się wideo"),
        "preprocessed_batch": ("embeddingi neuralne,", "dedupe semantyczny"), "module_splits": ("M1 / M2 / M3", "")},
        {"transcribed_batch": "newopt", "preprocessed_batch": "new"}, {"transcribed_batch": "WŁĄCZONY", "preprocessed_batch": "ZMIANA"})
    modules(s)
    s.zone(1160, 100, 310, 100, "Dostęp", "new")
    s.box(1175, 128, 280, 60, "Brama + logowanie", ["[reverse proxy · OIDC / LDAP · role]"], "new", "NOWE")
    s.zone(1160, 215, 310, 245, "Aplikacja webowa")
    s.box(1175, 243, 280, 92, "Frontend", ["[React]", "progi per reguła zapisane", "na serwerze, podpisane oceny"], "sys")
    s.box(1175, 352, 280, 92, "Backend (repliki)", ["[FastAPI · LISTEN w każdej replice]", "powiadomienia poza UI"], "sys")
    s.zone(1160, 475, 310, 120, "Dane")
    s.box(1175, 503, 280, 80, "PostgreSQL", ["[+ tabela progów z audytem]", "retencja, kopie"], "sys")
    s.zone(1160, 610, 310, 130, "Model decyzyjny (lokalny)", "new")
    s.box(1175, 638, 280, 88, "OpenJev na GPU", ["[vLLM · /v1/systemone · profil gpu]", "ten sam protokół, zmiana", "TYPESAFE_BASE_URL"], "new", "NOWE")
    # dolny pas
    s.zone(30, 760, 640, 125, "Obserwowalność", "new")
    s.box(45, 805, 290, 66, "Langfuse", ["[ślady wywołań modelu, koszt, jakość]"], "new", "NOWE")
    s.box(355, 805, 300, 66, "Loki + Grafana", ["[logi serwisów, metryki Dagstera]"], "new", "NOWE")
    s.zone(690, 760, 400, 125, "Serwisy AI i powiadomienia", "new")
    s.box(705, 805, 190, 66, "Serwis embeddingów", ["[model wielojęzyczny]"], "new", "NOWE")
    s.box(905, 805, 170, 66, "Alerty", ["[e-mail / komunikator]"], "new", "NOWE")
    # przepływy
    s.arrow([(275, 185), (355, 185)], "kontrakt v2", lx=315, ly=170)
    s.arrow([(275, 355), (315, 355), (315, 250), (355, 250)])
    s.arrow([(470, 285), (470, 335)], "retencja", lx=500, ly=315)
    s.arrow([(585, 210), (625, 210), (625, 166), (665, 166)])
    s.arrow([(1100, 543), (1175, 543)], "zapis", lx=1137, ly=535)
    s.arrow([(1075, 666), (1175, 676)], "pytania", lx=1125, ly=650)
    s.arrow([(1420, 188), (1420, 243)], "logowanie", lx=1412, ly=219, anchor="end")
    s.arrow([(1217, 335), (1217, 352)])
    s.arrow([(1420, 444), (1420, 503)])
    s.arrow([(1175, 410), (1100, 410)], "launchRun\n(GraphQL)", dashed=True, lx=1137, ly=392)
    s.arrow([(1175, 262), (1130, 262), (1130, 78), (470, 78), (470, 100)], "obrazy po id rekordu", dashed=True, lx=800, ly=72)
    s.arrow([(760, 740), (760, 805)], "wektory", dashed=True, lx=772, ly=754, anchor="start")
    s.arrow([(690, 740), (520, 805)], "logi, ślady, metryki", dashed=True, lx=560, ly=768)
    s.text(30, 905, "Iteracje: 1 model lokalny · 2 scraper na cronie z układem bloków · 3 progi na serwerze · 4 logowanie i role · 5 obserwowalność · 6 embeddingi i pomiary obrazowe · 7 retencja i alerty · 8 skalowanie.", "note")
    return s.render("InvestWatch — architektura docelowa", "Zielone elementy są nowe lub zmienione względem stanu obecnego; reszta bez zmian",
                    [("sys", "bez zmian"), ("new", "nowe lub zmienione"), ("newopt", "włączany, gdy będzie wideo")])


CSS = """
@page { size: %dpx %dpx; margin: 0 }
html, body { margin: 0; background: #fff }
.page { width: %dpx; height: %dpx; page-break-after: always; overflow: hidden }
svg text { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif }
.h1 { font-size: 26px; font-weight: 700; fill: #202124 } .h2 { font-size: 13.5px; fill: #5f6368 }
.zone { font-size: 11.5px; font-weight: 700; letter-spacing: .08em }
.title { font-size: 14px; font-weight: 700; fill: #202124 } .tech { font-size: 10.5px; fill: #1a4bb8; font-style: italic }
.line { font-size: 11px; fill: #3c4043 } .tag { font-size: 9px; font-weight: 700; fill: #fff }
.lbl { font-size: 10.5px; fill: #3c4043; paint-order: stroke; stroke: #fff; stroke-width: 4px }
.note { font-size: 11px; fill: #5f6368 }
""" % (W, H, W, H)


def main() -> None:
    from playwright.sync_api import sync_playwright

    out = Path(__file__).resolve().parents[1] / "architecture-diagrams.pdf"
    doc = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='page'>{current()}</div><div class='page'>{target()}</div></body></html>"
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        f = Path(tmp) / "d.html"
        f.write_text(doc, encoding="utf-8")
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(f.as_uri())
        page.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
        for i, sel in enumerate((".page:nth-of-type(1)", ".page:nth-of-type(2)")):
            page.locator(sel).screenshot(path=str(Path(tmp).parent / f"diagram-{i + 1}.png"))
        b.close()
    print(out)


if __name__ == "__main__":
    main()
