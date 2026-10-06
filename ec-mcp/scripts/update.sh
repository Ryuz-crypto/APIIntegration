#!/usr/bin/env bash
# Actualiza ec-mcp (git pull + reinstall) y lo arranca con el .env existente.
# Uso:  ./update.sh            # foreground
#       ./update.sh --daemon   # background con log en /tmp/ec-mcp.log
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: no existe .env. Ejecuta primero ./scripts/install.sh" >&2
  exit 1
fi

echo "==> Actualizando código"
git pull --ff-only

echo "==> Reinstalando"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements-stable.txt -e . >/dev/null

echo "==> Cargando .env y arrancando"
pkill -f "ec-mcp http" 2>/dev/null || true
sleep 1
set -a; source .env; set +a
# Garantiza que orchestrator_info pueda identificar el checkout servido.
export EC_MCP_BUILD_COMMIT="${EC_MCP_BUILD_COMMIT:-$(git rev-parse HEAD)}"

HOST="${EC_MCP_HOST:-0.0.0.0}"
PORT="${EC_MCP_PORT:-8000}"

if [ "${1:-}" = "--daemon" ]; then
  nohup ec-mcp http --host "$HOST" --port "$PORT" > /tmp/ec-mcp.log 2>&1 &
  sleep 2
  echo "Servidor en background (PID $!). Log: tail -f /tmp/ec-mcp.log"
else
  exec ec-mcp http --host "$HOST" --port "$PORT"
fi
