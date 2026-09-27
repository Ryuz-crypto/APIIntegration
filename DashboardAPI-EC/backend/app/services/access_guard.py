from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app.api.routes.auth import PUBLIC_PREFIXES, bearer_token
from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.services.auth_service import AuthService


def has_users(session: Session) -> bool:
    return session.exec(select(User).limit(1)).first() is not None


def is_public(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix.rstrip("/") + "/")
        for prefix in PUBLIC_PREFIXES
    )


async def access_guard(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith(f"{settings.api_v1_prefix}/"):
        return
    if is_public(path):
        return
    if not has_users(session):
        return
    token = bearer_token(request)
    identity = AuthService(session).identity(token) if token else None
    if not identity:
        raise HTTPException(401, "Sesión inválida o expirada. Inicia sesión para continuar.")
    request.state.identity = identity
