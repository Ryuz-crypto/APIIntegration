import json
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.schemas.system import SystemOverview
from app.services.system_service import get_system_overview
from app.services.tls_service import MAX_UPLOAD, normalize

router = APIRouter()


def tls_authorized(request: Request, x_tls_admin_token: str = Header(default="")):
    if not settings.tls_enabled:
        raise HTTPException(503, "HTTPS administrado requiere la instalación nativa Ubuntu actualizada.")
    if not settings.tls_admin_token or not secrets.compare_digest(x_tls_admin_token, settings.tls_admin_token):
        raise HTTPException(403, "Clave de administración incorrecta.")
    # Uvicorn trusts forwarded headers only from the local Nginx proxy.
    if request.url.scheme != "https" and (
        not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
    ):
        raise HTTPException(400, "Utiliza HTTPS o el túnel SSH local para cargar el certificado.")


@router.get("/tls", dependencies=[Depends(tls_authorized)])
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


@router.post("/tls", status_code=202, dependencies=[Depends(tls_authorized)])
async def upload_tls(hostname: str = Form(...), certificate: UploadFile = File(...),
                     key: UploadFile | None = File(None), password: str = Form("")):
    try:
        material = normalize(await certificate.read(MAX_UPLOAD + 1),
                             await key.read(MAX_UPLOAD + 1) if key else b"", password, hostname)
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
        raise HTTPException(409, "Hay una solicitud pendiente; espera antes de volver a cargar.") from None
    finally:
        temporary.unlink(missing_ok=True)
    return {"state": "pending", "message": "Validado. Ubuntu aplicará HTTPS en unos segundos."}


@router.get("/overview", response_model=SystemOverview)
def overview(session: Session = Depends(get_session)) -> SystemOverview:
    return get_system_overview(session)
