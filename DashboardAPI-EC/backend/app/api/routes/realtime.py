import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.services.auth_service import resolve_session
from app.services.dashboard_service import compose_dashboard

router = APIRouter()


def _token(websocket: WebSocket) -> str:
    protocols = [
        value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",")
    ]
    return protocols[1] if len(protocols) == 2 and protocols[0] == "dashboardapi" else ""


@router.websocket("/dashboard/{orchestrator_id}")
async def dashboard_stream(
    websocket: WebSocket,
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    if not _token(websocket) or resolve_session(session, _token(websocket)) is None:
        await websocket.close(code=4401, reason="Sesión inválida")
        return
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        await websocket.close(code=4404, reason="Orchestrator no encontrado")
        return
    await websocket.accept(subprotocol="dashboardapi")
    previous = ""
    sequence = 0
    heartbeat = datetime.now(UTC)
    try:
        while True:
            session.expire_all()
            orchestrator = session.get(Orchestrator, orchestrator_id)
            if orchestrator is None:
                await websocket.close(code=4404)
                return
            dashboard = compose_dashboard(session, orchestrator)
            serialized = dashboard.model_dump_json(exclude={"generated_at"})
            now = datetime.now(UTC)
            if serialized != previous:
                sequence += 1
                await websocket.send_json(
                    {
                        "type": "dashboard.snapshot",
                        "sequence": sequence,
                        "sent_at": now.isoformat(),
                        "data": dashboard.model_dump(mode="json"),
                    }
                )
                previous = serialized
                heartbeat = now
            elif (now - heartbeat).total_seconds() >= 15:
                await websocket.send_json({"type": "heartbeat", "sent_at": now.isoformat()})
                heartbeat = now
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
