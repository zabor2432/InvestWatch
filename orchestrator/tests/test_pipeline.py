import json

import httpx
import pytest

from pipeline import analyze, llm, preprocess
from pipeline.rules import RULES, VISUAL


def test_clean_text_strips_html_and_whitespace():
    assert preprocess.clean_text("<p>Ala  ma\n<b>kota</b></p>") == "Ala ma kota"
    assert preprocess.clean_text(None) is None


def test_rules_are_18_without_rule_1():
    assert len(RULES) == 18 and "1" not in RULES and {"12a", "12b"} <= set(RULES)


def _api(monkeypatch, handler, **env):
    for k in ("TYPESAFE_API_KEY", "TYPESAFE_BASE_URL", "JEV_MODEL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok(answers):
    return httpx.Response(
        200,
        json={
            "model": "openjev-0.1",
            "answers": {k: {"type": "noul", "noul": v} for k, v in answers.items()},
        },
    )


def test_classify_uses_codiv_openjev_defaults_and_bearer_key(monkeypatch):
    seen = {}

    def handler(req):
        seen.update(
            url=str(req.url), auth=req.headers["authorization"], body=json.loads(req.content)
        )
        return _ok({"q": 0.97})

    client = _api(monkeypatch, handler, TYPESAFE_API_KEY="sk-codiv-x")
    assert llm.classify("stan", {"q": "Czy?"}, client=client) == {"q": 0.97}
    assert (
        seen["url"] == "https://api.codiv.ai/v1/systemone" and seen["auth"] == "Bearer sk-codiv-x"
    )
    assert seen["body"]["model"] == "openjev-latest"
    assert seen["body"]["questions"]["q"] == {"type": "noul", "instructions": "Czy?"}


def test_classify_requires_key_for_hosted_api_but_not_for_local_server(monkeypatch):
    client = _api(monkeypatch, lambda req: _ok({"q": 0.5}))
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        llm.classify("s", {"q": "Q"}, client=client)
    client = _api(
        monkeypatch, lambda req: _ok({"q": 0.5}), TYPESAFE_BASE_URL="http://localhost:8080"
    )
    assert llm.classify("s", {"q": "Q"}, client=client) == {"q": 0.5}


def test_classify_retries_rate_limit_but_not_quota_and_explains_bad_key(monkeypatch):
    calls = []

    def flaky(req):
        calls.append(1)
        err = {"detail": {"error_type": "rate_limit_error", "message": "x"}}
        return httpx.Response(429, json=err) if len(calls) < 3 else _ok({"q": 0.1})

    assert llm.classify("s", {"q": "Q"}, client=_api(monkeypatch, flaky, TYPESAFE_API_KEY="k")) == {
        "q": 0.1
    }
    assert len(calls) == 3

    calls.clear()
    quota = httpx.Response(
        429, json={"detail": {"error_type": "quota_exceeded_error", "message": "x"}}
    )
    with pytest.raises(RuntimeError, match="limit"):
        llm.classify(
            "s",
            {"q": "Q"},
            client=_api(monkeypatch, lambda r: calls.append(1) or quota, TYPESAFE_API_KEY="k"),
        )
    assert len(calls) == 1

    denied = httpx.Response(403, json={"detail": {"error_type": "authentication_error"}})
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        llm.classify(
            "s", {"q": "Q"}, client=_api(monkeypatch, lambda r: denied, TYPESAFE_API_KEY="bad")
        )


@pytest.mark.parametrize("answers", [{"a": 0.8}, {"a": 0.8, "b": 1.7}])
def test_classify_rejects_missing_or_out_of_range(monkeypatch, answers):
    client = _api(monkeypatch, lambda req: _ok(answers), TYPESAFE_API_KEY="k")
    with pytest.raises(ValueError):
        llm.classify("s", {"a": "A", "b": "B"}, client=client)


def test_rules_scores_returns_18_results_visual_rules_null(monkeypatch):
    monkeypatch.setattr(
        analyze.llm, "classify", lambda state, qs, images=None: {r: 0.2 for r in qs} | {"3": 0.9}
    )
    score, details = analyze.rules_scores({"source_url": "u", "text": "t"})
    assert len(details["rules"]) == 18 and all(details["rules"][r] is None for r in VISUAL)
    assert score == 0.9


def test_classify_sends_criteria_and_images(monkeypatch):
    seen = {}

    def handler(req):
        seen.update(body=json.loads(req.content))
        return _ok({"q": 0.5})

    client = _api(monkeypatch, handler, TYPESAFE_API_KEY="k")
    q = {"q": {"instructions": "Czy?", "criteria": {"true": "T", "false": "F"}}}
    llm.classify("s", q, images=["data:image/png;base64,AAA"], client=client)
    assert seen["body"]["questions"]["q"] == {
        "type": "noul",
        "instructions": "Czy?",
        "criteria": {"true": "T", "false": "F"},
    }
    assert seen["body"]["images"] == ["data:image/png;base64,AAA"]


def _png_uri(size=(300, 200), color=(255, 0, 0, 0)):
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _decode(uri):
    import base64
    import io

    from PIL import Image

    return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


def test_footer_is_bottom_strip_and_images_are_flattened_to_white():
    from pipeline import images

    uri = _png_uri((300, 200))
    full, foot = _decode(images.full(uri)), _decode(images.footer(uri))
    assert full.size == (300, 200) and full.getpixel((5, 5)) == (
        255,
        255,
        255,
    )  # przezroczystość -> biel
    assert foot.size == (300, int(200 * images.FOOTER_FRACTION))


def _doc(*imgs):
    """Dokument z obrazami (variant, focus) jako prawdziwe data-URI."""
    return {
        "source_url": "u",
        "text": "t",
        "images": [{"variant": v, "focus": f, "uri": _png_uri()} for v, f in imgs],
    }


def _recording(monkeypatch):
    calls = []

    def fake(state, qs, images=None):
        calls.append((set(qs), len(images or [])))
        return {r: (0.9 if r == "5" else 0.2) for r in qs}

    monkeypatch.setattr(analyze.llm, "classify", fake)
    return calls


def test_rules_scores_without_image_asks_only_semantic_rules(monkeypatch):
    calls = _recording(monkeypatch)
    _, details = analyze.rules_scores(_doc())
    assert calls == [(set(RULES) - VISUAL, 0)]
    assert [r for r, v in details["rules"].items() if v is None] == sorted(VISUAL)


def test_rules_scores_with_page_image_adds_visual_passes_but_not_responsiveness(monkeypatch):
    calls = _recording(monkeypatch)
    score, details = analyze.rules_scores(_doc(("original", "page")))
    assert calls == [(set(RULES) - VISUAL, 1), ({"5", "6"}, 1), ({"4"}, 2)]
    assert (
        details["rules"]["8"] is None and score == 0.9
    )  # bez pary desktop/mobile reguła 8 = nie dotyczy
    assert all(details["rules"][r] is not None for r in set(RULES) - {"8"})


def test_rule_8_is_asked_only_for_a_desktop_and_mobile_pair_and_prefers_risk_crops(monkeypatch):
    calls = _recording(monkeypatch)
    _, details = analyze.rules_scores(_doc(("desktop", "page"), ("mobile", "page")))
    assert calls[-1] == ({"8"}, 2) and details["rules"]["8"] is not None

    calls.clear()
    seen = []
    monkeypatch.setattr(
        analyze.llm,
        "classify",
        lambda s, qs, images=None: seen.append(images) or {r: 0.1 for r in qs},
    )
    analyze.rules_scores(
        _doc(("desktop", "page"), ("mobile", "page"), ("desktop", "risk"), ("mobile", "risk"))
    )
    assert len(seen[-1]) == 2  # para bloków z ryzykiem
    only_desktop = _recording(monkeypatch)
    _, details = analyze.rules_scores(_doc(("desktop", "page")))
    assert details["rules"]["8"] is None and ({"8"}, 2) not in only_desktop


def test_state_lists_attached_images_and_title():
    doc = {
        "source_url": "u",
        "title": "T",
        "text": "x",
        "images": [{"variant": "mobile", "focus": "risk", "uri": ""}],
    }
    assert "Tytuł: T" in analyze.state(doc) and "mobile/risk" in analyze.state(doc)
    assert "obrazy" not in analyze.state({"source_url": "u", "text": "x"})


def test_content_hash_changes_with_any_image_and_ignores_text_case_and_image_order():
    assert preprocess.content_hash("t", ["a"]) != preprocess.content_hash("t", ["b"])
    assert preprocess.content_hash("t", ["a", "b"]) == preprocess.content_hash("T", ["b", "a"])
    assert preprocess.content_hash("t", ["a"]) != preprocess.content_hash("t", ["a", "b"])
