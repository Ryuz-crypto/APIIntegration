#!/usr/bin/env bash
set -euo pipefail
TLS_TEST_STAGE="install"
trap 'echo "::error title=HTTPS integration::Stage ${TLS_TEST_STAGE} failed at line ${LINENO}" >&2' ERR
# Disposable CI host only: installs the package and configures its Nginx site.
sudo apt-get install -y ./dist/dashboardapi-ec_1.0.0_*.deb
TLS_TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TLS_TEST_DIR"' EXIT
TLS_TEST_STAGE="generate certificate"
openssl req -x509 -newkey rsa:2048 -nodes -days 7 -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost' \
  -keyout "$TLS_TEST_DIR/key.pem" -out "$TLS_TEST_DIR/cert.pem" 2>/dev/null
TLS_TEST_STAGE="bootstrap readiness"
TLS_TEST_TOKEN="$(sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env)"
for attempt in $(seq 1 30); do
  if curl -fsS -H "X-TLS-Admin-Token: $TLS_TEST_TOKEN" http://127.0.0.1:8081/api/v1/system/tls >/dev/null; then break; fi
  sleep 2
done
TLS_TEST_STAGE="upload"
curl -fsS -H "X-TLS-Admin-Token: $TLS_TEST_TOKEN" \
  -F hostname=localhost -F "certificate=@$TLS_TEST_DIR/cert.pem" -F "key=@$TLS_TEST_DIR/key.pem" \
  http://127.0.0.1:8081/api/v1/system/tls | python3 -c 'import json,sys; assert json.load(sys.stdin)["state"] == "pending"'
TLS_TEST_STAGE="activate"
sudo systemctl start dashboardapi-ec-tls.service
curl -fsS -H "X-TLS-Admin-Token: $TLS_TEST_TOKEN" http://127.0.0.1:8081/api/v1/system/tls \
  | python3 -c 'import json,sys; assert json.load(sys.stdin)["state"] == "active"'
TLS_TEST_STAGE="HTTPS request"
curl --cacert "$TLS_TEST_DIR/cert.pem" -fsS https://localhost/ >/dev/null
TLS_TEST_STAGE="HTTP redirect"
TLS_HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' http://localhost/)"
echo "HTTP response code: $TLS_HTTP_CODE"
test "$TLS_HTTP_CODE" = 308
TLS_TEST_STAGE="private key permissions"
TLS_KEY_MODE="$(sudo stat -c '%a' /etc/dashboardapi-ec/tls/privkey.pem)"
echo "Private key permissions: $TLS_KEY_MODE"
test "$TLS_KEY_MODE" = 600
TLS_TEST_STAGE="reinstall"
sudo apt-get install --reinstall -y ./dist/dashboardapi-ec_1.0.0_*.deb
TLS_TEST_STAGE="HTTPS after reinstall"
curl --cacert "$TLS_TEST_DIR/cert.pem" -fsS https://localhost/ >/dev/null
sudo nginx -t
