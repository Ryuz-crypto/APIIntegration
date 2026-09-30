#!/usr/bin/env bash
# Instala ec-mcp como servicio systemd que arranca en el boot.
# Pensado para la instalacion en el directorio del usuario (p.ej. ~/APIIntegration/ec-mcp).
# Uso:  ./scripts/install_service.sh [--port 8000]
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${EC_MCP_PORT:-8000}"
if [ "${1:-}" = "--port" ]; then
  PORT="${2:-8000}"
fi

if [ ! -f .env ]; then
  echo "ERROR: no existe .env en $(pwd). Ejecuta primero ./scripts/install.sh" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null; then
  echo "ERROR: systemctl no disponible (¿no es Linux con systemd?)" >&2
  exit 1
fi

PROJECT_DIR="$(pwd)"
SERVICE_FILE=/etc/systemd/system/ec-mcp.service

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=EdgeConnect SD-WAN MCP server (ec-mcp)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
Environment=EC_MCP_ENV_FILE=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/ec-mcp http --host 0.0.0.0 --port ${PORT}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ec-mcp
sleep 2
systemctl --no-pager --lines=5 status ec-mcp || true

echo ""
echo "Servicio ec-mcp instalado y habilitado (arranca en el boot)."
echo "Comandos utiles:"
echo "  systemctl status ec-mcp        # estado"
echo "  sudo systemctl restart ec-mcp  # reiniciar tras actualizar"
echo "  journalctl -u ec-mcp -f        # ver logs"
echo "  curl http://localhost:${PORT}/health  # verificar"
