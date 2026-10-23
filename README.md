# APIIntegration — ec-mcp

[![ec-mcp](https://img.shields.io/badge/ec--mcp-6.0.0%20stable-7B61FF)](ec-mcp/README.md)
[![ec-mcp CI](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml)
[![Licencia restringida](https://img.shields.io/badge/licencia-uso_restringido-blue.svg)](LICENSE)

Servidor **MCP (Model Context Protocol)** para descubrir, consultar y operar entornos **HPE Aruba Networking EdgeConnect SD-WAN** mediante sus APIs y su CLI ECOS desde asistentes de IA.

## Registro de bugs

Todo bug detectado por personas o asistentes de IA se registra en [GitHub Issues](https://github.com/Ryuz-crypto/APIIntegration/issues), buscando duplicados primero. El número del issue (`#123`) es su **Bug ID** y se enlaza desde el PR de corrección. Usa la [plantilla de reporte](.github/ISSUE_TEMPLATE/bug_report.md), identifica si el hallazgo está reproducido o pendiente de validar y excluye secretos y datos sensibles. La regla provisional para cualquier IA que trabaje en el repositorio está en [AGENTS.md](AGENTS.md); el equipo podrá ampliarla con su criterio definitivo.

| Componente | Qué hace | Documentación |
| --- | --- | --- |
| **ec-mcp** | Servidor MCP (Model Context Protocol) para asistentes de IA (Claude Desktop, Le Chat, Cursor, ChatGPT): consulta la API REST del Orchestrator, ejecuta comandos `show ...` mediante la API del Orchestrator o SSH opcional, y aplica cambios con dry-run, whitelist y audit log. Incluye panel de administración web y updater web. | [ec-mcp/README.md](ec-mcp/README.md) |

## ec-mcp — MCP y panel de administración web

Versión estable en `main`: **6.0.0**. Incorpora la capa de telemetría del PR #70: KPIs de infraestructura del Orchestrator (`get_orchestrator_infrastructure`, `get_appliance_infrastructure`) y estadísticas real-time del appliance vía el proxy SD-WAN (`get_realtime_stats`, `get_appliance_health`). La referencia fija de la base anterior es la rama `release/4.5.0`. La referencia exhaustiva está en [ec-mcp/README.md](ec-mcp/README.md) y la plantilla completa en [ec-mcp/.env.example](ec-mcp/.env.example).

> **Regla principal:** `ec-mcp/.env` es la única fuente de configuración. No dupliques las credenciales del Orchestrator en el JSON del cliente MCP ni declares `EC_ADMIN_PORT` o `EC_ADMIN_PASSWORD` directamente en systemd. Cada variable debe aparecer una sola vez en `.env`.

### Instalación limpia en Linux

Requiere Ubuntu/Debian con Python 3.12 o superior:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl

git clone --branch release/4.5.0 https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
./scripts/install.sh --non-interactive

cp -n .env.example .env
nano .env
```

Configura como mínimo estos valores. No dejes espacios alrededor de `=` ni repitas claves:

```dotenv
# Orchestrator: usa API key o usuario/contraseña.
EC_ORCHESTRATOR_URL=https://TU-ORCHESTRATOR-REAL
EC_ORCHESTRATOR_API_KEY=  # gitleaks:allow; pega aquí la API key
EC_ORCHESTRATOR_USER=
EC_ORCHESTRATOR_PASSWORD=  # gitleaks:allow
EC_VERIFY_TLS=true

# SSH permanece deshabilitado si sólo usarás el API del Orchestrator.
EC_SSH_ENABLED=false
EC_SSH_USER=
EC_SSH_PASSWORD=  # gitleaks:allow
EC_SSH_PORT=22

# Escrituras deshabilitadas hasta habilitarlas expresamente.
EC_ALLOW_WRITE_TOOLS=false
EC_ALLOW_DANGEROUS_WRITES=false
EC_MCP_AUDIT_LOG=logs/mcp-audit.jsonl

# Transporte MCP remoto. Genera un token aleatorio para producción.
EC_MCP_AUTH_TOKEN=  # gitleaks:allow; genera un token aleatorio
EC_MCP_HOST=0.0.0.0
EC_MCP_PORT=8000
EC_MCP_ALLOWED_HOSTS=mcp.example.com
EC_MCP_JSON_RESPONSE=true
EC_MCP_STATELESS=false

# Panel web administrativo.
EC_ADMIN_HOST=0.0.0.0
EC_ADMIN_PORT=9090
EC_ADMIN_PASSWORD=  # gitleaks:allow; define una contraseña fuerte
EC_ADMIN_LOGIN_MAX_FAILURES=5
EC_ADMIN_LOGIN_WINDOW_SECONDS=60

# Updater web. Para repositorios privados, configura usuario y token.
EC_UPDATE_ALLOW_WEB=true
EC_UPDATE_REPOSITORY=Ryuz-crypto/APIIntegration
EC_UPDATE_BRANCH=main
EC_UPDATE_GITHUB_USER=
EC_UPDATE_GITHUB_TOKEN=  # gitleaks:allow
EC_UPDATE_STATE_DIR=/var/lib/ec-mcp-update
EC_UPDATE_SERVICE_NAME=ec-mcp.service
EC_UPDATE_ADMIN_SERVICE_NAME=ec-mcp-admin.service
```

Genera secretos largos, por ejemplo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

La plantilla contiene variables adicionales de timeouts, caché, API, SSH y updater. Revisa [ec-mcp/.env.example](ec-mcp/.env.example) antes de arrancar.

### Instalar los servicios

```bash
cd ~/APIIntegration/ec-mcp
./scripts/install_service.sh
./scripts/install_admin_service.sh --port 9090

sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
systemctl --no-pager status ec-mcp ec-mcp-admin
sudo ss -lntp | grep -E ':(8000|9090)\b'
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1:9090/login
```

Desde **3.0.0b3**, `install_admin_service.sh` conserva el puerto definido en `.env`; `--port` lo actualiza explícitamente. El panel queda en `http://IP-DEL-SERVIDOR:9090`.

### Configuración del cliente MCP local (stdio)

El cliente sólo necesita la ruta al archivo `.env`. Sustituye `TU-USUARIO` por el usuario Linux real:

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

No coloques `EC_ORCHESTRATOR_API_KEY`, contraseñas ni tokens directamente en este JSON.

Para un conector remoto usa `https://TU-HOST/mcp` y el Bearer token definido en `EC_MCP_AUTH_TOKEN`. La publicación TLS/ZTNA/nginx está explicada en [ec-mcp/README.md](ec-mcp/README.md).

### Actualizar servidores anteriores a 4.5.0

Aplica a instalaciones 2.x, 3.x y 4.0.x. Usa Python 3.12+, termina las operaciones ZTP/BIO en curso y respalda `.env`, configuración administrativa, logs y estado ZTP antes de reiniciar. La guía con respaldo, comprobaciones y recuperación está en [Upgrade por terminal](ec-mcp/README.md#upgrade-por-terminal).

Con el checkout limpio, actualiza a la referencia estable:

```bash
cd ~/APIIntegration
git status --short
git fetch origin
git switch --detach origin/release/4.5.0
cd ec-mcp
./scripts/install.sh --non-interactive
# Solo si ya utilizas estos servicios; conserva los puertos de .env.
./scripts/install_service.sh
./scripts/install_admin_service.sh
sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
./.venv/bin/python -c "import ec_mcp; assert ec_mcp.__version__ == '4.5.0'; print(ec_mcp.__version__)"
git rev-parse HEAD
```

No continúes si hay cambios locales sin respaldar. El instalador conserva `.env` e instala las dependencias fijadas en `requirements-stable.txt`, incluidas las herramientas de QA; no copia encima la plantilla. Para instalaciones stdio, reinicia el cliente MCP al terminar. No se requiere actualizar firmware del Orchestrator ni de los appliances.

### Mejoras de operación e inconsistencias

La base estable integra las correcciones existentes del PR #37 y alinea paquete, README y CI en 4.5.0. Las siguientes mejoras se desarrollan por separado en `fix/operation-integrity-4.5`: evitar repetir escrituras ante respuestas vacías, verificar ZTP con evidencia completa e inventario fresco, aplicar los mismos controles CLI en todas las rutas y distinguir escritura aplicada de verificación fallida. El endurecimiento SSH/updater y las inconsistencias del dashboard continúan pendientes de esa línea de trabajo.

### Validación y errores comunes

Comprueba claves duplicadas sin mostrar los secretos:

```bash
cd ~/APIIntegration/ec-mcp
cut -d= -f1 .env | sed 's/^export //' | grep '^EC_' | sort | uniq -d
grep -nE '^(EC_ADMIN_HOST|EC_ADMIN_PORT|EC_ADMIN_LOGIN_MAX_FAILURES|EC_ADMIN_LOGIN_WINDOW_SECONDS)=' .env
sudo systemctl cat ec-mcp-admin
sudo systemctl show ec-mcp-admin -p Environment -p WorkingDirectory --no-pager
```

- Si el primer comando imprime una clave, elimínala hasta dejar una sola definición.
- Si systemd muestra `Environment=EC_ADMIN_PORT=8080`, esa variable prevalece sobre `.env`. Reinstala el servicio con el script de 3.0.0b3 o elimina el override.
- Si el puerto correcto abre pero rechaza la contraseña, busca varias líneas `EC_ADMIN_PASSWORD=`; conserva exactamente una y reinicia `ec-mcp-admin`.
- Después de demasiados intentos, espera el valor de `EC_ADMIN_LOGIN_WINDOW_SECONDS` o reinicia el servicio una vez corregida la contraseña.
- `run_show_api(command="show arp", appliance_id="0.NE")` usa el API del Orchestrator. No requiere habilitar SSH ni usar `run_show_command`.

Guía completa de variables, seguridad, updater, HTTP/SSE, systemd y nginx: [ec-mcp/README.md](ec-mcp/README.md).

## Licencia

ec-mcp se distribuye bajo una **licencia de uso restringido**: evaluación, estudio y uso interno. Comercialización, copia fuera de la instalación/respaldo y redistribución requieren autorización escrita. Los derechos de terceros y los permisos de versiones anteriores se conservan. Esta licencia no es MIT.

Consulta el texto completo en [LICENSE](LICENSE).

## Donaciones

```text
╭────────────────────────────────────────────────────────╮
│                                                      │
│              ♥  APOYA EC-MCP  ♥                      │
│                                                      │
│   Si este proyecto te ahorra tiempo o te ayuda a     │
│   mostrar el potencial de las APIs de EdgeConnect,   │
│   considera apoyar su desarrollo y mantenimiento.    │
│                                                      │
│          Donaciones: decameru@outlook.com            │
│                                                      │
╰────────────────────────────────────────────────────────╯
```

Para conocer los medios de donación disponibles, escribe a [decameru@outlook.com](mailto:decameru@outlook.com).

## Contacto

Consultas, soporte, propuestas y donaciones:

**[decameru@outlook.com](mailto:decameru@outlook.com)**
