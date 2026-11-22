"""Odczyt wyników z Postgresa i mapowanie wiersz -> Record (jedyne miejsce znające schemat bazy)."""

import os
import re

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.schemas import (
    Annotation,
    Entity,
    Evidence,
    Judgment,
    ModelInfo,
    Record,
    RecordImage,
    ReportResponse,
    RuleResult,
)

MODULE = {"third_party_ads": 1, "self_promotion": 2, "non_investment_companies": 3}
KIND = {1: "finfluencer", 2: "investment_firm", 3: "unauthorized"}
FAIL_FROM, UNCERTAIN_FROM = 0.6, 0.4  # score reguły -> werdykt

# Wynik bieżącej wersji treści (najnowszy); dokumenty jeszcze nieocenione nie wchodzą.
SELECT = """
    SELECT d.id, d.module, d.source_key, d.source_url, d.text, d.title, d.status, d.platform,
           d.published_at, d.captured_at, d.content_hash, d.ground_truth, d.manipulated, d.observation_id,
           o.advertiser_handle, o.advertiser_name, o.advertiser_url, o.advertised_firm, r.score, r.details,
           (SELECT coalesce(jsonb_agg(jsonb_build_object('variant', i.variant, 'focus', i.focus)
                                      ORDER BY i.variant, i.focus), '[]')
            FROM document_images i WHERE i.document_id = d.id) AS images
    FROM documents d
    JOIN observations o ON o.id = d.observation_id
    JOIN LATERAL (SELECT score, details FROM results WHERE document_id = d.id AND content_hash = d.content_hash
                  ORDER BY created_at DESC LIMIT 1) r ON true
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def _rule_order(rule_id: str) -> tuple[int, str]:
    return int(re.match(r"\d+", rule_id).group()), rule_id  # 2, 3, ..., 12a, 12b, 13, ...


def _verdict(score: float | None) -> str:
    if score is None:
        return "n/a"
    return "fail" if score >= FAIL_FROM else "uncertain" if score >= UNCERTAIN_FROM else "pass"


def to_record(row: dict) -> Record:
    module = MODULE[row["module"]]
    text = row["text"] or ""
    rules = row["details"].get("rules")
    base = f"/api/records/{row['id']}/images"
    images = [
        RecordImage(**i, url=f"{base}/{i['variant']}?focus={i['focus']}") for i in row["images"]
    ]
    return Record(
        id=str(row["id"]),
        module=module,
        detected_at=row["captured_at"].isoformat(),
        published_at=row["published_at"].isoformat() if row["published_at"] else None,
        source=row["platform"],
        platform=row["platform"],
        url=row["source_url"],
        title=row["title"] or ((text[:80] + "…") if len(text) > 80 else text or "(brak tekstu)"),
        content=text,
        risk_score=row["score"],
        status=row["status"],
        entity=Entity(
            name=row["advertiser_name"] or row["advertiser_handle"],
            kind=KIND[module],
            url=row["advertiser_url"] or row["source_url"],
        ),
        advertised_firm=row["advertised_firm"],
        observation_id=str(row["observation_id"]),
        rule_results=None
        if rules is None
        else [
            RuleResult(rule_id=r, verdict=_verdict(s), score=s or 0.0)
            for r, s in sorted(rules.items(), key=lambda kv: _rule_order(kv[0]))
        ],
        images=images,
        manipulated=row["manipulated"] is not None,
        manipulated_rules=(row["manipulated"] or {}).get("rules", []),
        evidence=[
            Evidence(kind="snapshot", label="Archiwum treści", value=row["source_key"]),
            *(
                [Evidence(kind="screenshot", label="Obraz materiału", value=images[0].url)]
                if images
                else []
            ),
            Evidence(kind="hash", label="SHA-256 treści", value=row["content_hash"]),
        ],
        ground_truth=row["ground_truth"],
    )


def list_records(limit: int) -> list[Record]:
    with connect() as c:
        rows = c.execute(
            SELECT + " ORDER BY coalesce(d.published_at, d.captured_at) DESC, d.id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [to_record(r) for r in rows]


def get_record(doc_id: int) -> Record | None:
    with connect() as c:
        row = c.execute(SELECT + " WHERE d.id = %s", (doc_id,)).fetchone()
    return to_record(row) if row else None


def get_record_by_result(result_id: int) -> Record | None:
    with connect() as c:
        row = c.execute(
            SELECT + " WHERE d.id = (SELECT document_id FROM results WHERE id = %s)", (result_id,)
        ).fetchone()
    return to_record(row) if row else None


def set_status(doc_id: int, status: str) -> bool:
    with connect() as c:
        return (
            c.execute("UPDATE documents SET status = %s WHERE id = %s", (status, doc_id)).rowcount
            == 1
        )


def list_model_calls(limit: int) -> list[dict]:
    """Ostatnie wywołania modelu (podgląd/debug): co wysłano, co wróciło, czas, błędy."""
    with connect() as c:
        return c.execute(
            "SELECT c.id, c.created_at, d.source_key, c.module, c.model, c.latency_ms, c.score, "
            "c.error, c.answers, c.state FROM model_calls c LEFT JOIN documents d ON d.id = c.document_id "
            "ORDER BY c.id DESC LIMIT %s",
            (limit,),
        ).fetchall()


def get_image_key(doc_id: int, variant: str, focus: str) -> str | None:
    with connect() as c:
        row = c.execute(
            "SELECT image_key FROM document_images WHERE document_id = %s AND variant = %s AND focus = %s",
            (doc_id, variant, focus),
        ).fetchone()
    return row["image_key"] if row else None


def factor_ids(rec: Record) -> set[str]:
    """Czynniki do oceny: moduł 1 i 3 po jednym, moduł 2 wszystkie reguły rekordu (także te, które model uznał za n/a)."""
    if rec.module == 1:
        return {"is_ad"}
    if rec.module == 3:
        return {"offers_advisory"}
    return {r.rule_id for r in rec.rule_results or []}


def _annotation(row: dict) -> Annotation:
    return Annotation(
        id=row["id"],
        annotator=row["annotator"],
        answers=row["answers"],
        created_at=row["created_at"].isoformat(),
    )


def add_annotation(doc_id: int, annotator: str, answers: dict) -> Annotation:
    with connect() as c:
        row = c.execute(
            "INSERT INTO annotations (document_id, annotator, answers) VALUES (%s, %s, %s) "
            "RETURNING id, annotator, answers, created_at",
            (doc_id, annotator, Jsonb(answers)),
        ).fetchone()
    return _annotation(row)


def list_annotations(doc_id: int, annotator: str | None, limit: int = 50) -> list[Annotation]:
    with connect() as c:
        rows = c.execute(
            "SELECT id, annotator, answers, created_at FROM annotations WHERE document_id = %s "
            "AND (%s::text IS NULL OR annotator = %s) ORDER BY id DESC LIMIT %s",
            (doc_id, annotator, annotator, limit),
        ).fetchall()
    return [_annotation(r) for r in rows]


# Ostatnia ocena każdego oceniającego dla dokumentu (późniejsze zatwierdzenia nadpisują wcześniejsze) + wynik wybranego modelu
LATEST_JUDGMENTS = """
    SELECT l.document_id, d.module, l.annotator, l.answers, r.score, r.details
    FROM (SELECT DISTINCT ON (document_id, annotator) document_id, annotator, answers
          FROM annotations ORDER BY document_id, annotator, id DESC) l
    JOIN documents d ON d.id = l.document_id
    JOIN results r ON r.document_id = l.document_id AND r.model = %s
