"""Pure decisions of the scraper that determine what reaches the pipeline: language, topic, ownership, name matching, registry parsing."""

import pytest

from investwatch_common.text import extract_domains, normalize_name

from app.lang import is_polish
from app.models import RawPost
from app.queries import M2Brand
from app.registry.knf import _cell, _split_numbered
from app.relevance import investment_related


def post(title: str, content: str = "", url: str = "https://example.pl/x") -> RawPost:
    return RawPost(platform="web", external_id="x", url=url, title=title, content=content)


# --- language filter ---------------------------------------------------------------------------------------------


def test_polish_text_is_kept_foreign_script_is_dropped_and_unsure_short_text_is_kept():
    polish = (
        "Inwestowanie na giełdzie wymaga cierpliwości, dywersyfikacji portfela i świadomości ryzyka utraty kapitału."
    )
    assert is_polish(polish) == (True, "pl")
    assert is_polish("الاستثمار في البورصة يتطلب الصبر وتنويع المحفظة والوعي بمخاطر خسارة رأس المال") == (False, "ar")
    assert is_polish("OK") == (True, None)  # too short to judge: not rejected


# --- topic filter ------------------------------------------------------------------------------------------------


def test_investment_content_is_kept_and_shop_coupons_are_dropped():
    keep, why = investment_related(
        post("Jak inwestować w ETF? Poradnik dla początkujących", "Fundusze ETF na GPW, akcje i obligacje.")
    )
    assert keep and "etf" in why["strong"]
    shop, _ = investment_related(
        post("Kod rabatowy -20% na buty", "Kupon rabatowy, darmowa dostawa, Black Friday, wyprzedaż.")
    )
    assert not shop
    gibberish, _ = investment_related(post("Przepis na sernik", "Ser, jajka, cukier."))
    assert not gibberish


def test_whole_word_acronyms_do_not_match_inside_other_words():
    keep, _ = investment_related(post("Wigilia w domu, święta i ikea", "Lista zakupów na święta."))
    assert not keep  # "wig" w "wigilia" i "ike" w "ikea" nie są wskazówkami o inwestowaniu


# --- ownership (module 2 keeps only the firm's own content) --------------------------------------------------------


def test_brand_owns_its_domain_and_subdomains_but_not_lookalikes():
    xtb = M2Brand("XTB", ("xtb.com",), ("xtb", "x-trade brokers"))
    assert xtb.owns_host("www.xtb.com") and xtb.owns_host("pl.xtb.com")
    assert not xtb.owns_host("notxtb.com") and not xtb.owns_host("xtb.com.evil.io")


def test_brand_owns_a_channel_named_after_it_but_not_one_that_only_mentions_it():
    xtb = M2Brand("XTB", ("xtb.com",), ("xtb",))
    assert xtb.owns_channel("XTB Polska") and xtb.owns_channel(None, "XTB")
    assert not xtb.owns_channel("Inwestuję z XTB") and not xtb.owns_channel(None)


# --- name matching (shared with the analytic modules) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("XTB S.A.", "xtb"),
        ("Trigon Dom Maklerski S.A.", "trigon"),
        ("APS Financial", "aps financial"),
        ("  ŚLĄSKI  ", "slaski"),
    ],
)
def test_normalize_name_ignores_case_diacritics_and_legal_forms(raw, expected):
    assert normalize_name(raw) == expected


def test_extract_domains_returns_bare_unique_domains():
    assert extract_domains("Zobacz www.xtb.com/pl, mbank.pl oraz xtb.com") == ["xtb.com", "mbank.pl"]


# --- KNF registry parsing --------------------------------------------------------------------------------------------


def test_registry_cell_separates_current_lines_from_struck_through_former_ones():
    assert _cell("Nowa nazwa<br />ul. Prosta 1<strike>Stara nazwa</strike>") == (
        ["Nowa nazwa", "ul. Prosta 1"],
        ["Stara nazwa"],
    )


def test_registry_cell_ignores_one_letter_strike_noise():
    current, struck = _cell("<strike> <br />B</strike>iuro Maklerskie")
    assert struck == [] and "iuro Maklerskie" in " ".join(current)


def test_numbered_registry_items_are_split_and_unnumbered_ones_joined():
    assert _split_numbered(["1. Alfa", "2. Beta"]) == ["Alfa", "Beta"]
    assert _split_numbered(["Alfa", "Beta"]) == ["Alfa Beta"] and _split_numbered([]) == []
