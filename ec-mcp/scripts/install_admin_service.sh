#!/usr/bin/env bash
# Instala la UI de admin de ec-mcp (ec-mcp admin) como servicio systemd.
# Requiere EC_ADMIN_PASSWORD en .env (obligatorio porque escucha en 0.0.0.0).
# Uso:  ./scripts/install_admin_service.sh [--port PUERTO]
# Prioridad: --port > EC_ADMIN_PORT del proceso > EC_ADMIN_PORT de .env > 8080.

set -euo pipefail
cd "$(dirname "$0")/.."

CLI_PORT=""
if [ "${1:-}" = "--port" ]; then
  if [ -z "${2:-}" ]; then
    echo "ERROR: --port requiere un número de puerto." >&2
    exit 1
  fi
  CLI_PORT="$2"
fi

if [ ! -f .env ]; then
  echo "ERROR: no existe .env en $(pwd). Ejecuta primero ./scripts/install.sh" >&2
  exit 1
fi

ENV_PORT="$(grep '^EC_ADMIN_PORT=' .env | tail -1 | cut -d= -f2- || true)"
PORT="${CLI_PORT:-${EC_ADMIN_PORT:-${ENV_PORT:-8080}}}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "ERROR: EC_ADMIN_PORT debe ser un número entre 1 y 65535." >&2
  exit 1
fi

if ! grep -q '^EC_ADMIN_PASSWORD=' .env || [ -z "$(grep '^EC_ADMIN_PASSWORD=' .env | cut -d= -f2)" ]; then
  echo "ERROR: EC_ADMIN_PASSWORD no esta configurado en .env." >&2
  echo "La UI de admin escucha en 0.0.0.0 y se niega a arrancar sin contrasena." >&2
  echo "Agrega una contrasena fuerte:  echo 'EC_ADMIN_PASSWORD=<contrasena>' >> .env" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null; then
  echo "ERROR: systemctl no disponible (¿no es Linux con systemd?)" >&2
  exit 1
fi

PROJECT_DIR="$(pwd)"
INSTALL_USER="$(stat -c %U "$PROJECT_DIR")"
INSTALL_GROUP="$(id -gn "$INSTALL_USER")"
STATE_DIR="$(grep '^EC_UPDATE_STATE_DIR=' .env | tail -1 | cut -d= -f2- || true)"
STATE_DIR="${STATE_DIR:-/var/lib/ec-mcp-update}"
set_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}
set_env_value EC_UPDATE_PROJECT_DIR "$PROJECT_DIR"
set_env_value EC_UPDATE_STATE_DIR "$STATE_DIR"
set_env_value EC_UPDATE_ALLOW_WEB "true"
set_env_value EC_ADMIN_PORT "$PORT"
chmod 600 .env
sudo install -d -m 0750 -o "$INSTALL_USER" -g "$INSTALL_GROUP" "$STATE_DIR"

SERVICE_FILE=/etc/systemd/system/ec-mcp-admin.service
UPDATE_SERVICE_FILE=/etc/systemd/system/ec-mcp-update.service
UPDATE_TIMER_FILE=/etc/systemd/system/ec-mcp-update.timer

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=EdgeConnect SD-WAN MCP admin UI (ec-mcp admin)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${INSTALL_USER}
Group=${INSTALL_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment=EC_MCP_ENV_FILE=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/ec-mcp admin
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$UPDATE_SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=ec-mcp validated web update worker
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
Environment=EC_MCP_ENV_FILE=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/python ${PROJECT_DIR}/scripts/apply-web-update.py
PrivateTmp=true
ProtectHome=read-only
EOF

sudo tee "$UPDATE_TIMER_FILE" >/dev/null <<EOF
[Unit]
Description=Poll ec-mcp web update requests

[Timer]
OnBootSec=20s
OnUnitActiveSec=20s
AccuracySec=2s
Unit=ec-mcp-update.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ec-mcp-admin ec-mcp-update.timer
if systemctl is-active --quiet ec-mcp-admin; then
  sudo systemctl restart ec-mcp-admin
else
  sudo systemctl start ec-mcp-admin
fi
sudo systemctl start ec-mcp-update.timer
sleep 2
systemctl --no-pager --lines=5 status ec-mcp-admin || true

echo ""
echo "Panel ec-mcp-admin y updater web instalados y habilitados."
echo "UI: http://<IP-del-server>:${PORT}  (accesible desde cualquier IP)"
echo "Comandos utiles:"
echo "  systemctl status ec-mcp-admin"
echo "  systemctl status ec-mcp-update.timer"
echo "  cat $STATE_DIR/status.json"
echo "  sudo systemctl restart ec-mcp-admin"
echo "  journalctl -u ec-mcp-admin -f"
