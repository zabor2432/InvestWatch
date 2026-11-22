"""Przepisy manipulacji: kontrolowane psucie strony przed zrzutem, żeby powstał przykład naruszenia konkretnej reguły.
Strony prawdziwych firm zostają w kolekcji jako oryginały; wariant dostaje `manipulated {rules, recipe}` i nigdy nie jest
traktowany jak prawdziwy materiał (poza gitem, w UI znacznik "zmanipulowany").

Przepis to JS wykonywany na stronie; zwraca liczbę zmienionych elementów (0 = przepis nie pasuje do strony, wariantu nie tworzymy).
`riskNodes()` znajduje najmniejsze bloki tekstu z informacją o ryzyku i oznacza pierwszy atrybutem data-iw-risk (do wycinka)."""

from dataclasses import dataclass

PRELUDE = r"""
const RISK = /ryzyk|utrat[aęy]\s+(kapitału|całości|wpłacon)|wyniki historyczne/i;
const text = (el) => (el.innerText || '').trim();
const riskNodes = () => [...document.body.querySelectorAll('*:not(script):not(style):not(noscript)')].filter((el) => {
  const t = text(el);
  // blok z ryzykiem: bez dziecka, które zawiera prawie cały jego tekst (wtedy bierzemy dziecko)
  return t.length >= 40 && t.length <= 900 && RISK.test(t) && ![...el.children].some((c) => text(c).length >= 0.8 * t.length);
});
const banner = (html, bg) => {
  const d = document.createElement('div');
  d.innerHTML = html;
  d.style.cssText = `background:${bg};color:#fff;font:700 34px/1.25 Arial,sans-serif;padding:28px 40px;text-align:center;position:relative;z-index:99999`;
  document.body.prepend(d);
  return 1;
};
const each = (nodes, fn) => { nodes.forEach(fn); return nodes.length; };
"""


@dataclass(frozen=True)
class Recipe:
    rules: tuple[str, ...]  # reguły, które przepis ma złamać (ground truth wariantu)
    js: str
    mobile_only: bool = (
        False  # zmiana tylko na ekranie telefonu (reguła 8: różnica między ekranami)
    )


RECIPES: dict[str, Recipe] = {
    "tiny_print": Recipe(
        ("4",),
        "each(riskNodes(), (e) => { e.style.fontSize = '5px'; e.style.lineHeight = '6px'; })",
    ),
    "low_contrast": Recipe(
        ("5",),
        "each(riskNodes(), (e) => { e.style.color = '#e4e4e4'; e.style.opacity = '.4'; e.style.background = '#fff'; })",
    ),
    "blurred": Recipe(("5", "6"), "each(riskNodes(), (e) => { e.style.filter = 'blur(3px)'; })"),
    "behind_link": Recipe(
        ("7",),
        "each(riskNodes(), (e) => { e.innerHTML = '<a href=\"#\">Szczegóły i informacje prawne w regulaminie</a>'; })",
    ),
    "removed_warning": Recipe(("3",), "each(riskNodes(), (e) => { e.style.display = 'none'; })"),
    "mobile_clipped": Recipe(
        ("8",),
        "each(riskNodes(), (e) => { Object.assign(e.style, {display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', height: '1.3em', maxWidth: '100vw'}); })",
        mobile_only=True,
    ),
    "inflated_returns": Recipe(
        ("12a", "12b", "13", "14"),
        "banner('+312% zysku w 3 miesiące!<br><small style=\"font-size:20px\">Dołącz do klientów, którzy już zarabiają</small>', '#0a7d3b') + each(riskNodes(), (e) => { e.style.display = 'none'; })",
    ),
    "no_ad_label": Recipe(
        ("2",),
        "each([...document.querySelectorAll('span,small,div,p,a,button')].filter((e) => /^(reklama|materiał reklamowy|treść sponsorowana|współpraca reklamowa)\\b/i.test(text(e)) && text(e).length < 60), (e) => { e.style.display = 'none'; })",
    ),
    "forecast": Recipe(("15",), "banner('Prognozujemy: +18% do końca roku', '#1b4f9c')"),
    "regulator_approval": Recipe(("17",), "banner('Oferta zatwierdzona przez KNF', '#7a1f1f')"),
    "safe_because_supervised": Recipe(
        ("18",),
        "banner('Inwestuj bezpiecznie: nadzór KNF gwarantuje ochronę Twoich środków', '#4a2a7a')",
    ),
    "tax_claim": Recipe(("16",), "banner('Zysk wolny od podatku dla każdego klienta', '#0b6b6b')"),
    "comparison_no_source": Recipe(
        ("11",), "banner('Najniższe spready na rynku: 2x taniej niż u konkurencji', '#8a5a00')"
    ),
    "english_warning": Recipe(
        ("10",),
        "each(riskNodes(), (e) => { e.textContent = 'Investing involves risk, including the loss of the invested capital. Past performance does not guarantee future results.'; })",
    ),
}


def script(recipe: str) -> str:
    return f"(() => {{ {PRELUDE} return {RECIPES[recipe].js}; }})()"


# znacznik pierwszego bloku z ryzykiem (do wycinka); po przepisie, bo przepis może zmienić węzły
MARK_RISK = f"(() => {{ {PRELUDE} const n = riskNodes(); if (n[0]) n[0].setAttribute('data-iw-risk', '1'); return n.length; }})()"
