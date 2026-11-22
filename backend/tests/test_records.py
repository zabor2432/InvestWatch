from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import records
from app.main import app


def row(**kw):
    base = {
        "id": 7,
        "module": "self_promotion",
        "source_key": "instagram:1",
        "source_url": "https://www.instagram.com/p/1",
        "text": "t" * 100,
        "title": None,
        "status": "new",
        "platform": "instagram",
        "published_at": datetime(2026, 11, 20, tzinfo=UTC),
        "captured_at": datetime(2026, 11, 21, tzinfo=UTC),
        "content_hash": "h",
        "manipulated": None,
        "observation_id": 3,
        "advertiser_handle": "@firma",
        "advertiser_name": None,
        "advertiser_url": None,
        "advertised_firm": "Alfa",
        "images": [],
        "ground_truth": True,
        "score": 0.9,
        "details": {},
    }
    return base | kw


def test_to_record_maps_observation_platform_dates_and_evidence():
    rec = records.to_record(row())
    assert (rec.id, rec.module, rec.source, rec.entity.kind) == (
        "7",
        2,
        "instagram",
        "investment_firm",
    )
    assert (rec.entity.name, rec.advertised_firm, rec.observation_id) == ("@firma", "Alfa", "3")
    assert rec.published_at.startswith("2026-11-20") and rec.detected_at.startswith("2026-11-21")
    assert rec.title == "t" * 80 + "…" and rec.content == "t" * 100 and not rec.manipulated
    assert [e.kind for e in rec.evidence] == ["snapshot", "hash"] and rec.rule_results is None


def test_title_and_advertiser_name_win_when_present_and_manipulated_flag_is_exposed():
    rec = records.to_record(
        row(title="Tytuł", advertiser_name="Jan", manipulated={"rules": ["6"], "recipe": "x"})
    )
    assert (rec.title, rec.entity.name, rec.manipulated) == ("Tytuł", "Jan", True)
    assert rec.manipulated_rules == ["6"]


def test_images_carry_variant_focus_and_api_urls_and_first_is_screenshot_evidence():
    imgs = [{"variant": "desktop", "focus": "page"}, {"variant": "mobile", "focus": "page"}]
    rec = records.to_record(row(images=imgs))
    assert [(i.variant, i.url) for i in rec.images] == [
        ("desktop", "/api/records/7/images/desktop?focus=page"),
        ("mobile", "/api/records/7/images/mobile?focus=page"),
    ]
    assert [e.kind for e in rec.evidence] == ["snapshot", "screenshot", "hash"]
    assert rec.evidence[1].value == rec.images[0].url  # adres podglądu, nie ścieżka w storage


def test_rules_are_sorted_naturally_and_get_verdicts():
    rules = {"13": 0.1, "12b": 0.5, "2": 0.9, "12a": None, "3": 0.2}
    rec = records.to_record(row(details={"rules": rules}))
    assert [r.rule_id for r in rec.rule_results] == ["2", "3", "12a", "12b", "13"]
    assert [r.verdict for r in rec.rule_results] == ["fail", "pass", "n/a", "uncertain", "pass"]


def test_status_rejects_unknown_value_and_unknown_id(monkeypatch):
    client = TestClient(app)
    assert client.patch("/api/records/1/status", json={"status": "hacked"}).status_code == 422
    assert client.patch("/api/records/abc/status", json={"status": "new"}).status_code == 422
    monkeypatch.setattr(records, "set_status", lambda i, s: False)
    assert client.patch("/api/records/1/status", json={"status": "new"}).status_code == 404


@pytest.mark.parametrize("path", ["/api/records", "/api/model-calls"])
@pytest.mark.parametrize("limit", ["0", "99999"])
def test_list_limit_is_bounded(path, limit):
    assert TestClient(app).get(f"{path}?limit={limit}").status_code == 422


def test_record_image_serves_variant_bytes_with_safe_headers_and_404s(monkeypatch):
    from app import main

    client = TestClient(app)
    asked = []
    monkeypatch.setattr(
        records,
        "get_image_key",
        lambda i, v, f: asked.append((i, v, f)) or ("raw/x.png" if i == 1 else None),
    )
    monkeypatch.setattr(main.storage, "get", lambda key: b"PNGDATA")
    r = client.get("/api/records/1/images/mobile?focus=risk")
    assert r.status_code == 200 and r.content == b"PNGDATA" and asked == [(1, "mobile", "risk")]
    assert (
        r.headers["content-type"] == "image/png"
        and r.headers["x-content-type-options"] == "nosniff"
    )
    assert client.get("/api/records/2/images/desktop").status_code == 404  # brak takiego obrazu
    assert client.get("/api/records/1/images/smartwatch").status_code == 422
    assert client.get("/api/records/1/images/mobile?focus=../x").status_code == 422
    monkeypatch.setattr(records, "get_image_key", lambda i, v, f: "raw/x.exe")
    assert client.get("/api/records/1/images/mobile").status_code == 404  # tylko typy obrazów


def _rec(module, rules=None):
    details = {"rules": rules} if rules is not None else {}
    return records.to_record(row(module=module, details=details))


def test_factor_ids_per_module():
    assert records.factor_ids(_rec("third_party_ads")) == {"is_ad"}
    assert records.factor_ids(_rec("non_investment_companies")) == {"offers_advisory"}
    assert records.factor_ids(_rec("self_promotion", {"2": 0.1, "8": None, "12a": 0.3})) == {
        "2",
        "8",
        "12a",
    }


