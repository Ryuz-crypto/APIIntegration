from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, select

from app.core.config import settings
from app.db.session import get_session
from app.models.audit import AuditEvent
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    PasswordChange,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services.audit_service import record_event
from app.services.auth_service import AuthService, compare_tokens

router = APIRouter()

PUBLIC_PREFIXES = (
    f"{settings.api_v1_prefix}/auth",
    f"{settings.api_v1_prefix}/health",
    f"{settings.api_v1_prefix}/system/appearance",
    f"{settings.api_v1_prefix}/system/overview",
)


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def resolve_identity(request: Request, session: Session) -> dict | None:
    token = bearer_token(request)
    if not token:
        return None
    return AuthService(session).identity(token)


def require_identity(request: Request, session: Session = Depends(get_session)) -> dict:
    identity = resolve_identity(request, session)
    if not identity:
        raise HTTPException(401, "Sesión inválida o expirada.")
    return identity


def require_role(minimum: str):
    def dependency(request: Request, session: Session = Depends(get_session)) -> dict:
        identity = resolve_identity(request, session)
        if not identity:
            raise HTTPException(401, "Sesión inválida o expirada.")
        if not AuthService.allowed(identity, minimum):
            raise HTTPException(403, f"Esta operación requiere rol {minimum}.")
        return identity

    return dependency


def audit(session: Session, identity: dict | None, action: str, resource_id: str | None = None) -> None:
    record_event(
        session,
        action=action,
        resource_type="auth",
        resource_id=resource_id,
        actor=(identity or {}).get("username", "system"),
        details={"role": (identity or {}).get("role", "system")},
    )
    session.commit()


@router.get("/status")
def auth_status(session: Session = Depends(get_session)) -> dict:
    service = AuthService(session)
    has_users = service.has_users()
    return {
        "users_configured": has_users,
        "session_minutes": AuthService.session_minutes(),
        "login_required": True,
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    service = AuthService(session)
    try:
        result = service.login(payload.username, payload.password)
    except PermissionError as exc:
        audit(session, {"username": payload.username, "role": "unknown"}, "auth.login_failed")
        raise HTTPException(401, str(exc)) from None
    audit(session, result["user"], "auth.login", result["user"]["id"])
    return LoginResponse(
        token=result["token"],
        expires_at=result["expires_at"],
        user=UserRead(**result["user"]),
    )


@router.post("/logout")
def logout(request: Request, session: Session = Depends(get_session)) -> dict:
    identity = resolve_identity(request, session)
    if not identity:
        raise HTTPException(401, "Sesión inválida o expirada.")
    AuthService(session).logout(bearer_token(request))
    audit(session, identity, "auth.logout", identity["id"])
    return {"ok": True}


@router.get("/me")
def me(request: Request, session: Session = Depends(get_session)) -> dict:
    identity = resolve_identity(request, session)
    if not identity:
        raise HTTPException(401, "Sesión inválida o expirada.")
    return identity


@router.get("/users", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("admin")),
) -> list[UserRead]:
    return [UserRead(**user) for user in AuthService(session).list_users()]


@router.post("/bootstrap", response_model=UserRead, status_code=201)
def bootstrap_admin(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    x_tls_admin_token: str = Header(default=""),
) -> UserRead:
    if payload.role != "admin":
        raise HTTPException(400, "El primer usuario debe tener rol admin.")
    service = AuthService(session)
    if service.has_users():
        raise HTTPException(409, "Ya existe un usuario administrador. Inicia sesión para gestionar accesos.")
    if not settings.tls_admin_token or not compare_tokens(x_tls_admin_token, settings.tls_admin_token):
        raise HTTPException(403, "Clave de administración incorrecta.")
    user = service.create_user(payload)
    audit(session, user, "user.bootstrap", user["id"])
    return UserRead(**user)


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("admin")),
) -> UserRead:
    service = AuthService(session)
    try:
        user = service.create_user(payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    audit(session, identity, "user.create", user["id"])
    return UserRead(**user)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("admin")),
) -> UserRead:
    service = AuthService(session)
    users = {user["id"]: user for user in service.list_users()}
    current = users.get(user_id)
    if current is None:
        raise HTTPException(404, "Usuario no encontrado.")
    removes_admin = current["role"] == "admin" and (
        payload.enabled is False or (payload.role is not None and payload.role != "admin")
    )
    if removes_admin and service.active_admins() <= 1:
        raise HTTPException(409, "No se puede retirar el último administrador habilitado.")
    try:
        user = service.update_user(user_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    audit(session, identity, "user.update", user["id"])
    return UserRead(**user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("admin")),
) -> dict:
    service = AuthService(session)
    users = {user["id"]: user for user in service.list_users()}
    target = users.get(user_id)
    if target is None:
        raise HTTPException(404, "Usuario no encontrado.")
    if target["role"] == "admin" and target["enabled"] and service.active_admins() <= 1:
        raise HTTPException(409, "No se puede eliminar el último administrador habilitado.")
    try:
        service.delete_user(user_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    audit(session, identity, "user.delete", user_id)
    return {"ok": True}


@router.get("/audit")
def audit_events(
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("admin")),
) -> list[dict]:
    events = session.exec(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": str(event.id),
            "actor": event.actor,
            "role": event.details.get("role", "system"),
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.post("/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    session: Session = Depends(get_session),
    identity: dict = Depends(require_role("viewer")),
) -> dict:
    service = AuthService(session)
    try:
        service.change_password(identity["id"], payload.current_password, payload.new_password)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    audit(session, identity, "user.password_rotate", identity["id"])
    return {"ok": True}
