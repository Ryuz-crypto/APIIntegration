#!/usr/bin/env bash
# Instalación de ec-mcp en un solo comando (Ubuntu/Debian).
# Uso:  ./install.sh
# Idempotente: se puede reejecutar sin romper nada; nunca sobrescribe tu .env.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1/4 Dependencias del sistema (si faltan)"
if ! command -v python3 >/dev/null || ! python3 -c "import venv" 2>/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip
fi

echo "==> 2/4 Entorno virtual + paquete"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e .

if [ ! -f .env ]; then
  echo "==> 3/4 Creando .env a partir de .env.example"
  cp .env.example .env
  if [ -z "${EC_MCP_AUTH_TOKEN:-}" ]; then
    TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    sed -i "s|^EC_MCP_AUTH_TOKEN=.*|EC_MCP_AUTH_TOKEN=${TOKEN}|" .env
    echo "    Token generado automáticamente en .env"
  fi
  echo "    >>> EDITA .env y pon tu EC_ORCHESTRATOR_URL y EC_ORCHESTRATOR_API_KEY <<<"
else
  echo "==> 3/4 .env ya existe: se conserva"
fi

echo "==> 4/4 Verificación"
python -m pytest tests -q

cat <<'EOF'

Instalación terminada.

Próximos pasos:
  1. nano .env                       # URL + API key del Orchestrator
  2. ./update.sh                     # arranca el servidor HTTP (foreground)
     (o: ./update.sh --daemon       # en background, log en /tmp/ec-mcp.log)
EOF
