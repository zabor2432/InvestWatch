"""Kształt body dla frontendu. Lustro `frontend/src/api/dto.ts` (jedyny kontrakt przewodowy)."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Status = Literal["new", "in_review", "confirmed", "false_positive"]


class Entity(BaseModel):
    name: str
    kind: Literal["investment_firm", "finfluencer", "unauthorized"]
    url: str | None = None


class Evidence(BaseModel):
    kind: Literal["screenshot", "snapshot", "phrase", "hash"]
    label: str
    value: str


class RuleResult(BaseModel):
    rule_id: str
    verdict: Literal["pass", "fail", "uncertain", "n/a"]
    score: float
    note: str | None = None


class RecordImage(BaseModel):
    variant: Literal["desktop", "mobile", "tablet", "original"]
    focus: Literal["page", "risk"]
    url: str


class RefreshRun(BaseModel):
    run_id: str
    status: str
    already_running: bool = False


class Record(BaseModel):
    id: str
    module: Literal[1, 2, 3]
    detected_at: str
    source: str
    url: str
    title: str
    content: str
    risk_score: float
    status: Status
    entity: Entity
    rule_results: list[RuleResult] | None = None
    evidence: list[Evidence] = []
    ground_truth: bool | None = None
    platform: str = ""
    published_at: str | None = None
    advertised_firm: str = ""
    observation_id: str = ""  # ta sama para (podmiot, firma): historia = rekordy o tym id
    images: list[RecordImage] = []
    manipulated: bool = False
    manipulated_rules: list[str] = []  # reguły, które wariant testowy miał celowo złamać


class RecordsResponse(BaseModel):
    items: list[Record]
    total: int


class StatusUpdate(BaseModel):
    status: Status


# 1 = oflagowane (naruszenie / reklama / doradztwo), 0 = zgodne, None = nie dotyczy
Answer = Literal[0, 1] | None
Annotator = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]


class AnnotationIn(BaseModel):
    annotator: Annotator
    answers: dict[str, Answer]


class Annotation(BaseModel):
    id: int
    annotator: str
    answers: dict[str, Answer]
    created_at: str


class Judgment(BaseModel):
    """Jedna ocena człowieka dla czynnika zestawiona z odpowiedzią modelu (score None = model: nie dotyczy)."""

    record_id: str
    module: Literal[1, 2, 3]
    annotator: str
    factor: str
    human: Answer
    score: float | None


class ModelInfo(BaseModel):
    model: str
    results: int


class ReportResponse(BaseModel):
    model: str | None
    models: list[ModelInfo]
    annotators: list[str]
    judgments: list[Judgment]
