from __future__ import annotations

import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import scrypt, sha256
from hmac import compare_digest


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${urlsafe_b64encode(salt).decode()}${urlsafe_b64encode(digest).decode()}"


def password_valid(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = scrypt(
            password.encode(),
            salt=urlsafe_b64decode(salt.encode()),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return compare_digest(urlsafe_b64encode(digest).decode(), expected)
    except (TypeError, ValueError):
        return False


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(48)
