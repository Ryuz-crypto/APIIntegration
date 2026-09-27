import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet

from app.core.config import settings


def mask_secret(value: str | None, visible: int = 4) -> str | None:
    if value is None:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * 8}"


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def hash_password(password: str) -> str:
    """Hash a local account password with the stdlib scrypt KDF."""
    if len(password) < 12:
        raise ValueError("La contraseña debe contener al menos 12 caracteres.")
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt$16384$8$1${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt64, digest64 = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt64.encode())
        expected = base64.urlsafe_b64decode(digest64.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
