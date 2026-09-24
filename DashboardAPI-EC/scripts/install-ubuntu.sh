#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Ejecuta: sudo ./scripts/install-ubuntu.sh" >&2
  exit 1
fi
if [[ ! -r /etc/os-release ]]; then
  echo "No se pudo identificar el sistema operativo." >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "DashboardAPI-EC 1.0 solo se instala en Ubuntu." >&2
  exit 1
fi

echo "[1/4] Instalando dependencias de construcción y ejecución..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential ca-certificates curl dpkg-dev nginx nodejs npm openssl \
  postgresql python3 python3-pip python3-venv redis-server

echo "[2/4] Construyendo el paquete para $(dpkg --print-architecture)..."
BUILD_USER="${SUDO_USER:-root}"
BUILD_HOME="$(getent passwd "$BUILD_USER" | cut -d: -f6)"
runuser -u "$BUILD_USER" -- env HOME="$BUILD_HOME" "$ROOT_DIR/scripts/build-deb.sh"
PACKAGE_PATH="$(find "$ROOT_DIR/dist" -maxdepth 1 -name 'dashboardapi-ec_1.0.0_*.deb' -print -quit)"
if [[ -z "$PACKAGE_PATH" ]]; then
  echo "No se generó el paquete .deb." >&2
  exit 1
fi

echo "[3/4] Instalando DashboardAPI-EC..."
apt-get install -y "$PACKAGE_PATH"

echo "[4/4] Verificando servicios..."
systemctl is-active --quiet dashboardapi-ec
systemctl is-active --quiet nginx
for _ in {1..15}; do
  if curl --fail --silent http://127.0.0.1/api/v1/health >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1/api/v1/health >/dev/null

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
SERVER_IP="${SERVER_IP:-127.0.0.1}"
echo
echo "DashboardAPI-EC 1.0 stable quedó instalado."
echo "Abre: http://${SERVER_IP}/"
echo "Luego selecciona 'Conectar Orchestrator' para guardar la primera conexión."
