"""Alerty wysokiego ryzyka: Postgres NOTIFY high_risk (od orkiestratora) -> WebSocket do dashboardu."""

import asyncio
import logging
import os

import psycopg
from fastapi import WebSocket

from app import records

log = logging.getLogger("alerts")
clients: set[WebSocket] = set()


async def broadcast(result_id: int) -> None:
    rec = await asyncio.to_thread(records.get_record_by_result, result_id)
    if rec is None:
        return
    msg = {
        "type": "alert",
        "id": f"alert-{result_id}",
        "at": rec.detected_at,
        "record": rec.model_dump(mode="json"),
    }
    for ws in list(clients):
        try:
            await ws.send_json(msg)
        except Exception:  # noqa: BLE001  # rozłączony klient
            clients.discard(ws)


async def listen() -> None:
    """Stałe LISTEN z automatycznym ponowieniem po utracie połączenia."""
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                os.environ["DATABASE_URL"], autocommit=True
            ) as conn:
                await conn.execute("LISTEN high_risk")
                async for note in conn.notifies():
                    await broadcast(int(note.payload))
        except Exception:
            log.exception("LISTEN przerwany, ponawiam za 2 s")
            await asyncio.sleep(2)
