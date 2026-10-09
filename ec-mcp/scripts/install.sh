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
pip install -r requirements-stable.txt -e .

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
      echo "    Credenciales comunes para todos los appliances; los hosts se"
      echo "    descubren desde el Orchestrator en cada consulta."
      SSH_USER="$(prompt_default "Usuario SSH (comun para todos los appliances)" "mcp")"
      set_env_value EC_SSH_USER "$SSH_USER"
      SSH_PASS="$(prompt_secret "Password SSH (comun para todos)")"
      if [ -n "$SSH_PASS" ]; then
        set_env_value EC_SSH_PASSWORD "$SSH_PASS"
      fi
      SSH_ENABLE="$(prompt_secret "Password de enable (comun; Enter si no hay)")"
      if [ -n "$SSH_ENABLE" ]; then
        set_env_value EC_SSH_ENABLE_PASSWORD "$SSH_ENABLE"
      fi
      echo "    Autodetectando appliances desde el Orchestrator..."
      if ! ./scripts/detect_appliances.sh; then
        echo "    (No se pudo consultar el inventario ahora; no es bloqueante:)"
        echo "     el servidor resuelve los hosts contra el Orchestrator en cada consulta)"
      fi
    fi
    ALLOWED="$(prompt_default "Dominio(s) públicos del túnel, separados por coma" "")"
    set_env_value EC_MCP_ALLOWED_HOSTS "$ALLOWED"
    BIND="$(prompt_default "IP de escucha (0.0.0.0 = todas, necesario para túnel)" "0.0.0.0")"
    set_env_value EC_MCP_HOST "$BIND"
  else
    echo "    (modo no interactivo: edita .env a mano)"
  fi

  echo ""
  echo "    Token MCP generado automáticamente: $TOKEN"
  echo "    (es el que pegas como Bearer en el conector de Mistral)"
fi

echo "==> 4/6 Verificación"
python -m pytest tests -q

echo "==> 5/6 Servicios systemd (arranque automático en el boot)"
if command -v systemctl >/dev/null; then
  ./scripts/install_service.sh
  if [ -n "$(grep '^EC_ADMIN_PASSWORD=' .env | cut -d= -f2)" ]; then
    ./scripts/install_admin_service.sh
  else
    echo "    (ec-mcp-admin omitido: EC_ADMIN_PASSWORD no esta configurado en .env)"
  fi
else
  echo "    (systemctl no disponible: arranca manualmente con ./scripts/update.sh)"
fi

echo "==> 6/6 Listo"
if [ -f .env ]; then
  echo "    Credenciales en .env (permisos 600):"
  grep -E '^(EC_ORCHESTRATOR_URL|EC_SSH_ENABLED|EC_SSH_HOST|EC_MCP_HOST|EC_MCP_ALLOWED_HOSTS)=' .env | sed 's/^/      /'
  echo "    (secretos omitidos)"
fi

cat <<'EOF'

Instalación terminada.

Los servicios ec-mcp (y ec-mcp-admin, si aplica) quedan instalados con
systemctl enable --now: arrancan automáticamente al reiniciar el servidor y
se reinician solos ante fallos (Restart=on-failure).

Comandos útiles:
  systemctl status ec-mcp ec-mcp-admin
  sudo systemctl restart ec-mcp ec-mcp-admin
  journalctl -u ec-mcp -f

Verificar:  curl http://localhost:8000/health
EOF
