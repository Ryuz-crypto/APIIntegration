"""Multi-user accounts for the ec-mcp admin web panel.

Users live in a JSON file (``EC_ADMIN_USERS_FILE``, default
``.ec-admin-users.json``, permissions 0600)::

    {"users": {"alice": {"password_hash": "sha256:<hex>", "role": "admin"}}}

Roles (ascending privilege): ``viewer`` (read-only), ``operator`` (configure,
apply, probe, restart) and ``admin`` (everything, including user management).

If the file does not exist or has no users, the panel falls back to the
legacy single ``EC_ADMIN_PASSWORD`` with full admin rights, preserving
backwards compatibility. Password hashes are never returned by the API.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

ROLES = ("viewer", "operator", "admin")
ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3}

_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class UserError(ValueError):
    pass


def users_path() -> Path:
    return Path(os.environ.get("EC_ADMIN_USERS_FILE") or Path.cwd() / ".ec-admin-users.json")


PBKDF2_ITERATIONS = 600_000
MAX_PASSWORD_LENGTH = 1024


def hash_password(password: str) -> str:
    if not password or len(password) > MAX_PASSWORD_LENGTH:
        raise UserError("La contraseña debe tener entre 1 y 1024 caracteres")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256:{PBKDF2_ITERATIONS}:{salt}:{digest.hex()}"


def verify_password_hash(password: str, expected: str) -> bool:
    if not password or len(password) > MAX_PASSWORD_LENGTH:
        return False
    if expected.startswith("sha256:"):
        candidate = "sha256:" + hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, candidate)
    try:
        algorithm, count, salt, digest = expected.split(":")
        iterations = int(count)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return False
        salt_bytes = bytes.fromhex(salt)
        if len(salt_bytes) != 16 or len(digest) != 64:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations).hex()
        return hmac.compare_digest(digest, candidate)
    except (TypeError, ValueError):
        return False


def load_users() -> dict[str, dict[str, Any]]:
    path = users_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    users = data.get("users") if isinstance(data, dict) else None
    return users if isinstance(users, dict) else {}


def _save_users(users: dict[str, dict[str, Any]]) -> None:
    path = users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"users": users}, indent=2), encoding="utf-8")
    path.chmod(0o600)


def public_users() -> list[dict[str, str]]:
    return [
        {"username": name, "role": str(info.get("role", "viewer"))}
        for name, info in sorted(load_users().items())
    ]


def validate_username(username: str) -> str:
    username = username.strip()
    if not _USERNAME.fullmatch(username):
        raise UserError("El usuario debe tener 1-64 caracteres [A-Za-z0-9_.-]")
    return username


def validate_role(role: str) -> str:
    role = str(role or "").strip().lower()
    if role not in ROLES:
        raise UserError(f"Rol inválido; usa uno de: {', '.join(ROLES)}")
    return role


def verify_user(username: str, password: str) -> str | None:
    """Return the role when username+password are valid, else None."""
    users = load_users()
    if not users:
        return None
    info = users.get(username.strip())
    if not isinstance(info, dict):
        return None
    expected = str(info.get("password_hash") or "")
    if not expected:
        return None
    if verify_password_hash(password, expected):
        # Existing SHA-256 records remain usable; changing the password upgrades them.
        return validate_role(str(info.get("role", "viewer")))
    return None


def upsert_user(username: str, password: str, role: str) -> dict[str, str]:
    username = validate_username(username)
    role = validate_role(role)
    if not password:
        raise UserError("La contraseña no puede estar vacía")
    users = load_users()
    users[username] = {"password_hash": hash_password(password), "role": role}
    _save_users(users)
    return {"username": username, "role": role}


def delete_user(username: str) -> bool:
    users = load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False


def set_password(username: str, new_password: str) -> None:
    if not new_password:
        raise UserError("La contraseña no puede estar vacía")
    users = load_users()
    if username not in users:
        raise UserError(f"No existe el usuario '{username}'")
    users[username]["password_hash"] = hash_password(new_password)
    _save_users(users)


def has_users() -> bool:
    return bool(load_users())
