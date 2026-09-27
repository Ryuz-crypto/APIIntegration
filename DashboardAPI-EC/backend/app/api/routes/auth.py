import hmac
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.session import get_session
from app.models.audit import AuditEvent
from app.models.user import UserAccount
from app.schemas.auth import (
    AuditRead,
    AuthStatus,
    BootstrapRequest,
    LoginRequest,
    PasswordChange,
    SessionRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services.audit_service import record_event
from app.services.auth_service import (
    authenticate,
    create_session,
    create_user,
    enabled_admin_count,
    require_role,
    revoke_user_sessions,
)

router = APIRouter()


def _identity(request: Request) -> UserAccount:
    user = getattr(request.state, "identity", None)
    if not user:
        raise HTTPException(status_code=401, detail="Sesión requerida.")
    return user


def _admin(request: Request) -> UserAccount:
    user = _identity(request)
    require_role(user, "admin")
    return user


def _read(user: UserAccount) -> UserRead:
    return UserRead.model_validate(user, from_attributes=True)


@router.get("/status", response_model=AuthStatus)
def auth_status(session: Session = Depends(get_session)) -> AuthStatus:
    return AuthStatus(users_configured=session.exec(select(UserAccount.id)).first() is not None, version=settings.app_version)


@router.post("/bootstrap", response_model=SessionRead, status_code=201)
def bootstrap(payload: BootstrapRequest, request: Request, session: Session = Depends(get_session)) -> SessionRead:
    if session.exec(select(UserAccount.id)).first() is not None:
        raise HTTPException(status_code=409, detail="El administrador inicial ya fue creado.")
    if not settings.tls_admin_token or not hmac.compare_digest(payload.admin_token, settings.tls_admin_token):
        raise HTTPException(status_code=403, detail="Token administrativo no válido.")
    user = create_user(session, payload.username, payload.password, payload.display_name, "admin")
    token, auth_session = create_session(session, user)
    record_event(session, "auth.bootstrap", "user", str(user.id), {"role": "admin"}, actor=user.username)
    session.commit()
    return SessionRead(token=token, expires_at=auth_session.expires_at, user=_read(user))


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)) -> SessionRead:
    user = authenticate(session, payload.username, payload.password)
    if not user:
        record_event(session, "auth.login_failed", "session", details={"username": payload.username.strip().lower()})
        session.commit()
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    token, auth_session = create_session(session, user)
    record_event(session, "auth.login", "session", str(auth_session.id), actor=user.username)
    session.commit()
    return SessionRead(token=token, expires_at=auth_session.expires_at, user=_read(user))


@router.get("/me", response_model=UserRead)
def me(user: UserAccount = Depends(_identity)) -> UserRead:
    return _read(user)


@router.post("/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_session)) -> Response:
    user = _identity(request)
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session:
        auth_session.revoked_at = datetime.now(UTC)
        session.add(auth_session)
    record_event(session, "auth.logout", "session", str(auth_session.id) if auth_session else None, actor=user.username)
    session.commit()
    return Response(status_code=204)


@router.get("/users", response_model=list[UserRead])
def list_users(_: UserAccount = Depends(_admin), session: Session = Depends(get_session)) -> list[UserRead]:
    return [_read(item) for item in session.exec(select(UserAccount).order_by(UserAccount.username)).all()]


@router.post("/users", response_model=UserRead, status_code=201)
def add_user(payload: UserCreate, admin: UserAccount = Depends(_admin), session: Session = Depends(get_session)) -> UserRead:
    user = create_user(session, payload.username, payload.password, payload.display_name, payload.role)
    record_event(session, "user.create", "user", str(user.id), {"role": user.role}, actor=admin.username)
    session.commit()
    session.refresh(user)
    return _read(user)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: uuid.UUID, payload: UserUpdate, admin: UserAccount = Depends(_admin), session: Session = Depends(get_session)) -> UserRead:
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    next_role = payload.role if payload.role is not None else user.role
    next_enabled = payload.enabled if payload.enabled is not None else user.enabled
    if user.role == "admin" and user.enabled and (next_role != "admin" or not next_enabled) and enabled_admin_count(session) <= 1:
        raise HTTPException(status_code=409, detail="No se puede deshabilitar o degradar al último administrador.")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    user.role = next_role
    user.enabled = next_enabled
    user.updated_at = datetime.now(UTC)
    if not user.enabled:
        revoke_user_sessions(session, user.id)
    session.add(user)
    record_event(session, "user.update", "user", str(user.id), {"role": user.role, "enabled": user.enabled}, actor=admin.username)
    session.commit()
    session.refresh(user)
    return _read(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, request: Request, admin: UserAccount = Depends(_admin), session: Session = Depends(get_session)) -> Response:
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == admin.id:
        raise HTTPException(status_code=409, detail="No puedes eliminar tu propia cuenta.")
    if user.role == "admin" and user.enabled and enabled_admin_count(session) <= 1:
        raise HTTPException(status_code=409, detail="No se puede eliminar al último administrador.")
    record_event(session, "user.delete", "user", str(user.id), {"username": user.username}, actor=admin.username)
    session.delete(user)
    session.commit()
    return Response(status_code=204)


@router.post("/password", status_code=204)
def change_password(payload: PasswordChange, request: Request, session: Session = Depends(get_session)) -> Response:
    user = _identity(request)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="La contraseña actual no es correcta.")
    try:
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.updated_at = datetime.now(UTC)
    current_session = getattr(request.state, "auth_session", None)
    revoke_user_sessions(session, user.id, current_session.id if current_session else None)
    session.add(user)
    record_event(session, "user.password_change", "user", str(user.id), actor=user.username)
    session.commit()
    return Response(status_code=204)


@router.get("/audit", response_model=list[AuditRead])
def audit_log(_: UserAccount = Depends(_admin), session: Session = Depends(get_session)) -> list[AuditRead]:
    events = session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [AuditRead.model_validate(item, from_attributes=True) for item in events]