"""


def judgments_from_rows(rows: list[dict]) -> list[Judgment]:
    """Rozwija oceny do (czynnik, człowiek, model). Moduł 1 i 3: score rekordu; moduł 2: score reguły (None = n/a)."""
    out = []
    for row in rows:
        module = MODULE[row["module"]]
        rules = row["details"].get("rules", {})
        for factor, human in row["answers"].items():
            score = rules.get(factor) if module == 2 else row["score"]
            out.append(
                Judgment(
                    record_id=str(row["document_id"]),
                    module=module,
                    annotator=row["annotator"],
                    factor=factor,
                    human=human,
                    score=score,
                )
            )
    return out


def report(model: str | None) -> ReportResponse:
    """Dane do raportu odchyleń: oceny ręczne vs model (domyślnie model z największą liczbą wyników)."""
    with connect() as c:
        models = c.execute(
            "SELECT model, count(*) AS results FROM results GROUP BY model "
            "ORDER BY results DESC, model"
        ).fetchall()
        model = model or (models[0]["model"] if models else None)
        rows = c.execute(LATEST_JUDGMENTS, (model,)).fetchall() if model else []
    judgments = judgments_from_rows(rows)
    return ReportResponse(
        model=model,
        models=[ModelInfo(**m) for m in models],
        annotators=sorted({j.annotator for j in judgments}),
        judgments=judgments,
    )
