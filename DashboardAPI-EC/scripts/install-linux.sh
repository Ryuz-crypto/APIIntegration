#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
else
  echo "Cannot detect Linux distribution: /etc/os-release not found." >&2
  exit 1
fi

SUDO=""
if [ "${EUID}" -ne 0 ]; then
  SUDO="sudo"
fi

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

install_debian_family() {
  local repo_os="ubuntu"
  local codename="${VERSION_CODENAME:-}"
  if [ "${ID}" = "debian" ] || [[ "${ID_LIKE:-}" == *debian* && "${ID}" != "ubuntu" ]]; then
    repo_os="debian"
  fi
  if [ "${ID}" = "ubuntu" ] && [ -n "${UBUNTU_CODENAME:-}" ]; then
    codename="${UBUNTU_CODENAME}"
  fi
  if [ -z "${codename}" ]; then
    echo "Cannot detect Debian/Ubuntu codename for Docker repository." >&2
    exit 1
  fi

  ${SUDO} apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc || true
  ${SUDO} apt-get update
  ${SUDO} apt-get install -y ca-certificates curl git gnupg openssl
  ${SUDO} install -m 0755 -d /etc/apt/keyrings
  ${SUDO} curl -fsSL "https://download.docker.com/linux/${repo_os}/gpg" -o /etc/apt/keyrings/docker.asc
  ${SUDO} chmod a+r /etc/apt/keyrings/docker.asc
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
    "$(dpkg --print-architecture)" "${repo_os}" "${codename}" |
    ${SUDO} tee /etc/apt/sources.list.d/docker.list >/dev/null
  ${SUDO} apt-get update
  ${SUDO} apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_rhel_family() {
  local installer="dnf"
  if ! command_exists dnf; then
    installer="yum"
  fi
  ${SUDO} "${installer}" install -y git curl openssl
  if ! command_exists docker; then
    ${SUDO} "${installer}" install -y yum-utils || true
    ${SUDO} "${installer}" config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    ${SUDO} "${installer}" install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  elif ! ${SUDO} docker compose version >/dev/null 2>&1; then
    ${SUDO} "${installer}" install -y docker-compose-plugin
  fi
}

install_prerequisites() {
  case "${ID_LIKE:-${ID}}" in
    *debian*|*ubuntu*)
      install_debian_family
      ;;
    *rhel*|*fedora*|*centos*)
      install_rhel_family
      ;;
    *)
      case "${ID}" in
        ubuntu|debian)
          install_debian_family
          ;;
        rocky|rhel|centos|fedora)
          install_rhel_family
          ;;
        *)
          echo "Unsupported distribution '${ID}'. Install git, docker, docker compose plugin, curl and openssl, then rerun." >&2
          exit 1
          ;;
      esac
      ;;
  esac
  ${SUDO} systemctl enable --now docker
  validate_prerequisites
}

validate_prerequisites() {
  if ! command_exists git; then
    echo "Missing required command: git" >&2
    exit 1
  fi
  if ! command_exists curl; then
    echo "Missing required command: curl" >&2
    exit 1
  fi
  if ! command_exists openssl; then
    echo "Missing required command: openssl" >&2
    exit 1
  fi
  if ! command_exists docker; then
    echo "Missing required command: docker" >&2
    exit 1
  fi
  if ! ${SUDO} docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is not available. Validate with: sudo docker compose version" >&2
    exit 1
  fi
}

prompt_value() {
  local name="$1"
  local prompt="$2"
  local default_value="$3"
  local value=""
  read -r -p "${prompt} [${default_value}]: " value
  if [ -z "${value}" ]; then
    value="${default_value}"
  fi
  printf -v "${name}" '%s' "${value}"
}

secret_value() {
  local generated=""
  generated="$(openssl rand -hex 24)"
  printf '%s' "${generated}"
}

write_env_file() {
  local dashboard_port postgres_user postgres_password postgres_db secret_key cors_origins environment
  prompt_value dashboard_port "Dashboard HTTP port" "8080"
  prompt_value postgres_user "PostgreSQL user" "edgeconnect"
  prompt_value postgres_password "PostgreSQL password" "$(secret_value)"
  prompt_value postgres_db "PostgreSQL database" "edgeconnect"
  prompt_value secret_key "Application secret key" "$(secret_value)"
  prompt_value cors_origins "Allowed CORS origins" "http://localhost:5173,http://localhost:${dashboard_port}"
  prompt_value environment "Environment name" "production"

  cat > "${ENV_FILE}" <<EOF
PROJECT_NAME=DashboardAPI-EC
ENVIRONMENT=${environment}
API_V1_PREFIX=/api/v1
BACKEND_CORS_ORIGINS=${cors_origins}
DASHBOARD_HTTP_PORT=${dashboard_port}

POSTGRES_USER=${postgres_user}
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=${postgres_db}
DATABASE_URL=postgresql+psycopg://${postgres_user}:${postgres_password}@postgres:5432/${postgres_db}

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

SECRET_KEY=${secret_key}
ACCESS_TOKEN_EXPIRE_MINUTES=60
EOF
}

start_stack() {
  cd "${ROOT_DIR}"
  ${SUDO} docker compose up -d --build
}

validate_stack() {
  local dashboard_port
  dashboard_port="$(grep '^DASHBOARD_HTTP_PORT=' "${ENV_FILE}" | cut -d '=' -f2)"
  echo "Waiting for API health on http://localhost:${dashboard_port}/api/v1/health"
  for _ in $(seq 1 40); do
    if curl -fsS "http://localhost:${dashboard_port}/api/v1/health" >/dev/null 2>&1; then
      echo "DashboardAPI-EC is ready: http://localhost:${dashboard_port}"
      return 0
    fi
    sleep 3
  done
  echo "The stack started, but health check did not pass yet. Run: ${SUDO} docker compose logs -f" >&2
  return 1
}

install_prerequisites
write_env_file
start_stack
validate_stack
