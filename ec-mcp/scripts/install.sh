#!/usr/bin/env bash
# Instalación de ec-mcp en un solo comando (Ubuntu/Debian).
# Uso:  ./scripts/install.sh          (interactivo: pregunta credenciales)
#       ./scripts/install.sh --non-interactive   (solo instala, .env sin credenciales)
# Idempotente: se puede reejecutar sin romper nada; nunca sobrescribe un .env existente.
set -euo pipefail
cd "$(dirname "$0")/.."

INTERACTIVE=1
if [ "${1:-}" = "--non-interactive" ]; then
  INTERACTIVE=0
fi

prompt_default() {
  local question="$1" default="$2" value
  read -r -p "$question [$default]: " value
  value="${value:-$default}"
  printf '%s' "$value"
}

prompt_secret() {
  local question="$1" value
  read -r -s -p "$question: " value
  echo >&2
  printf '%s' "$value"
}

set_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

echo "==> 1/5 Dependencias del sistema (si faltan)"
if ! command -v python3 >/dev/null || ! python3 -c "import venv" 2>/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip
fi

echo "==> 2/5 Entorno virtual + paquete"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e .

if [ -f .env ]; then
  echo "==> 3/5 .env ya existe: se conserva (borra .env para reconfigurar)"
else
  echo "==> 3/5 Configuración de credenciales"
  cp .env.example .env
  chmod 600 .env

  TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  set_env_value EC_MCP_AUTH_TOKEN "$TOKEN"

  if [ "$INTERACTIVE" -eq 1 ]; then
    echo "    (Enter acepta el valor entre corchetes)"
    ORCH_URL="$(prompt_default "URL del Orchestrator" "https://lac-wan-sewan-orchge-useast1.silverpeak.cloud")"
    set_env_value EC_ORCHESTRATOR_URL "${ORCH_URL%/}"
    API_KEY="$(prompt_secret "API key del Orchestrator (X-Auth-Token)")"
    if [ -n "$API_KEY" ]; then
      set_env_value EC_ORCHESTRATOR_API_KEY "$API_KEY"
    fi
    SSH_ENABLED="$(prompt_default "SSH a appliances (true/false)" "true")"
    set_env_value EC_SSH_ENABLED "$SSH_ENABLED"
    if [ "$SSH_ENABLED" = "true" ]; then
      SSH_HOST="$(prompt_default "IP/host del appliance" "192.168.1.40")"
      set_env_value EC_SSH_HOST "$SSH_HOST"
      SSH_USER="$(prompt_default "Usuario SSH del appliance" "mcp")"
      set_env_value EC_SSH_USER "$SSH_USER"
      SSH_PASS="$(prompt_secret "Password SSH")"
      if [ -n "$SSH_PASS" ]; then
        set_env_value EC_SSH_PASSWORD "$SSH_PASS"
      fi
      SSH_ENABLE="$(prompt_secret "Password de enable (Enter si no hay)")"
      if [ -n "$SSH_ENABLE" ]; then
        set_env_value EC_SSH_ENABLE_PASSWORD "$SSH_ENABLE"
      fi
    fi
    ALLOWED="$(prompt_default "Dominio(s) públicos del túnel, separados por coma" "")"
    set_env_value EC_MCP_ALLOWED_HOSTS "$ALLOWED"
    BIND="$(prompt_default "IP de escucha (0.0.0.0 para exponer via túnel)" "0.0.0.0")"
    set_env_value EC_MCP_HOST "$BIND"
  else
    echo "    (modo no interactivo: edita .env a mano)"
  fi

  echo ""
  echo "    Token MCP generado automáticamente: $TOKEN"
  echo "    (es el que pegas como Bearer en el conector de Mistral)"
fi

echo "==> 4/5 Verificación"
python -m pytest tests -q

echo "==> 5/5 Listo"
if [ -f .env ]; then
  echo "    Credenciales en .env (permisos 600):"
  grep -E '^(EC_ORCHESTRATOR_URL|EC_SSH_ENABLED|EC_SSH_HOST|EC_MCP_HOST|EC_MCP_ALLOWED_HOSTS)=' .env | sed 's/^/      /'
  echo "    (secretos omitidos)"
fi

cat <<'EOF'

Instalación terminada.

Arranque:
  ./scripts/update.sh --daemon     # background, log en /tmp/ec-mcp.log
  ./scripts/update.sh              # foreground

Verificar:  curl http://localhost:8000/health
EOF
