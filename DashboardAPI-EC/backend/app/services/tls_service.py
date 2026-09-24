"""Certificate validation shared by the unprivileged API and Ubuntu activator."""
import ipaddress
import re
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

MAX_UPLOAD = 256 * 1024


def normalize(certificate: bytes, key: bytes, password: str, hostname: str) -> dict:
    hostname = hostname.lower().strip()
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
        if len(hostname) > 253 or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", hostname
        ):
            raise ValueError("Introduce un nombre DNS o una dirección IP válida.") from None
    if len(certificate) > MAX_UPLOAD or len(key) > MAX_UPLOAD:
        raise ValueError("Cada archivo debe ocupar como máximo 256 KiB.")
    secret = password.encode() if password else None
    try:
        if not key:
            private, leaf, chain = pkcs12.load_key_and_certificates(certificate, secret)
            if private is None or leaf is None:
                raise ValueError()
            certs = [leaf, *(chain or [])]
        else:
            certs = (x509.load_pem_x509_certificates(certificate)
                     if b"-----BEGIN CERTIFICATE-----" in certificate
                     else [x509.load_der_x509_certificate(certificate)])
            private = (serialization.load_pem_private_key(key, secret)
                       if b"-----BEGIN" in key else serialization.load_der_private_key(key, secret))
        leaf = certs[0]
        def public_bytes(public):
            return public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if public_bytes(private.public_key()) != public_bytes(leaf.public_key()):
            raise ValueError()
    except (ValueError, TypeError, IndexError, UnsupportedAlgorithm):
        raise ValueError("Certificado/clave inválidos, contraseña incorrecta o clave que no corresponde.") from None
    now = datetime.now(UTC)
    for cert in certs:
        if cert.not_valid_before_utc > now or cert.not_valid_after_utc <= now + timedelta(days=1):
            raise ValueError("La cadena debe estar vigente y conservar más de 24 horas de validez.")
    try:
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        if ip:
            matches = ip in san.get_values_for_type(x509.IPAddress)
        else:
            matches = any(
                hostname == name.lower() or (
                    name.startswith("*.") and hostname.count(".") == name.count(".")
                    and hostname.endswith(name[1:].lower())
                ) for name in san.get_values_for_type(x509.DNSName)
            )
        if not matches:
            raise ValueError("El certificado no cubre el nombre DNS/IP indicado en sus SAN.")
    except x509.ExtensionNotFound:
        raise ValueError("El certificado necesita Subject Alternative Name (SAN).") from None
    return {
        "hostname": hostname,
        "expires_at": leaf.not_valid_after_utc.isoformat(),
        "certificate": b"".join(c.public_bytes(serialization.Encoding.PEM) for c in certs).decode(),
        "key": private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()).decode(),
    }
