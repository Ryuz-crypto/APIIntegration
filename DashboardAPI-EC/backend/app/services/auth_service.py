from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.core.config import settings
from app.core.passwords import new_session_token, password_hash, password_valid, token_hash
from app.models.user import User, UserSession

ROLE_RANKING = {"viewer": 1, "operator": 2, "admin": 3}


def _as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def role_allowed(role: str | None, minimum: str) -> bool:
    return ROLE_RANKING.get(str(role), 0) >= ROLE_RANKING[minimum]


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def has_users(self) -> bool:
        return self.session.exec(select(User).limit(1)).first() is not None

    def public_user(self, user: User) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "enabled": user.enabled,
            "created_at": _ensure_utc(user.created_at),
            "updated_at": _ensure_utc(user.updated_at),
            "last_login_at": _ensure_utc(user.last_login_at) if user.last_login_at else None,
        }

    def login(self, username: str, password: str) -> dict:
        user = self.session.exec(select(User).where(User.username == username)).first()
        if not user or not user.enabled or not password_valid(password, user.password_hash):
            raise PermissionError("Usuario o contraseña incorrectos.")
        token = new_session_token()
        expires = datetime.now(UTC) + timedelta(minutes=self.session_minutes())
        self.session.add(
            UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires)
        )
        user.last_login_at = datetime.now(UTC)
        self.session.add(user)
        self.session.commit()
        return {"token": token, "expires_at": expires, "user": self.public_user(user)}

    @staticmethod
    def session_minutes() -> int:
        return max(15, min(settings.access_token_expire_minutes, 7 * 24 * 60))

    def identity(self, token: str | None) -> dict | None:
        if not token:
            return None
        now = datetime.now(UTC)
        record = self.session.exec(
            select(UserSession).where(UserSession.token_hash == token_hash(token))
        ).first()
        if not record or _ensure_utc(record.expires_at) < now:
            if record:
                self.session.delete(record)
                self.session.commit()
            return None
        user = self.session.get(User, record.user_id)
        if not user or not user.enabled:
            return None
        record.last_seen_at = now
        self.session.add(record)
        self.session.commit()
        return {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "enabled": user.enabled,
            "expires_at": _ensure_utc(record.expires_at),
        }

    def logout(self, token: str | None) -> None:
        if not token:
            return
        record = self.session.exec(
            select(UserSession).where(UserSession.token_hash == token_hash(token))
        ).first()
        if record:
            self.session.delete(record)
            self.session.commit()

    def create_user(self, payload) -> dict:
        exists = self.session.exec(
            select(User).where(User.username == payload.username)
        ).first()
        if exists:
            raise ValueError("El nombre de usuario ya está en uso.")
        user = User(
            username=payload.username,
            full_name=payload.full_name,
            password_hash=password_hash(payload.password),
            role=payload.role,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self.public_user(user)

    def update_user(self, user_id: str, payload) -> dict:
        user = self.session.get(User, _as_uuid(user_id))
        if not user:
            raise LookupError("Usuario no encontrado.")
        if payload.role is not None:
            user.role = payload.role
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.enabled is not None:
            user.enabled = payload.enabled
        if payload.password:
            user.password_hash = password_hash(payload.password)
            self.revoke_user_sessions(user.id)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self.public_user(user)

    def delete_user(self, user_id: str) -> None:
        user = self.session.get(User, _as_uuid(user_id))
        if not user:
            raise LookupError("Usuario no encontrado.")
        for record in self.session.exec(
            select(UserSession).where(UserSession.user_id == user.id)
        ).all():
            self.session.delete(record)
        self.session.delete(user)
        self.session.commit()

    def list_users(self) -> list[dict]:
        return [self.public_user(user) for user in self.session.exec(select(User)).all()]

    def active_admins(self) -> int:
        return len(
            self.session.exec(
                select(User).where(User.role == "admin", User.enabled)  # type: ignore[arg-type]
            ).all()
        )

    def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user = self.session.get(User, _as_uuid(user_id))
        if not user or not password_valid(current_password, user.password_hash):
            raise PermissionError("La contraseña actual no es correcta.")
        user.password_hash = password_hash(new_password)
        self.session.add(user)
        self.session.commit()
        self.revoke_user_sessions(user.id)

    def revoke_user_sessions(self, user_id) -> None:
        for record in self.session.exec(
            select(UserSession).where(UserSession.user_id == user_id)
        ).all():
            self.session.delete(record)
        self.session.commit()

    @staticmethod
    def allowed(identity: dict, minimum: str) -> bool:
        return role_allowed(identity.get("role"), minimum)


def compare_tokens(supplied: str, expected: str) -> bool:
    return bool(supplied) and secrets.compare_digest(supplied.encode(), expected.encode())
