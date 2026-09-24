import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.system import router
from app.core.config import settings
from app.services.tls_service import MAX_UPLOAD, normalize


def material(days=30, name="dashboard.example.com"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2)).not_valid_after(now + timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
            .sign(key, hashes.SHA256()))
    return cert, key


def pem(cert, key):
    return cert.public_bytes(serialization.Encoding.PEM), key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


@pytest.mark.parametrize("format", ["pem", "der", "pfx"])
def test_formats(format):
    cert, key = material()
    password = ""
    if format == "pfx":
        certificate = pkcs12.serialize_key_and_certificates(b"dashboard", key, cert, None,
                         serialization.BestAvailableEncryption(b"test-password"))
        private = b""
        password = "test-password"
    elif format == "der":
        certificate = cert.public_bytes(serialization.Encoding.DER)
        private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    else:
        certificate, private = pem(cert, key)
    result = normalize(certificate, private, password, "dashboard.example.com")
    assert result["key"].startswith("-----BEGIN PRIVATE KEY-----")
    assert result["hostname"] == "dashboard.example.com"


def test_invalid_certificates():
    cert, key = material()
    certificate, private = pem(cert, key)
    for host in ["other.example.com", "example.com;include /tmp/test", "bad\nname"]:
        with pytest.raises(ValueError):
            normalize(certificate, private, "", host)
    _, another = material()
    with pytest.raises(ValueError, match="corresponde"):
        normalize(certificate, pem(cert, another)[1], "", "dashboard.example.com")
    with pytest.raises(ValueError, match="24 horas"):
        normalize(*pem(*material(days=-1)), "", "dashboard.example.com")
    with pytest.raises(ValueError, match="256 KiB"):
        normalize(b"x" * (MAX_UPLOAD + 1), private, "", "dashboard.example.com")
    with pytest.raises(ValueError):
        normalize(b"bad-pfx", b"", "wrong", "dashboard.example.com")


def test_upload_authorization_and_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "tls_enabled", True)
    monkeypatch.setattr(settings, "tls_admin_token", "admin-test")
    monkeypatch.setattr(settings, "tls_state_dir", str(tmp_path))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    cert, key = pem(*material())
    files = {"certificate": ("cert.pem", cert), "key": ("key.pem", key)}
    data = {"hostname": "dashboard.example.com"}
    assert client.post("/tls", files=files, data=data).status_code == 403
    headers = {"X-TLS-Admin-Token": "admin-test"}
    response = client.post("/tls", files=files, data=data, headers=headers)
    assert response.status_code == 202
    assert "PRIVATE KEY" not in response.text
    assert json.loads((tmp_path / "request.json").read_text())["hostname"] == data["hostname"]
    assert client.get("/tls", headers=headers).json()["state"] == "pending"
    assert client.post("/tls", files=files, data=data, headers=headers).status_code == 409
    remote = TestClient(app, client=("203.0.113.1", 12345))
    assert remote.get("/tls", headers=headers).status_code == 400
    secure = TestClient(app, base_url="https://dashboard.example.com", client=("203.0.113.1", 12345))
    assert secure.get("/tls", headers=headers).status_code == 200
    monkeypatch.setattr(settings, "tls_enabled", False)
    assert client.get("/tls", headers=headers).status_code == 503


@pytest.mark.skipif(sys.platform == "win32", reason="Ubuntu privileged activator")
def test_activation_rolls_back(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts" / "apply-tls.py"
    spec = importlib.util.spec_from_file_location("tls_activator", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "nginx.conf"
    config.write_bytes(b"previous nginx config")
    monkeypatch.setattr(module, "CONFIG", config)
    monkeypatch.setattr(module, "CERT_DIR", tmp_path / "certs")
    calls = []
    def fail_validation(command, **kwargs):
        calls.append(command)
        if command[-1] == "-t":
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(module.subprocess, "run", fail_validation)
    with pytest.raises(subprocess.CalledProcessError):
        module.activate(normalize(*pem(*material()), "", "dashboard.example.com"))
    assert config.read_bytes() == b"previous nginx config"
    assert not (tmp_path / "certs" / "privkey.pem").exists()
    assert calls[-1][-2:] == ["reload", "nginx"]
