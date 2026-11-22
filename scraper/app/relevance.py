"""Is a post about investing? Drops off-topic hits (shop coupons, plain bank accounts, payment terminals).

Every module looks for investment content: ads of investment firms (1), their marketing of investment services (2),
unauthorised investment advice (3). A post is kept when its text (title, content, transcript; first 20k chars) uses
investment vocabulary: a strong term in the title, at least two distinct "strong" terms, or one strong term and two
"weak" ones. Coupon / discount
pages ("kod rabatowy", "kupon", "Black Friday") need three strong terms - a broker's promo code page passes, a shoe
shop's does not. Matching is case- and diacritic-insensitive on word starts.
"""

import re

from investwatch_common.text import fold

from app.models import RawPost

STRONG = (
    "inwest", "investing", "investment", "gield", "gpw", "akcj", "etf", "obligacj", "fundusz", "ike", "ikze", "makler",
    "emakler", "xstation", "forex", "cfd", "kontrakt", "dywidend", "trading", "trader", "tradingow", "broker",
    "notowan", "stopa zwrotu", "stopy zwrotu", "rekomendacje kupna", "rekomendacje sprzedazy", "rekomendacj gield",
    "rekomendacj inwest", "kryptowalut", "bitcoin", "dzwigni", "nasdaq",
    "s&p", "wig20", "wig", "portfel inwest", "spolk gield", "spolek gield", "rachunek maklersk", "konto maklersk",
    "doradztw inwest", "doradc inwest", "doradca finansow", "wealth", "family office", "zarzadzan majatk",
    "zarzadzan portfel", "instrument finansow", "papier wartosciow", "hossa", "bessa", "sygnaly transakcyjn",
    "spread", "lewar",
)
WEAK = (
    "kapital", "zysk", "ryzyk", "rynek", "rynk", "kurs", "walut", "oszczedz", "emerytur", "sygnal", "majat", "doradc",
    "portfel", "spolk", "spolek", "lokat", "procent", "zwrot", "strat", "pieniadz", "finans", "analiz", "wycen",
    "premi", "prowizj", "rekomendacj",
)
COUPON = re.compile(
    r"\b(kod(y)? rabatow|kupon|rabat|znizk|promokod|cashback|black friday|cyber monday|darmowa dostawa|wyprzedaz"
    r"|voucher|coupon|discount code|promo code)",
)


# acronyms that must match as whole words ("ike" is not "ikea", "wig" is not "wigilia")
WHOLE_WORD = {"ike", "ikze", "etf", "gpw", "cfd", "wig", "wig20", "s&p", "spread"}


def _hits(text: str, terms: tuple[str, ...]) -> set[str]:
    return {t for t in terms
            if re.search(rf"(?<![a-z0-9]){re.escape(t)}" + (r"(?![a-z0-9])" if t in WHOLE_WORD else ""), text)}


def investment_related(raw: RawPost) -> tuple[bool, dict]:
    """(keep, details) - details name the matched terms, for the job stats / logs."""
    text = fold("\n".join(x for x in (raw.title, raw.content, raw.transcript) if x)[:20000])
    strong, weak = _hits(text, STRONG), _hits(text, WEAK)
    coupon = bool(COUPON.search(fold(f"{raw.title or ''} {raw.url}"))) or len(COUPON.findall(text)) >= 3
    in_title = bool(_hits(fold(raw.title or ""), STRONG))
    if coupon:
        keep = len(strong) >= 3
    else:
        keep = in_title or len(strong) >= 2 or (len(strong) >= 1 and len(weak) >= 2)
    return keep, {"strong": sorted(strong)[:10], "weak": len(weak), "coupon": coupon, "in_title": in_title}
