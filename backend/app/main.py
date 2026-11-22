import asyncio
import mimetypes
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Path, Query, Response, WebSocket, WebSocketDisconnect

from app import alerts, records, refresh, storage
from app.schemas import (
    Annotation,
    AnnotationIn,
    Record,
    RecordsResponse,
    RefreshRun,
    ReportResponse,
    StatusUpdate,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(alerts.listen())
    yield
    task.cancel()


app = FastAPI(title="InvestWatch Backend", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/records")
def list_records(limit: int = Query(1000, ge=1, le=5000)) -> RecordsResponse:
    items = records.list_records(limit)
    return RecordsResponse(items=items, total=len(items))


@app.get("/api/report")
def report(model: str | None = Query(None, max_length=100)) -> ReportResponse:
    return records.report(model)


@app.get("/api/model-calls")
def model_calls(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return records.list_model_calls(limit)


IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@app.get("/api/records/{doc_id}/images/{variant}")
def record_image(
    doc_id: int,
    variant: Literal["desktop", "mobile", "tablet", "original"],
    focus: Literal["page", "risk"] = "page",
) -> Response:
    """Podgląd obrazu rekordu (klucz ze storage bierzemy z bazy po id, więc klient nie wskazuje ścieżek)."""
    key = records.get_image_key(doc_id, variant, focus)
    content_type = mimetypes.guess_type(key or "")[0]
    if not key or content_type not in IMAGE_TYPES:
        raise HTTPException(404, "Not found")
    try:
        data = storage.get(key)
    except ClientError:
        raise HTTPException(404, "Not found") from None
    return Response(
        data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@app.post("/api/refresh", status_code=202)
def start_refresh() -> RefreshRun:
    """Przycisk "Odśwież dane": uruchamia przetwarzanie w Dagsterze (jeden run naraz)."""
    try:
        return RefreshRun(**refresh.start())
    except refresh.DagsterError as e:
        raise HTTPException(502, str(e)) from None


@app.get("/api/refresh/{run_id}")
def refresh_status(run_id: Annotated[str, Path(pattern=r"^[0-9a-f-]{8,64}$")]) -> RefreshRun:
    try:
        run = refresh.status(run_id)
    except refresh.DagsterError as e:
        raise HTTPException(502, str(e)) from None
    if run is None:
        raise HTTPException(404, "Not found")
    return RefreshRun(**run)


@app.get("/api/records/{doc_id}/annotations")
def list_annotations(
    doc_id: int, annotator: str | None = Query(None, max_length=64)
) -> list[Annotation]:
    return records.list_annotations(doc_id, annotator)


@app.post("/api/records/{doc_id}/annotations", status_code=201)
def add_annotation(doc_id: int, body: AnnotationIn) -> Annotation:
    """Zatwierdzenie oceny: kompletny zestaw czynników rekordu (0/1/null), zawsze jako nowy wpis."""
    rec = records.get_record(doc_id)
    if rec is None:
        raise HTTPException(404, "Not found")
    if set(body.answers) != records.factor_ids(rec):
        raise HTTPException(422, "answers musi zawierać dokładnie czynniki tego rekordu")
    return records.add_annotation(doc_id, body.annotator, body.answers)


@app.patch("/api/records/{doc_id}/status")
def update_status(doc_id: int, body: StatusUpdate) -> Record:
    if not records.set_status(doc_id, body.status) or (rec := records.get_record(doc_id)) is None:
        raise HTTPException(404, "Not found")
    return rec


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await ws.accept()
    alerts.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # klient nic nie wysyła; czekamy na rozłączenie
    except WebSocketDisconnect:
        pass
    finally:
        alerts.clients.discard(ws)
