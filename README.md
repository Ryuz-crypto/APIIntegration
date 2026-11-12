# APIIntegration — ec-mcp

[![ec-mcp](https://img.shields.io/badge/ec--mcp-9.5.0%20audit--readiness-7B61FF)](ec-mcp/README.md)
[![Human Verified](https://img.shields.io/badge/human--verified-%E2%9C%93-2EA44F)](SECURITY.md)
[![ec-mcp CI](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml)
[![Licencia restringida](https://img.shields.io/badge/licencia-uso_restringido-blue.svg)](LICENSE)

Servidor **MCP (Model Context Protocol)** para descubrir, consultar y operar entornos **HPE Aruba Networking EdgeConnect SD-WAN** desde asistentes de IA, mediante la API REST del Orchestrator, comandos `show` y un panel de administración web.

## ec-mcp — MCP y panel de administración web

Versión en `main`: **9.5.0**. La validación de esta versión en el servidor real queda pendiente. Referencia exhaustiva en [ec-mcp/README.md](ec-mcp/README.md) y plantilla completa en [ec-mcp/.env.example](ec-mcp/.env.example).

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

### Actualizar a la versión más reciente de `main`

Este procedimiento actualiza una instalación existente; conserva `.env` y no reinstala las unidades de systemd. Ejecuta los bloques **en orden** y detente si algún comando falla.

**1. Confirma la carpeta y revisa cambios locales.** Sustituye la ruta si tu instalación está en otro lugar:

```bash
cd ~/APIIntegration
pwd -P
git status -sb
sudo systemctl show ec-mcp-admin -p WorkingDirectory -p ExecStart --no-pager
sudo systemctl show ec-mcp -p WorkingDirectory -p ExecStart --no-pager
```

Las rutas `WorkingDirectory` y `ExecStart` deben apuntar a la instalación que vas a actualizar, normalmente `APIIntegration/ec-mcp` y su `.venv`. Si no coinciden, detente y localiza la instalación usada por los servicios. Si `git status` muestra cambios locales o archivos sin seguimiento, respáldalos o revísalos antes de continuar; no uses `git reset --hard`.

**2. Respalda configuración y estado.** Este respaldo contiene secretos; mantenlo privado:

```bash
umask 077
mkdir -p "$HOME/ec-mcp-backups"
QA_BACKUP_DIR="$(mktemp -d "$HOME/ec-mcp-backups/actualizacion-XXXXXXXX")"
git rev-parse HEAD > "$QA_BACKUP_DIR/commit-anterior.txt"
for item in .env .ec-admin.json .ec-admin-pass .ec-admin-backups logs; do
  if [ -e "ec-mcp/$item" ]; then cp -a "ec-mcp/$item" "$QA_BACKUP_DIR/"; fi
done
printf 'Respaldo: %s\n' "$QA_BACKUP_DIR"
```

Respalda también las rutas externas de configuración, registro, auditoría y estado ZTP que uses. Los planes en memoria pueden perderse al reiniciar; termina o documenta las operaciones pendientes antes de actualizar.

**3. Descarga `main` y actualiza el paquete.**

```bash
git fetch origin
git switch main
git merge --ff-only origin/main
git rev-parse HEAD
cd ec-mcp
./.venv/bin/pip install -r requirements-stable.txt -e .
./.venv/bin/python -c "import ec_mcp, ec_mcp.admin_page; print('Versión:', ec_mcp.__version__); print('Panel:', ec_mcp.admin_page.__file__)"
```

Si `git switch` o `git merge --ff-only` falla, **detente**: puede haber cambios locales o commits divergentes. No fuerces el cambio; revisa la situación y conserva tu respaldo. La ruta impresa del panel debe pertenecer a la carpeta verificada en el paso 1.

**4. Reinicia y verifica.** El reinicio interrumpe brevemente ambos servicios:

```bash
sudo systemctl restart ec-mcp ec-mcp-admin
systemctl is-active ec-mcp ec-mcp-admin
git rev-parse --short HEAD
sudo journalctl -u ec-mcp-admin -n 30 --no-pager
```

Ambos servicios deben indicar `active`. Accede al panel con el puerto que ya tienes configurado y recarga el navegador con `Ctrl+F5`. Confirma también la build servida mediante `orchestrator_info()` desde el cliente MCP: la versión puede permanecer igual entre commits, por lo que es importante comparar el SHA. Si una unidad no existe o un servicio no arranca, revisa su `systemctl status` y journal antes de hacer más cambios.

Para una guía de respaldo y recuperación más amplia, consulta [Upgrade por terminal](ec-mcp/README.md#upgrade-por-terminal).

### Reporte de bugs

Los fallos se registran en [GitHub Issues](https://github.com/Ryuz-crypto/APIIntegration/issues) buscando duplicados primero; el número del issue (`#123`) es su **Bug ID** y se enlaza desde el PR de corrección. Usa la [plantilla de reporte](.github/ISSUE_TEMPLATE/bug_report.md) y excluye secretos y datos sensibles. Reglas para asistentes de IA: [AGENTS.md](AGENTS.md).

### Referencias

- Documentación completa (variables, seguridad, updater, HTTP/SSE, systemd, nginx): [ec-mcp/README.md](ec-mcp/README.md)
- Seguridad y reporte de vulnerabilidades: [SECURITY.md](SECURITY.md)

## Licencia

Uso restringido: evaluación, estudio y uso interno. Comercialización, copia fuera de la instalación/respaldo y redistribución requieren autorización escrita. Texto completo en [LICENSE](LICENSE).

## Contacto

Consultas, soporte y propuestas: [decameru@outlook.com](mailto:decameru@outlook.com)
