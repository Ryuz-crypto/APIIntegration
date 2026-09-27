import json
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.models.system_setting import SystemSetting
from app.schemas.system import AppearanceSettings, SystemOverview, UpdateRequest
from app.services.audit_service import record_event
from app.services.system_service import get_system_overview
from app.services.tls_service import MAX_UPLOAD, normalize
from app.services.update_service import queue_update, release_status, update_status

router = APIRouter()
APPEARANCE_KEY = "appearance"


def tls_available():
    if not settings.tls_enabled:
        raise HTTPException(
            503, "HTTPS administrado requiere la instalación nativa Ubuntu actualizada."
        )


def update_available():
    if not settings.update_enabled:
        raise HTTPException(
            503, "Actualización administrada requiere DashboardAPI-EC 1.2 o posterior en Ubuntu."
        )


@router.get("/tls", dependencies=[Depends(tls_available)])
def tls_status():
    directory = Path(settings.tls_state_dir)
    result = {"state": "http"}
    try:
        result = json.loads((directory / "status.json").read_text())
    except FileNotFoundError:
        pass
    if (directory / "request.json").exists():
        result["state"] = "pending"
    return result


@router.post("/tls", status_code=202, dependencies=[Depends(tls_available)])
async def upload_tls(
    hostname: str = Form(...),
    certificate: UploadFile = File(...),
    key: UploadFile | None = File(None),
    password: str = Form(""),
):
    try:
        material = normalize(
            await certificate.read(MAX_UPLOAD + 1),
            await key.read(MAX_UPLOAD + 1) if key else b"",
            password,
            hostname,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    directory = Path(settings.tls_state_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = directory / f"upload-{secrets.token_hex(16)}"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(material, stream)
        # Atomic publication without overwriting a pending request.
        os.link(temporary, directory / "request.json")
    except FileExistsError:
        raise HTTPException(
            409, "Hay una solicitud pendiente; espera antes de volver a cargar."
        ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return {"state": "pending", "message": "Validado. Ubuntu aplicará HTTPS en unos segundos."}


@router.get("/overview", response_model=SystemOverview)
def overview(session: Session = Depends(get_session)) -> SystemOverview:
    return get_system_overview(session)


@router.get("/appearance", response_model=AppearanceSettings)
def appearance(session: Session = Depends(get_session)) -> AppearanceSettings:
    item = session.get(SystemSetting, APPEARANCE_KEY)
    return AppearanceSettings.model_validate(item.value if item else {})


@router.put("/appearance", response_model=AppearanceSettings)
def update_appearance(
    payload: AppearanceSettings,
    session: Session = Depends(get_session),
) -> AppearanceSettings:
    item = session.get(SystemSetting, APPEARANCE_KEY) or SystemSetting(key=APPEARANCE_KEY)
    item.value = payload.model_dump()
    session.add(item)
    session.commit()
    return payload


@router.get("/releases", dependencies=[Depends(update_available)])
def releases():
    return release_status()


@router.get("/update", dependencies=[Depends(update_available)])
def get_update_status():
    return update_status()


@router.post("/update", status_code=202, dependencies=[Depends(update_available)])
def apply_update(payload: UpdateRequest, session: Session = Depends(get_session)):
    if payload.confirmation != f"ACTUALIZAR {payload.version}":
        raise HTTPException(409, "Escribe la confirmación exacta mostrada en el panel.")
    try:
        result = queue_update(payload.version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    record_event(
        session,
        "system.update_queued",
        "system",
        payload.version,
        {"version": payload.version},
    )
    session.commit()
    return result
