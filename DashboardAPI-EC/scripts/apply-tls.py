#!/opt/dashboardapi-ec/venv/bin/python
"""Root-only activator; accepts certificate material, never configuration or commands."""

import http.client
import json
import os
import pwd
import socket
import ssl
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.services.tls_service import normalize

STATE = "/var/lib/dashboardapi-ec-tls"
CONFIG = Path("/etc/nginx/sites-available/dashboardapi-ec")
CERT_DIR = Path("/etc/dashboardapi-ec/tls")


def atomic(path, content, mode=0o600):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def nginx_config(hostname):
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"""include /opt/dashboardapi-ec/nginx-bootstrap.conf;
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 308 https://{host}$request_uri;
}}
server {{
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name {hostname};
    ssl_certificate /etc/dashboardapi-ec/tls/fullchain.pem;
    ssl_certificate_key /etc/dashboardapi-ec/tls/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 1m;
    root /usr/share/dashboardapi-ec/frontend;
    index index.html;
    location /api/ {{
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    location / {{ try_files $uri $uri/ /index.html; }}
}}
""".encode()


def wait_for_https(material):
    """A successful reload signal alone does not mean the new workers are ready."""
    expected = x509.load_pem_x509_certificates(material["certificate"].encode())[0].public_bytes(
        serialization.Encoding.DER
    )
    hostname = material["hostname"]
    host = f"[{hostname}]" if ":" in hostname else hostname
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Trust the exact uploaded certificate, including private/internal CAs.
    # This is a loopback readiness probe, not an outbound Orchestrator connection.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=1)
        try:
            with socket.create_connection(("127.0.0.1", 443), timeout=1) as raw:
                with context.wrap_socket(raw, server_hostname=hostname) as secure:
                    certificate_matches = secure.getpeercert(binary_form=True) == expected
            connection.request("GET", "/", headers={"Host": host, "Connection": "close"})
            response = connection.getresponse()
            if (
                certificate_matches
                and response.status == 308
                and response.getheader("Location") == f"https://{host}/"
            ):
                return
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.25)
    raise RuntimeError("Nginx did not activate the expected certificate and redirect")


def activate(material):
    CERT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    paths = [CERT_DIR / "fullchain.pem", CERT_DIR / "privkey.pem", CONFIG]
    old = {p: p.read_bytes() if p.exists() else None for p in paths}
    try:
        for path, content in zip(
            paths,
            [
                material["certificate"].encode(),
                material["key"].encode(),
                nginx_config(material["hostname"]),
            ],
        ):
            atomic(path, content)
        subprocess.run(["/usr/sbin/nginx", "-t"], check=True, capture_output=True, timeout=30)
        subprocess.run(
            ["/usr/bin/systemctl", "reload", "nginx"], check=True, capture_output=True, timeout=30
        )
        wait_for_https(material)
    except Exception:
        for path, content in old.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path, content)
        subprocess.run(["/usr/bin/systemctl", "reload", "nginx"], capture_output=True, timeout=30)
        raise


def main():
    # The direct parent /var/lib is root-owned. Directory-relative operations and
    # O_NOFOLLOW prevent a compromised API from redirecting privileged writes.
    directory = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fd = os.open(
                "request.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return
        result = {
            "state": "error",
            "message": "No se activó HTTPS. Se conservó la configuración anterior.",
        }
        try:
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("Not a regular file")
                raw = stream.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ValueError("Request too large")
            request = json.loads(raw)
            material = normalize(
                request["certificate"].encode(), request["key"].encode(), "", request["hostname"]
            )
            activate(material)
            result = {
                "state": "active",
                "hostname": material["hostname"],
                "expires_at": material["expires_at"],
            }
        except Exception:
            # Never put certificate contents, keys or subprocess output in status/logs.
            pass
        name = f"status-{os.urandom(16).hex()}"
        out = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory
        )
        account = pwd.getpwnam("dashboardapi")
        os.fchown(out, account.pw_uid, account.pw_gid)
        with os.fdopen(out, "w") as stream:
            json.dump(result, stream)
        os.replace(name, "status.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.unlink("request.json", dir_fd=directory)
    finally:
        os.close(directory)


if __name__ == "__main__":
    main()
