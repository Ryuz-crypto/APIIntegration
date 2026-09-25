"""Short-lived encrypted MFA state shared by all API workers; OTPs are never stored."""

import hashlib
import json
import secrets

import httpx
from redis import Redis, RedisError

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret

CHALLENGE_TTL = 300
SESSION_TTL = 1800


class InteractiveAuthError(ValueError):
    pass


def store():
    return Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
    )


def binding(orchestrator):
    values = [
        str(orchestrator.id),
        orchestrator.base_url,
        orchestrator.username,
        orchestrator.encrypted_password,
        orchestrator.auth_type,
        orchestrator.login_type,
        orchestrator.verify_tls,
    ]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def cookie_state(client):
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires,
        }
        for c in client.cookies.jar
    ]


def restore_cookies(client, state):
    from http.cookiejar import Cookie

    for c in state:
        client.cookies.jar.set_cookie(
            Cookie(
                version=0,
                name=c["name"],
                value=c["value"],
                port=None,
                port_specified=False,
                domain=c["domain"],
                domain_specified=bool(c["domain"]),
                domain_initial_dot=c["domain"].startswith("."),
                path=c["path"],
                path_specified=True,
                secure=c["secure"],
                expires=c["expires"],
                discard=c["expires"] is None,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )


def save(key, orchestrator, client, ttl):
    data = {"binding": binding(orchestrator), "cookies": cookie_state(client)}
    try:
        store().setex(key, ttl, encrypt_secret(json.dumps(data)))
    except RedisError:
        raise InteractiveAuthError(
            "Redis no está disponible para mantener la sesión MFA."
        ) from None


def load(key, orchestrator, consume=False):
    try:
        cache = store()
        encrypted = cache.getdel(key) if consume else cache.get(key)
    except RedisError:
        raise InteractiveAuthError(
            "Redis no está disponible para mantener la sesión MFA."
        ) from None
    if not encrypted:
        raise InteractiveAuthError(
            "La sesión o la espera del OTP expiró. Inicia la autenticación de nuevo."
        )
    data = json.loads(decrypt_secret(encrypted))
    if data["binding"] != binding(orchestrator):
        raise InteractiveAuthError(
            "La conexión o sus credenciales cambiaron. Inicia la autenticación de nuevo."
        )
    return data["cookies"]


def active_key(orchestrator):
    return f"dashboardapi:mfa:session:{orchestrator.id}"


def challenge_key(orchestrator, challenge):
    return f"dashboardapi:mfa:challenge:{orchestrator.id}:{challenge}"


def invalidate(orchestrator):
    try:
        store().delete(active_key(orchestrator))
    except RedisError:
        raise InteractiveAuthError("No fue posible cerrar la sesión MFA en Redis.") from None


def start(orchestrator, engine):
    from app.services.edgeconnect_client import EdgeConnectClient

    api = EdgeConnectClient(orchestrator, engine)
    # Fail before sending credentials when shared state cannot be maintained.
    invalidate(orchestrator)
    with httpx.Client(
        verify=orchestrator.verify_tls, timeout=orchestrator.timeout_seconds, follow_redirects=False
    ) as client:
        api.request_otp(client)
        challenge = secrets.token_urlsafe(32)
        save(challenge_key(orchestrator, challenge), orchestrator, client, CHALLENGE_TTL)
    return {
        "status": "otp_required",
        "challenge_id": challenge,
        "expires_in": CHALLENGE_TTL,
        "message": "Usuario y contraseña enviados. Introduce ahora el OTP vigente de tu aplicación.",
    }


def complete(orchestrator, engine, challenge, otp):
    from app.services.edgeconnect_client import EdgeConnectClient

    cookies = load(challenge_key(orchestrator, challenge), orchestrator, consume=True)
    api = EdgeConnectClient(orchestrator, engine, otp=otp)
    with httpx.Client(
        verify=orchestrator.verify_tls, timeout=orchestrator.timeout_seconds, follow_redirects=False
    ) as client:
        restore_cookies(client, cookies)
        api._login(client, {})
        save(active_key(orchestrator), orchestrator, client, SESSION_TTL)


def cancel(orchestrator, challenge):
    try:
        store().delete(challenge_key(orchestrator, challenge))
    except RedisError:
        raise InteractiveAuthError("No fue posible cancelar la espera en Redis.") from None
