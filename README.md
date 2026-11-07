# APIIntegration — ec-mcp

[![ec-mcp](https://img.shields.io/badge/ec--mcp-8.2.0%20stable-7B61FF)](ec-mcp/README.md)
[![Human Verified](https://img.shields.io/badge/human--verified-%E2%9C%93-2EA44F)](SECURITY.md)
[![ec-mcp CI](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml)
[![Licencia restringida](https://img.shields.io/badge/licencia-uso_restringido-blue.svg)](LICENSE)

Servidor **MCP (Model Context Protocol)** para descubrir, consultar y operar entornos **HPE Aruba Networking EdgeConnect SD-WAN** desde asistentes de IA, mediante la API REST del Orchestrator, comandos `show` y un panel de administración web.

## ec-mcp — MCP y panel de administración web

Versión estable en `main`: **8.2.0**. CI en verde y verificado en laboratorio sobre Orchestrator 9.x/10.x. Referencia exhaustiva en [ec-mcp/README.md](ec-mcp/README.md) y plantilla completa en [ec-mcp/.env.example](ec-mcp/.env.example).

### Instalación (Linux)

Requisitos: Ubuntu/Debian con Python 3.12+.

```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip curl

git clone --branch main https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
./scripts/install.sh --non-interactive

cp -n .env.example .env
nano .env
```

Configura como mínimo en `.env` (sin espacios alrededor de `=` y sin claves duplicadas):

```dotenv
EC_ORCHESTRATOR_URL=https://TU-ORCHESTRATOR
EC_ORCHESTRATOR_API_KEY=  # pega aquí la API key
EC_VERIFY_TLS=true

EC_SSH_ENABLED=false
EC_ALLOW_WRITE_TOOLS=false
EC_ALLOW_DANGEROUS_WRITES=false
EC_MCP_AUDIT_LOG=logs/mcp-audit.jsonl

EC_MCP_AUTH_TOKEN=  # genera un token aleatorio para producción
EC_MCP_HOST=0.0.0.0
EC_MCP_PORT=8000
EC_MCP_ALLOWED_HOSTS=mcp.example.com

EC_ADMIN_HOST=0.0.0.0
EC_ADMIN_PORT=9090
EC_ADMIN_PASSWORD=  # define una contraseña fuerte

EC_UPDATE_ALLOW_WEB=true
EC_UPDATE_REPOSITORY=Ryuz-crypto/APIIntegration
EC_UPDATE_BRANCH=main
EC_UPDATE_GITHUB_TOKEN=
EC_UPDATE_STATE_DIR=/var/lib/ec-mcp-update
EC_UPDATE_SERVICE_NAME=ec-mcp.service
EC_UPDATE_ADMIN_SERVICE_NAME=ec-mcp-admin.service
```

Genera los secretos con:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Servicios systemd

```bash
./scripts/install_service.sh
./scripts/install_admin_service.sh --port 9090

sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
systemctl --no-pager status ec-mcp ec-mcp-admin
curl -fsS http://127.0.0.1:8000/health
```

El panel administrativo queda en `http://IP-DEL-SERVIDOR:9090`.

### Cliente MCP (stdio)

El cliente sólo necesita la ruta al `.env`; no coloques credenciales en el JSON:

```json
{
  "mcpServers": {
    "ec-mcp": {
      "command": "/home/TU-USUARIO/APIIntegration/ec-mcp/.venv/bin/ec-mcp",
      "env": {
        "EC_MCP_ENV_FILE": "/home/TU-USUARIO/APIIntegration/ec-mcp/.env"
      }
    }
  }
}
```

Para transporte remoto usa `https://TU-HOST/mcp` con el Bearer token de `EC_MCP_AUTH_TOKEN`.

### Reglas de configuración

- `ec-mcp/.env` es la **única fuente de configuración**: no dupliques credenciales en el JSON del cliente ni declares `EC_ADMIN_PORT` o `EC_ADMIN_PASSWORD` directamente en systemd.
- Las escrituras están deshabilitadas por defecto (`EC_ALLOW_WRITE_TOOLS=false`); habilítalas expresamente cuando las necesites.
- Lectura por API del Orchestrator sin SSH: `run_show_api(command="show arp", appliance_id="0.NE")`.

### Actualizar a 8.2.0

```bash
cd ~/APIIntegration
git status --short          # no continúes con cambios sin respaldar
git fetch origin
git switch --detach origin/main
cd ec-mcp
./scripts/install.sh --non-interactive
./scripts/install_service.sh
./scripts/install_admin_service.sh
sudo systemctl daemon-reload && sudo systemctl restart ec-mcp ec-mcp-admin
./.venv/bin/python -c "import ec_mcp; assert ec_mcp.__version__ == '8.2.0'; print(ec_mcp.__version__)"
```

Antes de actualizar: respalda `.env`, configuración administrativa, logs y estado ZTP, y termina las operaciones en curso. La guía completa con recuperación está en [Upgrade por terminal](ec-mcp/README.md#upgrade-por-terminal).

### Reporte de bugs

Los fallos se registran en [GitHub Issues](https://github.com/Ryuz-crypto/APIIntegration/issues) buscando duplicados primero; el número del issue (`#123`) es su **Bug ID** y se enlaza desde el PR de corrección. Usa la [plantilla de reporte](.github/ISSUE_TEMPLATE/bug_report.md) y excluye secretos y datos sensibles. Reglas para asistentes de IA: [AGENTS.md](AGENTS.md).

### Referencias

- Documentación completa (variables, seguridad, updater, HTTP/SSE, systemd, nginx): [ec-mcp/README.md](ec-mcp/README.md)
- Seguridad y reporte de vulnerabilidades: [SECURITY.md](SECURITY.md)

## Licencia

Uso restringido: evaluación, estudio y uso interno. Comercialización, copia fuera de la instalación/respaldo y redistribución requieren autorización escrita. Texto completo en [LICENSE](LICENSE).

## Contacto

Consultas, soporte y propuestas: [decameru@outlook.com](mailto:decameru@outlook.com)
