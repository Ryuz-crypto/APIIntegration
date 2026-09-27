from fastapi import Request
from fastapi.responses import JSONResponse
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.db.session import engine
from app.services.auth_service import ROLE_RANK, resolve_session

PUBLIC_PATHS = {
    f"{settings.api_v1_prefix}/health",
    f"{settings.api_v1_prefix}/auth/status",
    f"{settings.api_v1_prefix}/auth/login",
    f"{settings.api_v1_prefix}/auth/bootstrap",
    f"{settings.api_v1_prefix}/docs",
    f"{settings.api_v1_prefix}/openapi.json",
}


def required_role(path: str, method: str) -> str:
    relative = path.removeprefix(settings.api_v1_prefix)
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "viewer"
    if relative.startswith("/auth/"):
        return "viewer"
    if relative.startswith(("/system/", "/compatibility/")):
        return "admin"
    if relative == "/orchestrators" or "/credentials" in relative:
        return "admin"
    if relative.startswith("/try-me/catalog"):
        return "admin"
    if relative == "/try-me/execute":
        return "admin"
    if method == "DELETE" and relative.startswith("/try-me/snapshots"):
        return "admin"
    return "operator"


class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if getattr(request.app.state, "auth_disabled", False):
            return await call_next(request)
        path = request.url.path.rstrip("/") or "/"
        if request.method == "OPTIONS" or not path.startswith(settings.api_v1_prefix) or path in PUBLIC_PATHS:
            return await call_next(request)
        if path == f"{settings.api_v1_prefix}/system/appearance" and request.method == "GET":
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Inicia sesión para continuar."})
        with Session(engine) as session:
            resolved = resolve_session(session, token)
            if not resolved:
                return JSONResponse(status_code=401, content={"detail": "La sesión venció o fue revocada."})
            user, auth_session = resolved
            minimum = required_role(path, request.method)
            if ROLE_RANK.get(user.role, 0) < ROLE_RANK[minimum]:
                return JSONResponse(status_code=403, content={"detail": f"Esta operación requiere el rol {minimum}."})
            request.state.identity = user
            request.state.auth_session = auth_session
            response = await call_next(request)
            return response
