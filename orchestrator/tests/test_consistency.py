"""Wiedza powtórzona w niezależnych projektach. Serwisy się nie importują (łączy je kontrakt przez dane), więc nic nie wymusza
zgodności w czasie wykonania: te testy wykrywają rozjazd, zanim trafi do repozytorium. Źródłem prawdy jest `pipeline/contract.py`."""

import re
from pathlib import Path

import pytest

from pipeline import contract
from pipeline.rules import RULES

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "db/init.sql",  # CHECK na documents.module
        "backend/app/records.py",  # mapowanie moduł -> numer
        "common/investwatch_common/landing.py",  # zadanie scrapera -> moduł
        "demo/seed/seed.py",
        "demo/collect/collect.py",
    ],
)
def test_every_project_knows_exactly_the_modules_of_the_contract(path):
    text = read(path)
    for module in contract.MODULES:
        assert module in text, f"{path} nie zna modułu {module}"


def test_module_names_in_the_database_constraint_match_the_contract():
    constraint = re.search(
        r"module\s+text NOT NULL CHECK \(module IN \(([^)]*)\)\)", read("db/init.sql")
    )
    assert constraint, "brak CHECK na documents.module"
    assert set(re.findall(r"'(\w+)'", constraint.group(1))) == set(contract.MODULES)


def test_our_tables_do_not_collide_with_the_scrapers():
    """Dwa mechanizmy schematu w jednej bazie: nasze tabele z db/init.sql, tabele scrapera z Alembica (common/models.py)."""
    ours = set(re.findall(r"CREATE TABLE (\w+)", read("db/init.sql")))
    scrapers = set(
        re.findall(r'__tablename__ = "(\w+)"', read("common/investwatch_common/models.py"))
    )
    assert ours and scrapers and not ours & scrapers


def test_dashboard_defines_every_rule_id_the_model_scores():
    """Reguły są zdefiniowane osobno w froncie (nazwy, podstawy prawne) i tutaj (pytania): brak id we froncie psuje widok.
    Nazwy w `rules.py` to etykiety w promptach i mogą się różnić od nazw w UI (zmiana prompta wymaga pomiaru jakości)."""
    ids = set(re.findall(r'\{ id: "(\w+)"', read("frontend/src/domain/rules.ts")))
    assert set(RULES) <= ids
