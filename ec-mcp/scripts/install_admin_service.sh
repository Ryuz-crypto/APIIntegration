#!/usr/bin/env bash
# Instala la UI de admin de ec-mcp (ec-mcp admin) como servicio systemd.
# Requiere EC_ADMIN_PASSWORD en .env (obligatorio porque escucha en 0.0.0.0).
# Uso:  ./scripts/install_admin_service.sh [--port 8080]

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${EC_ADMIN_PORT:-8080}"
if [ "${1:-}" = "--port" ]; then
  PORT="${2:-8080}"
fi

if [ ! -f .env ]; then
  echo "ERROR: no existe .env en $(pwd). Ejecuta primero ./scripts/install.sh" >&2
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
SERVICE_FILE=/etc/systemd/system/ec-mcp-admin.service

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=EdgeConnect SD-WAN MCP admin UI (ec-mcp admin)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
Environment=EC_MCP_ENV_FILE=${PROJECT_DIR}/.env
Environment=EC_ADMIN_HOST=0.0.0.0
Environment=EC_ADMIN_PORT=${PORT}
ExecStart=${PROJECT_DIR}/.venv/bin/ec-mcp admin
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ec-mcp-admin
sleep 2
systemctl --no-pager --lines=5 status ec-mcp-admin || true

echo ""
echo "Servicio ec-mcp-admin instalado y habilitado (arranca en el boot)."
echo "UI: http://<IP-del-server>:${PORT}  (accesible desde cualquier IP)"
echo "Comandos utiles:"
echo "  systemctl status ec-mcp-admin"
echo "  sudo systemctl restart ec-mcp-admin"
echo "  journalctl -u ec-mcp-admin -f"
