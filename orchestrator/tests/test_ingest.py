"""Kontrakt danych v2, ingestia (landing -> dokumenty), wybór batcha i graf Dagstera (store/s3/model zastąpione atrapami)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import dagster as dg
import pytest
from dagster import instance_for_test

from pipeline import analyze, contract, definitions, ingest, preprocess, s3, store, transcribe

SHA = "a" * 64


def item(external_id="v1", module="third_party_ads", captured="2026-11-01T10:00:00Z", **over):
    base = {
        "schema_version": 2,
        "source": {
            "system": "demo",
            "platform": "youtube",
            "external_id": external_id,
            "url": f"https://y/{external_id}",
        },
        "module": module,
        "observation": {"advertiser": {"handle": "@kanal"}, "advertised_firm": "Alfa"},
        "captured_at": captured,
        "text": "Polecam Alfa, kod PROMO",
    }
    return base | over


def blob(obj) -> bytes:
    return json.dumps(obj).encode()


# --- kontrakt ---------------------------------------------------------------------------------------------------


def test_contract_accepts_valid_item_and_builds_source_key():
    parsed = contract.parse(blob(item()))
    assert parsed.source_key == "youtube:v1" and parsed.observation.advertised_firm == "Alfa"


@pytest.mark.parametrize(
    "bad",
    [
        item(text=None),  # ani tekstu, ani obrazu
        item(module="nieznany"),
        item(schema_version=1),
        item(images=[{"key": "k", "sha256": "abc"}]),  # za krótki skrót
        item(images=[{"key": "k", "sha256": SHA, "variant": "smartwatch"}]),
        {"schema_version": 2},
    ],
)
def test_contract_rejects_invalid_items(bad):
    with pytest.raises(ValueError):
        contract.parse(blob(bad))


def test_contract_images_have_variant_and_focus_defaults():
    parsed = contract.parse(blob(item(images=[{"key": "k", "sha256": SHA}])))
    assert (parsed.images[0].variant, parsed.images[0].focus) == ("original", "page")


def test_json_schema_file_matches_the_model():
    from pathlib import Path

    schema_file = Path(__file__).resolve().parents[2] / "docs" / "intake-item.schema.json"
    if (
        schema_file.exists()
    ):  # generowany: python -m pipeline.contract > docs/intake-item.schema.json
        assert json.loads(schema_file.read_text()) == contract.IntakeItem.model_json_schema()


# --- wybór batcha -----------------------------------------------------------------------------------------------


def test_plan_batch_takes_fresh_always_and_old_only_inside_lookback_window():
    now = datetime(2026, 11, 22, tzinfo=UTC)
    since = now - timedelta(days=30)
    rows = [
        {
            "id": 1,
            "fresh": True,
            "ref_at": now - timedelta(days=200),
        },  # nowy, ale stary: bierzemy (bez okna)
        {"id": 2, "fresh": False, "ref_at": now - timedelta(days=5)},  # inny model, w oknie
        {"id": 3, "fresh": False, "ref_at": now - timedelta(days=90)},  # inny model, poza oknem
        {"id": 4, "fresh": True, "ref_at": now - timedelta(days=1)},
    ]
    batch, counts = store.plan_batch(rows, since, limit=10)
    assert [r["id"] for r in batch] == [1, 4, 2]  # nowe pierwsze, potem przeliczane
    assert counts == {
        "fresh": 2,
        "reprocess_in_window": 1,
        "skipped_outside_window": 1,
        "selected": 3,
        "deferred_by_batch_size": 0,
    }
    limited, c2 = store.plan_batch(rows, since, limit=2)
    assert [r["id"] for r in limited] == [1, 4] and c2["deferred_by_batch_size"] == 1


# --- graf Dagstera ----------------------------------------------------------------------------------------------


def _world(monkeypatch, objects: dict[str, bytes], known=frozenset()):
    monkeypatch.setenv("JEV_MODEL", "m")
    monkeypatch.setattr(s3, "ensure_bucket", lambda: None)
    monkeypatch.setattr(s3, "list_keys", lambda prefix: [*objects, "raw/readme.txt"])
    monkeypatch.setattr(s3, "get", lambda k: objects[k])
    monkeypatch.setattr(store, "known_object_keys", lambda: set(known))
    rejected, ingested = [], []
    monkeypatch.setattr(store, "reject", lambda key, reason: rejected.append((key, reason)))
    monkeypatch.setattr(
        store,
        "ingest",
        lambda it, key, text, h, run: ingested.append((it.source_key, key, text, h)) or "new",
    )
    return rejected, ingested


def test_intake_items_validates_skips_known_and_quarantines_invalid(monkeypatch):
    objects = {
        "raw/youtube/v2/b.json": blob(item("v2", captured="2026-11-03T00:00:00Z")),
        "raw/youtube/v1/a.json": blob(item("v1", captured="2026-11-01T00:00:00Z")),
        "raw/youtube/bad/c.json": b'{"schema_version": 2}',
        "raw/youtube/old/d.json": blob(item("old")),
    }
    rejected, _ = _world(monkeypatch, objects, known={"raw/youtube/old/d.json"})
    with instance_for_test() as instance:
        result = dg.materialize([definitions.intake_items], instance=instance)
    out = result.output_for_node("intake_items")
    assert [e["item"].source_key for e in out] == [
        "youtube:v1",
        "youtube:v2",
    ]  # wg captured_at, bez znanych
    assert len(rejected) == 1 and rejected[0][0] == "raw/youtube/bad/c.json"
    meta = result.get_asset_materialization_events()[0].materialization.metadata
    assert meta["new_objects"].value == 2 and meta["rejected"].value == 1


def test_documents_asset_cleans_text_hashes_with_image_digests_and_counts_outcomes(monkeypatch):
    objects = {
        "raw/youtube/v1/a.json": blob(
            item(text="<p>Ala  ma</p>", images=[{"key": "k", "sha256": SHA}])
        )
    }
    _, ingested = _world(monkeypatch, objects)
    with instance_for_test() as instance:
        result = dg.materialize(
            [definitions.intake_items, definitions.documents], instance=instance
        )
    key, _, text, digest = ingested[0]
    assert text == "Ala ma" and digest == preprocess.content_hash("Ala ma", [SHA])
    assert result.output_for_node("documents") == {
        "new": 1,
        "changed": 0,
        "unchanged": 0,
        "stale": 0,
    }


def _docs():
    img = {"variant": "original", "focus": "page", "image_key": "images/x.png"}

    def mk(i, module):
        return {
            "id": i,
            "key": f"k{i}",
            "module": module,
            "source_url": "u",
            "title": None,
            "text": "t",
            "hash": f"h{i}",
            "label": None,
            "images": [dict(img)],
        }

    return [mk(1, "third_party_ads"), mk(2, "self_promotion"), mk(3, "non_investment_companies")]


def _graph(monkeypatch, **scores):
    _world(monkeypatch, {})
    seen = {}
    monkeypatch.setattr(
        store,
        "select_batch",
        lambda *a: seen.update(args=a) or (_docs(), {"fresh": 3, "selected": 3}),
    )
    monkeypatch.setattr(ingest, "_data_uri", lambda key: f"data:image/png;base64,{key}")
    monkeypatch.setattr(store, "done_ids", lambda docs, model: set())
    saved, calls = [], []
    monkeypatch.setattr(store, "save_result", lambda *a: saved.append(a))
    monkeypatch.setattr(store, "log_call", lambda *a: calls.append(a))
    monkeypatch.setattr(analyze, "state", lambda doc: "STATE")
    for name, score in (("ad_score", 0.8), ("rules_scores", 0.6), ("advisory_score", 0.7)):
        monkeypatch.setattr(analyze, name, lambda doc, s=score: (s, {}))
    return seen, saved, calls


def test_job_selects_with_config_splits_by_module_and_stores_scores_per_version(monkeypatch):
    seen, saved, calls = _graph(monkeypatch)
    run_config = {
        "ops": {
            "analysis_batch": {
                "config": {
                    "batch_size": 7,
                    "reprocess_lookback_days": 14,
                    "modules": ["self_promotion"],
                }
            }
        }
    }
    with instance_for_test() as instance:
        result = definitions.defs.resolve_job_def("process_batch").execute_in_process(
            instance=instance, run_config=run_config
        )
    assert result.success
    assert seen["args"] == (
        "m",
        ["self_promotion"],
        7,
        14,
    )  # parametry ingestii trafiają do wyboru batcha
    assert sorted((a[0], a[1], a[3], a[4]) for a in saved) == [  # (doc, moduł, hash wersji, score)
        (1, "third_party_ads", "h1", 0.8),
        (2, "self_promotion", "h2", 0.6),
        (3, "non_investment_companies", "h3", 0.7),
    ]
    assert sorted((c[0], c[3], c[4]["score"]) for c in calls) == [
        (1, "STATE", 0.8),
        (2, "STATE", 0.6),
        (3, "STATE", 0.7),
    ]


def test_default_config_comes_from_env_style_defaults_and_covers_all_modules(monkeypatch):
    seen, _, _ = _graph(monkeypatch)
    with instance_for_test() as instance:
        definitions.defs.resolve_job_def("process_batch").execute_in_process(instance=instance)
    model, modules, batch, days = seen["args"]
    assert set(modules) == set(contract.MODULES) and batch > 0 and days == 30


def test_nothing_runs_automatically():
    assert not definitions.defs.sensors and not definitions.defs.schedules


def test_failed_model_call_is_logged_with_error_and_fails_asset(monkeypatch):
    _, _, calls = _graph(monkeypatch)

    def boom(doc):
        raise RuntimeError("boom")

    monkeypatch.setattr(analyze, "ad_score", boom)
    with instance_for_test() as instance:
        result = dg.materialize(
            [
                definitions.intake_items,
                definitions.documents,
                definitions.analysis_batch,
                definitions.transcribed_batch,
                definitions.preprocessed_batch,
                definitions.module_splits,
                definitions.ad_scores,
            ],
            instance=instance,
            raise_on_error=False,
        )
    assert not result.success
    errors = [c for c in calls if c[4] is None]
    assert errors and errors[0][7] == "boom" and errors[0][0] == 1


# --- preprocessing (UKNF: HTML, normalizacja, duplikaty, tokeny i wektory) -------------------------------------------


def test_clean_text_strips_html_scripts_entities_invisibles_and_normalizes_unicode():
    from pipeline import preprocess

    raw = "<p>Zysk&nbsp;18%</p><script>alert(1)</script><style>p{}</style>\u200bKUP\ufb01 teraz &amp; zarabiaj"
    assert (
        preprocess.clean_text(raw) == "Zysk 18% KUPfi teraz & zarabiaj"
    )  # ﬁ (ligatura) -> fi przez NFKC
    assert preprocess.clean_text("  ") is None and preprocess.clean_text(None) is None


def test_embedding_is_deterministic_unit_length_and_similarity_reflects_overlap():
    from pipeline import preprocess as p

    a = p.embed(p.tokens("Otwórz konto z kodem PROMO i odbierz 50 zł na start"))
    assert a == p.embed(p.tokens("Otwórz konto z kodem PROMO i odbierz 50 zł na start"))
    assert abs(p.cosine(a, a) - 1) < 1e-9
    near = p.embed(p.tokens("Otwórz konto z kodem PROMO i odbierz 50 zł na start!!"))
    far = p.embed(p.tokens("Dzisiejsza sesja na GPW: WIG20 spadł o 0,4 procent"))
    assert p.cosine(a, near) > 0.95 > p.cosine(a, far)


def test_find_duplicates_is_per_module_text_only_and_keeps_the_first_as_representative():
    from pipeline import preprocess as p

    promo = "Otwórz konto z kodem PROMO i odbierz 50 zł na start w Alfa Capital"
    docs = [
        {"id": 1, "module": "third_party_ads", "text": promo, "images": []},
        {
            "id": 2,
            "module": "third_party_ads",
            "text": promo + " !",
            "images": [],
        },  # prawie ten sam tekst
        {
            "id": 3,
            "module": "non_investment_companies",
            "text": promo,
            "images": [],
        },  # inny moduł: osobno
        {
            "id": 4,
            "module": "third_party_ads",
            "text": promo,
            "images": [{"variant": "original"}],
        },  # z obrazem: osobno
        {
            "id": 5,
            "module": "third_party_ads",
            "text": "Zupełnie inny wpis o gotowaniu zupy",
            "images": [],
        },
    ]
    assert p.find_duplicates(docs) == {2: 1}


def test_duplicates_get_the_originals_score_without_a_second_model_call(monkeypatch):
    seen, saved, calls = _graph(monkeypatch)
    promo = "Otwórz konto z kodem PROMO i odbierz 50 zł na start w Alfa Capital"
    docs = [
        {
            "id": i,
            "key": f"k{i}",
            "module": "third_party_ads",
            "source_url": "u",
            "title": None,
            "text": promo,
            "hash": f"h{i}",
            "label": None,
            "images": [],
        }
        for i in (1, 2)
    ]
    monkeypatch.setattr(store, "select_batch", lambda *a: (docs, {"fresh": 2}))
    scored = []
    monkeypatch.setattr(analyze, "ad_score", lambda d: scored.append(d["id"]) or (0.8, {}))
    with instance_for_test() as instance:
        result = definitions.defs.resolve_job_def("process_batch").execute_in_process(
            instance=instance
        )
    assert result.success and scored == [1]  # model tylko dla oryginału
    dup = next(a for a in saved if a[0] == 2)
    assert (
        dup[4] == 0.8 and dup[5]["duplicate_of"] == "k1" and dup[3] == "h2"
    )  # wynik z hashem wersji duplikatu


# --- opcjonalna transkrypcja (domyślnie pominięta) ----------------------------------------------------------------------


def _transcription_world(monkeypatch, docs):
    _graph(monkeypatch)
    monkeypatch.setattr(store, "select_batch", lambda *a: (docs, {"fresh": len(docs)}))


def test_transcription_is_skipped_by_default_and_documents_pass_through_unchanged(monkeypatch):
    docs = _docs()
    docs[0]["audio_key"] = "audio/a.mp3"  # nawet z audio: bez włączenia nic się nie dzieje
    _transcription_world(monkeypatch, docs)
    monkeypatch.setattr(transcribe, "transcribe", lambda p: pytest.fail("nie wolno transkrybować"))
    with instance_for_test() as instance:
        result = dg.materialize(
            [
                definitions.intake_items,
                definitions.documents,
                definitions.analysis_batch,
                definitions.transcribed_batch,
            ],
            instance=instance,
        )
    out = result.output_for_node("transcribed_batch")
    assert [d["text"] for d in out] == ["t", "t", "t"]
    meta = result.get_asset_materialization_events()[-1].materialization.metadata
    assert meta["skipped"].value is True


def test_enabled_transcription_appends_text_of_documents_with_audio_only(monkeypatch):
    docs = _docs()
    docs[1]["audio_key"] = "audio/b.mp3"
    _transcription_world(monkeypatch, docs)
    monkeypatch.setattr(s3, "get", lambda k: b"AUDIO")
    seen = []
    monkeypatch.setattr(
        transcribe,
        "transcribe",
        lambda p: seen.append(Path(p).name) or {"text": " Dzień dobry ", "chunks": []},
    )
    run_config = {"ops": {"transcribed_batch": {"config": {"enabled": True}}}}
    with instance_for_test() as instance:
        result = dg.materialize(
            [
                definitions.intake_items,
                definitions.documents,
                definitions.analysis_batch,
                definitions.transcribed_batch,
            ],
            instance=instance,
            run_config=run_config,
        )
    out = result.output_for_node("transcribed_batch")
    assert [d["text"] for d in out] == ["t", "t\n\nDzień dobry", "t"] and seen == ["b.mp3"]
    assert "transcribed" not in out[0]


def test_transcribe_without_optional_dependencies_fails_with_a_clear_message():
    from pipeline import transcribe

    transcribe._asr.cache_clear()
    try:
        import torch  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="torch, transformers i accelerate"):
            transcribe.transcribe("x.mp3")
    assert transcribe.model_id() == "openai/whisper-large-v3-turbo"