def test_annotation_requires_exactly_the_records_factors_and_valid_values(monkeypatch):
    from app.schemas import Annotation

    client = TestClient(app)
    monkeypatch.setattr(
        records,
        "get_record",
        lambda i: _rec("self_promotion", {"2": 0.1, "8": None}) if i == 1 else None,
    )
    saved = []
    monkeypatch.setattr(
        records,
        "add_annotation",
        lambda i, who, ans: (
            saved.append((i, who, ans))
            or Annotation(id=5, annotator=who, answers=ans, created_at="2026-11-21T00:00:00+00:00")
        ),
    )

    ok = client.post(
        "/api/records/1/annotations", json={"annotator": "  Ola ", "answers": {"2": 1, "8": None}}
    )
    assert ok.status_code == 201 and saved == [
        (1, "Ola", {"2": 1, "8": None})
    ]  # imię przycięte, null = nie dotyczy
    post = lambda i, body: client.post(f"/api/records/{i}/annotations", json=body).status_code  # noqa: E731
    assert post(1, {"annotator": "Ola", "answers": {"2": 1}}) == 422  # brakuje czynnika
    assert (
        post(1, {"annotator": "Ola", "answers": {"2": 1, "8": 0, "99": 1}}) == 422
    )  # obcy czynnik
    assert (
        post(1, {"annotator": "Ola", "answers": {"2": 2, "8": 0}}) == 422
    )  # wartość spoza 0/1/null
    assert post(1, {"annotator": " ", "answers": {"2": 1, "8": 0}}) == 422  # puste imię
    assert post(1, {"annotator": "x" * 65, "answers": {"2": 1, "8": 0}}) == 422
    assert post(2, {"annotator": "Ola", "answers": {"2": 1, "8": 0}}) == 404  # brak rekordu
    assert len(saved) == 1


def test_judgments_use_record_score_for_modules_1_3_and_rule_score_for_module_2():
    rows = [
        {
            "document_id": 1,
            "module": "third_party_ads",
            "annotator": "Ola",
            "answers": {"is_ad": 1},
            "score": 0.9,
            "details": {},
        },
        {
            "document_id": 2,
            "module": "self_promotion",
            "annotator": "Jan",
            "answers": {"2": 0, "8": None, "5": 1},
            "score": 0.7,
            "details": {"rules": {"2": 0.1, "8": None, "5": 0.95}},
        },
    ]
    got = {
        (j.record_id, j.factor): (j.module, j.annotator, j.human, j.score)
        for j in records.judgments_from_rows(rows)
    }
    assert got == {
        ("1", "is_ad"): (1, "Ola", 1, 0.9),
        ("2", "2"): (2, "Jan", 0, 0.1),
        ("2", "8"): (2, "Jan", None, None),  # człowiek: nie dotyczy, model: nie dotyczy
        ("2", "5"): (2, "Jan", 1, 0.95),
    }


def test_report_endpoint_passes_model_and_validates_length(monkeypatch):
    from app.schemas import ReportResponse

    seen = []
    monkeypatch.setattr(
        records,
        "report",
        lambda m: seen.append(m) or ReportResponse(model=m, models=[], annotators=[], judgments=[]),
    )
    client = TestClient(app)
    assert client.get("/api/report?model=jev-latest").json()["model"] == "jev-latest"
    assert client.get("/api/report").status_code == 200 and seen == ["jev-latest", None]
    assert client.get("/api/report?model=" + "x" * 101).status_code == 422


# --- odświeżanie (Dagster GraphQL) ----------------------------------------------------------------------------------


def _dagster(handler):
    import httpx

    return httpx.Client(transport=httpx.MockTransport(handler))


def _json(data):
    import httpx

    return httpx.Response(200, json={"data": data})


def test_refresh_launches_process_batch_when_nothing_runs():
    import json

    from app import refresh

    sent = []

    def handler(req):
        body = json.loads(req.content)
        sent.append(body)
        if "runsOrError" in body["query"]:
            return _json({"runsOrError": {"__typename": "Runs", "results": []}})
        return _json({"launchRun": {"__typename": "LaunchRunSuccess", "run": {"runId": "abc-123"}}})

    out = refresh.start(_dagster(handler))
    assert out == {"run_id": "abc-123", "status": "QUEUED", "already_running": False}
    assert sent[1]["variables"]["sel"]["jobName"] == "process_batch"


def test_refresh_returns_the_active_run_instead_of_starting_a_second_one():
    from app import refresh

    def handler(req):
        assert b"launchRun" not in req.content
        return _json(
            {
                "runsOrError": {
                    "__typename": "Runs",
                    "results": [{"runId": "r1", "status": "STARTED"}],
                }
            }
        )

    assert refresh.start(_dagster(handler)) == {
        "run_id": "r1",
        "status": "STARTED",
        "already_running": True,
    }


def test_refresh_endpoints_map_dagster_errors_to_502_and_unknown_run_to_404(monkeypatch):
    from app import refresh

    def down(*a):
        raise refresh.DagsterError("Dagster niedostępny")

    client = TestClient(app)
    monkeypatch.setattr(refresh, "start", down)
    assert client.post("/api/refresh").status_code == 502
    monkeypatch.setattr(refresh, "status", lambda run_id: None)
    assert client.get("/api/refresh/0123abcd-0000").status_code == 404
    assert client.get("/api/refresh/'; DROP").status_code == 422  # id walidowane przed wywołaniem


def test_refresh_status_passes_through(monkeypatch):
    monkeypatch.setattr(
        "app.refresh.status", lambda run_id: {"run_id": run_id, "status": "SUCCESS"}
    )
    r = TestClient(app).get("/api/refresh/0123abcd-0000")
    assert r.json() == {"run_id": "0123abcd-0000", "status": "SUCCESS", "already_running": False}
