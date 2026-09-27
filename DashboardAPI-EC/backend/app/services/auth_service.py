import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_password, hash_session_token, verify_password
from app.models.user import UserAccount, UserSession

ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3}


def normalized_username(value: str) -> str:
    username = value.strip().lower()
    if not username or any(character.isspace() for character in username):
        raise HTTPException(status_code=422, detail="El usuario es obligatorio y no puede contener espacios.")
    return username


def create_user(session: Session, username: str, password: str, display_name: str, role: str) -> UserAccount:
    username = normalized_username(username)
    if role not in ROLE_RANK:
        raise HTTPException(status_code=422, detail="Rol no válido.")
    if session.exec(select(UserAccount).where(UserAccount.username == username)).first():
        raise HTTPException(status_code=409, detail="El usuario ya existe.")
    try:
        password_digest = hash_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = UserAccount(
        username=username,
        display_name=display_name.strip(),
        password_hash=password_digest,
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def create_session(session: Session, user: UserAccount) -> tuple[str, UserSession]:
    token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    item = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=max(1, min(settings.session_expire_hours, 168))),
    )
    user.last_login_at = now
    user.updated_at = now
    session.add(user)
    session.add(item)
    session.flush()
    return token, item


def authenticate(session: Session, username: str, password: str) -> UserAccount | None:
    username = username.strip().lower()
    user = session.exec(select(UserAccount).where(UserAccount.username == username)).first()
    if not user or not user.enabled or not verify_password(password, user.password_hash):
        return None
    return user


def resolve_session(session: Session, token: str) -> tuple[UserAccount, UserSession] | None:
    item = session.exec(select(UserSession).where(UserSession.token_hash == hash_session_token(token))).first()
    now = datetime.now(UTC)
    if not item or item.revoked_at is not None or _aware(item.expires_at) <= now:
        return None
    user = session.get(UserAccount, item.user_id)
    if not user or not user.enabled:
        return None
    return user, item


def revoke_user_sessions(session: Session, user_id: uuid.UUID, except_id: uuid.UUID | None = None) -> None:
    now = datetime.now(UTC)
    items = session.exec(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))).all()
    for item in items:
        if item.id != except_id:
            item.revoked_at = now
            session.add(item)


def enabled_admin_count(session: Session) -> int:
    return len(session.exec(select(UserAccount).where(UserAccount.role == "admin", UserAccount.enabled == True)).all())


def require_role(user: UserAccount, minimum: str) -> None:
    if ROLE_RANK.get(user.role, 0) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Esta operación requiere el rol {minimum}.")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
