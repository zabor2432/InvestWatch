import pytest
import yaml

import collect
import manipulate

# reguły modułu 2 (orchestrator/pipeline/rules.py); ten projekt nie zależy od orkiestratora, więc lista jest tu wprost
RULE_IDS = {str(i) for i in range(2, 19) if i != 12} | {"12a", "12b"}


def test_manifest_is_valid_and_covers_every_module():
    entries = collect.load_sources()
    assert {e["module"] for e in entries} == collect.MODULES
    assert all(e["url"].startswith("https://") for e in entries)
    assert all("label" not in e or "basis" in e for e in entries)  # etykieta zawsze z uzasadnieniem


def test_every_recipe_targets_known_rules_and_manipulation_only_on_module_2():
    for name, r in manipulate.RECIPES.items():
        assert r.rules and set(r.rules) <= RULE_IDS, name
    for e in collect.load_sources():
        assert not e.get("manipulate") or e["module"] == "self_promotion", e["id"]


def test_recipes_used_in_manifest_cover_most_module_2_rules():
    used = {
        r
        for e in collect.load_sources()
        for name in e.get("manipulate", [])
        for r in manipulate.RECIPES[name].rules
    }
    assert {"2", "3", "4", "5", "6", "7", "8", "10", "11", "13", "15", "16", "17", "18"} <= used


def test_manipulated_record_has_label_true_and_rules_original_keeps_manifest_label():
    entry = {
        "id": "x",
        "module": "self_promotion",
        "url": "https://www.broker.pl/oferta",
        "label": None,
    }
    img = [{"file": "a.png", "variant": "desktop", "focus": "page"}]
    orig = collect.record(entry, "x", "T", "tekst", img, None)
    man = collect.record(entry, "x--tiny_print", "T", "tekst", img, "tiny_print")
    assert orig["label"] is None and orig["manipulated"] is None
    assert man["label"] is True and man["manipulated"] == {"rules": ["4"], "recipe": "tiny_print"}
    assert orig["advertiser"]["handle"] == "broker.pl" and man["meta"] == {"derived_from": "x"}


def test_script_wraps_recipe_with_prelude():
    js = manipulate.script("tiny_print")
    assert "riskNodes" in js and js.startswith("(() =>")


@pytest.mark.parametrize(
    "bad",
    [
        {"entries": [{"id": "a", "module": "zly", "url": "u"}]},
        {
            "entries": [
                {"id": "a", "module": "self_promotion", "url": "u", "manipulate": ["nie_ma"]}
            ]
        },
    ],
)
def test_load_sources_rejects_bad_manifest(tmp_path, bad):
    f = tmp_path / "s.yaml"
    f.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError):
        collect.load_sources(f)
