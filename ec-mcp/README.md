# ec-mcp — EdgeConnect SD-WAN MCP server

**Versión 3.0 base: 3.0.0b2**  
Esta entrega inicia la línea 3.0. La base 2.0.0 fue la versión estable anterior; 3.0.0b2 incorpora el control plane web y prepara el flujo ZTP.

`ec-mcp` conecta asistentes compatibles con Model Context Protocol (MCP) con
HPE Aruba Networking EdgeConnect SD-WAN. Puede consultar el Orchestrator y los
appliances mediante sus APIs oficiales y, de forma opcional, ejecutar el
catálogo ECOS por SSH.

## Qué incluye

- Compatibilidad con perfiles API de Orchestrator 9.3–9.6; versiones 9.7 usan
  automáticamente el perfil compatible 9.6.
- Inventario, alarmas, salud WAN, MOS, túneles, HA, brownouts, ZTP, firmware,
  top talkers y métricas del Orchestrator.
- `run_show_api`: ejecuta comandos `show` de solo lectura mediante el API del
  appliance a través del Orchestrator. No requiere SSH.
- `run_show_command` y `run_cli_command`: acceso ECOS opcional por SSH.
- Escrituras desactivadas por defecto, dry-run, confirmación explícita, límite
  de frecuencia y segundo candado para operaciones peligrosas.
- Transporte stdio, HTTP streamable y SSE con bearer token.
- Registro de auditoría JSONL y redacción de secretos.
- Panel administrativo 3.0 para gestionar Orchestrators, editar todas las variables permitidas y aplicar cambios sin entrar por SSH.
- Updater web con detección de GitHub público o privado, commit exacto, pruebas, respaldo y rollback.
- Roadmap ZTP visible y bloqueado: `discover → template → adoptar → preview/diff → confirmar y aplicar`.

## Herramientas MCP

| Grupo | Herramientas |
|---|---|
| Descubrimiento | `orchestrator_info`, `list_appliances`, `list_api_operations`, `orchestrator_metrics` |
| Estado operativo | `get_wan_health`, `get_mos`, `get_tunnel_state`, `get_brownout_state`, `get_availability`, `get_top_talkers`, `get_active_alarms`, `get_ha_status`, `get_firmware_compliance`, `get_ztp_status` |
| API genérica | `call_read_api`, `apply_change` |
| CLI | `list_cli_commands`, `run_show_api`, `run_show_command`, `run_cli_command` |

`run_show_api` usa el Orchestrator como transporte:

```text
run_show_api(command="show arp", appliance_id="0.NE")
```

Una respuesta correcta incluye `"transport": "orchestrator"`. Este flujo no
usa SSH. `appliance_id` acepta nePk, nombre, IP o serial del appliance.

## Requisitos

- Linux recomendado: Ubuntu/Debian.
- Python 3.12 o superior.
- Git.
- Acceso HTTPS al Orchestrator.
- API key, o usuario y contraseña del Orchestrator.
- SSH solo si se usarán `run_show_command` o `run_cli_command`.

## Instalación recomendada

### 1. Clonar la versión estable

```bash
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration
git checkout main
cd ec-mcp
```

El checkout de `main` permite recibir futuras actualizaciones estables mediante
`./scripts/update.sh --daemon`.

### 2. Ejecutar el instalador

```bash
./scripts/install.sh
```

El instalador crea `.venv`, instala el paquete, solicita la configuración y
genera `.env`. Es idempotente y no reemplaza un `.env` existente.

### 3. Instalar el servicio MCP

```bash
./scripts/install_service.sh
sudo systemctl enable --now ec-mcp
systemctl status ec-mcp
curl http://127.0.0.1:8000/health
```

Para instalar el panel administrativo y el updater web:

```bash
./scripts/install_admin_service.sh
systemctl status ec-mcp-admin
systemctl status ec-mcp-update.timer
```

El instalador habilita ambos servicios. A partir de ese momento la configuración
y las actualizaciones se administran en `http://<servidor>:8080`; no es
necesario entrar por SSH para cambiar el `.env` o aplicar una publicación.

Define una contraseña fuerte en `.env` antes de exponer el panel:

```dotenv
EC_ADMIN_PASSWORD=example
```

## Instalación manual

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip

git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .

cp .env.example .env
chmod 600 .env
```

Edita `.env` y configura, como mínimo:

```dotenv
EC_ORCHESTRATOR_URL=https://orchestrator.example.com
EC_ORCHESTRATOR_API_KEY=  # pega aquí la API key
EC_VERIFY_TLS=true
```

Nunca subas `.env` al repositorio.

## Autenticación del Orchestrator

Elige uno de estos métodos:

### API key — recomendado

```dotenv
EC_ORCHESTRATOR_URL=https://orchestrator.example.com
EC_ORCHESTRATOR_API_KEY=TU-API-KEY
```

### Usuario y contraseña

```dotenv
EC_ORCHESTRATOR_URL=https://orchestrator.example.com
EC_ORCHESTRATOR_USER=usuario
EC_ORCHESTRATOR_PASSWORD=contraseña
```

Si se configuran ambos métodos, se usa la API key. Para cuentas con OTP/2FA,
usa una API key; un OTP de un solo uso no sirve para automatización.

## Modos de ejecución

### stdio

Para clientes locales como Claude Desktop o Cursor:

```bash
ec-mcp
```

Ejemplo de configuración:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "/ruta/APIIntegration/ec-mcp/.venv/bin/ec-mcp",
      "env": {
        "EC_MCP_ENV_FILE": "/ruta/APIIntegration/ec-mcp/.env"
      }
    }
  }
}
```

### HTTP streamable

```bash
ec-mcp http --host 127.0.0.1 --port 8000
```

Requiere `EC_MCP_AUTH_TOKEN` de al menos 32 bytes aleatorios:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Cliente remoto:

```text
URL: https://mcp.example.com/mcp
Authorization: Bearer <EC_MCP_AUTH_TOKEN>
```

`/health` es público para probes. `/mcp` requiere bearer token.

### SSE heredado

```bash
ec-mcp sse --host 127.0.0.1 --port 8000
```

### Panel administrativo 3.0

```bash
ec-mcp admin
```

El panel usa `EC_ADMIN_HOST`, `EC_ADMIN_PORT` y
`EC_ADMIN_PASSWORD`. La pestaña **Variables** presenta la lista blanca
completa de parámetros de Orchestrator, SSH opcional, seguridad, transporte,
panel y updater. Los secretos se guardan con permisos `600`, se muestran sólo
como “configurado” y un campo secreto vacío conserva el valor existente.

**Guardar variables** actualiza `.env` de forma atómica. **Guardar y reiniciar
servicios** crea una solicitud que procesa el worker privilegiado; el proceso
web nunca ejecuta Git, pip ni systemctl directamente.

## Archivo de configuración y precedencia

Al iniciar, el servidor busca variables en este orden:

1. Variables ya definidas en el proceso o en systemd.
2. Archivo indicado por `EC_MCP_ENV_FILE`.
3. `.env` del directorio de trabajo.
4. `.env` junto a la instalación del paquete.

Una variable ya presente en el proceso no es reemplazada por el archivo.

## Referencia completa de variables

### Orchestrator

| Variable | Predeterminado | Requerida | Uso |
|---|---:|---|---|
| `EC_ORCHESTRATOR_URL` | vacío | Sí | URL base HTTPS del Orchestrator, sin `/` final. |
| `EC_ORCHESTRATOR_API_KEY` | vacío | Una opción | Token enviado como `X-Auth-Token`; método recomendado. |
| `EC_ORCHESTRATOR_USER` | vacío | Una opción | Usuario para login cuando no se usa API key. |
| `EC_ORCHESTRATOR_PASSWORD` | vacío | Con usuario | Contraseña del usuario del Orchestrator. |
| `EC_VERIFY_TLS` | `true` | No | Verifica el certificado TLS. Usa `false` únicamente en un laboratorio controlado. |

### SSH opcional a appliances

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_SSH_ENABLED` | `false` | Habilita las herramientas SSH. No afecta `run_show_api`. |
| `EC_SSH_HOST` | vacío | Host predeterminado. Si está vacío, se intenta resolver desde el inventario del Orchestrator. |
| `EC_SSH_USER` | vacío | Usuario SSH común. |
| `EC_SSH_PASSWORD` | vacío | Contraseña SSH. |
| `EC_SSH_ENABLE_PASSWORD` | vacío | Contraseña de modo enable, si el appliance la solicita. |
| `EC_SSH_PORT` | `22` | Puerto SSH. |
| `EC_SSH_AUTH_METHOD` | `auto` | `auto`, `password` o `keyboard-interactive`. |

### Seguridad, límites y auditoría

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_ALLOW_WRITE_TOOLS` | `false` | Kill switch para escrituras. Aun en `true`, los cambios requieren `confirm=true`. |
| `EC_ALLOW_DANGEROUS_WRITES` | `false` | Segundo candado para reboot, delete, wipe, factory, shutdown y operaciones equivalentes. |
| `EC_MAX_WRITES_PER_MINUTE` | `10` | Límite de operaciones de escritura por minuto. |
| `EC_MAX_OUTPUT_CHARS` | `12000` | Tamaño máximo de respuesta antes del envoltorio de truncado seguro. |
| `EC_API_CACHE_TTL` | `30` | Duración de caché API en segundos; admite decimales. |
| `EC_MCP_AUDIT_LOG` | `logs/mcp-audit.jsonl` | Ruta del registro de auditoría JSONL. |
| `EC_MCP_PROFILES_DIR` | perfiles incluidos | Directorio alternativo de perfiles de compatibilidad. |

### Transporte y proceso

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_MCP_ENV_FILE` | búsqueda automática | Ruta explícita al archivo `.env`. |
| `EC_MCP_AUTH_TOKEN` | vacío | Bearer token obligatorio para HTTP/SSE; mínimo 32 bytes aleatorios. |
| `EC_MCP_HOST` | `127.0.0.1` | Dirección de escucha HTTP/SSE. |
| `EC_MCP_PORT` | `8000` | Puerto HTTP/SSE. |
| `EC_MCP_ALLOWED_HOSTS` | vacío | Hosts públicos separados por coma para protección contra DNS rebinding; incluye puerto si el cliente lo envía. |
| `EC_MCP_JSON_RESPONSE` | `true` | Responde POST con JSON plano; usa `false` para SSE estricto. |
| `EC_MCP_STATELESS` | `false` | Elimina `Mcp-Session-Id` cuando está en `true`. |
| `EC_MCP_BUILD_COMMIT` | HEAD local | Identidad de commit para wheels/containers sin directorio `.git`. |

### Panel administrativo

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_ADMIN_HOST` | `0.0.0.0` | Dirección de escucha del panel. Usa `127.0.0.1` si no debe aceptar conexiones remotas. |
| `EC_ADMIN_PORT` | `8080` | Puerto del panel. |
| `EC_ADMIN_PASSWORD` | vacío | Contraseña del panel. Es obligatoria si se expone fuera de loopback. |
| `EC_ADMIN_LOGIN_MAX_FAILURES` | `5` | Fallos permitidos por IP antes del bloqueo temporal. |
| `EC_ADMIN_LOGIN_WINDOW_SECONDS` | `60` | Duración de la ventana de bloqueo; una contraseña correcta desbloquea inmediatamente. |
| `EC_ADMIN_PASSWORD_FILE` | `.ec-admin-pass` | Archivo alternativo para almacenar la contraseña del primer inicio. |
| `EC_ADMIN_STORE` | `.ec-admin.json` | Almacén de configuraciones de Orchestrators. |

### Actualizaciones web

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_UPDATE_ALLOW_WEB` | `true` | Habilita detección, actualización y reinicio desde el panel. |
| `EC_UPDATE_REPOSITORY` | `Ryuz-crypto/APIIntegration` | Repositorio en formato `owner/repository`. |
| `EC_UPDATE_BRANCH` | `main` | Rama que contiene las publicaciones autorizadas. |
| `EC_UPDATE_GITHUB_USER` | vacío | Usuario de GitHub para un repositorio privado. |
| `EC_UPDATE_GITHUB_TOKEN` | vacío | Token fine-grained con lectura de Contents. Es secreto y nunca vuelve al navegador. |
| `EC_UPDATE_PROJECT_DIR` | instalación actual | Directorio de `ec-mcp`; el instalador lo completa. |
| `EC_UPDATE_STATE_DIR` | `/var/lib/ec-mcp-update` | Solicitudes, estado y respaldos del updater. |
| `EC_UPDATE_SERVICE_NAME` | `ec-mcp.service` | Servicio MCP que se reinicia después de validar. |
| `EC_UPDATE_ADMIN_SERVICE_NAME` | `ec-mcp-admin.service` | Servicio del panel administrativo. |

## Ejemplo completo de `.env`

```dotenv
EC_ORCHESTRATOR_URL=https://orchestrator.example.com
EC_ORCHESTRATOR_API_KEY=example
EC_ORCHESTRATOR_USER=
EC_ORCHESTRATOR_PASSWORD=example
EC_VERIFY_TLS=true

EC_SSH_ENABLED=false
EC_SSH_HOST=
EC_SSH_USER=
EC_SSH_PASSWORD=
EC_SSH_ENABLE_PASSWORD=
EC_SSH_PORT=22
EC_SSH_AUTH_METHOD=auto

EC_ALLOW_WRITE_TOOLS=false
EC_ALLOW_DANGEROUS_WRITES=false
EC_MAX_WRITES_PER_MINUTE=10
EC_MAX_OUTPUT_CHARS=12000
EC_API_CACHE_TTL=30
EC_MCP_AUDIT_LOG=logs/mcp-audit.jsonl
EC_MCP_PROFILES_DIR=

EC_MCP_ENV_FILE=
EC_MCP_AUTH_TOKEN=example
EC_MCP_HOST=127.0.0.1
EC_MCP_PORT=8000
EC_MCP_ALLOWED_HOSTS=
EC_MCP_JSON_RESPONSE=true
EC_MCP_STATELESS=false
EC_MCP_BUILD_COMMIT=

EC_ADMIN_HOST=127.0.0.1
EC_ADMIN_PORT=8080
EC_ADMIN_PASSWORD=  # define una contraseña fuerte
EC_ADMIN_PASSWORD_FILE=
EC_ADMIN_STORE=

EC_UPDATE_ALLOW_WEB=true
EC_UPDATE_REPOSITORY=Ryuz-crypto/APIIntegration
EC_UPDATE_BRANCH=main
EC_UPDATE_GITHUB_USER=
EC_UPDATE_GITHUB_TOKEN=
EC_UPDATE_PROJECT_DIR=
EC_UPDATE_STATE_DIR=/var/lib/ec-mcp-update
EC_UPDATE_SERVICE_NAME=ec-mcp.service
EC_UPDATE_ADMIN_SERVICE_NAME=ec-mcp-admin.service
```

No dejes `EC_MCP_PROFILES_DIR`, `EC_ADMIN_PASSWORD_FILE` o
`EC_ADMIN_STORE` definidos con valores vacíos si quieres usar sus rutas
predeterminadas; elimina esas líneas del archivo.

## Escrituras y confirmación

El servidor inicia en modo de solo lectura:

```dotenv
EC_ALLOW_WRITE_TOOLS=false
EC_ALLOW_DANGEROUS_WRITES=false
```

Para una escritura normal:

1. Define `EC_ALLOW_WRITE_TOOLS=true`.
2. La primera llamada sin confirmación devuelve el dry-run.
3. Revisa método, ruta y cuerpo.
4. Repite la llamada con `confirm=true`.

Las operaciones peligrosas también requieren
`EC_ALLOW_DANGEROUS_WRITES=true`. No habilites estos interruptores para una
cuenta del Orchestrator con privilegios que no necesitas.

## Validación

```bash
source .venv/bin/activate
python -m pytest tests -q
ec-mcp --help
```

Con el servicio activo:

```bash
curl http://127.0.0.1:8000/health
journalctl -u ec-mcp -f
```

Desde un cliente MCP:

```text
orchestrator_info()
list_appliances()
run_show_api(command="show arp", appliance_id="0.NE")
```

La última llamada debe devolver `applied: true`,
`transport: orchestrator` y la tabla ARP/NDP del appliance.

## Actualización desde la web

1. Abre **Actualizaciones** y pulsa **Detectar GitHub**.
2. Si el repositorio es privado, guarda antes `EC_UPDATE_GITHUB_USER` y
   `EC_UPDATE_GITHUB_TOKEN` en **Variables → Actualizaciones**.
3. Revisa el commit remoto y escribe la confirmación exacta
   `ACTUALIZAR <sha-corto>`.
4. Pulsa **Aplicar actualización**. El panel mostrará
   `pending`, `running`, `success` o `error`.

El worker vuelve a consultar y fija el commit, acepta sólo avance rápido,
respalda `.env`, reinstala el paquete, ejecuta todas las pruebas y reinicia
los servicios. Si la instalación o las pruebas fallan, restaura el commit
anterior y conserva el diagnóstico sanitizado en
`/var/lib/ec-mcp-update/status.json`.

No se guarda el token en la solicitud, la URL Git no contiene credenciales y
los secretos se redactan de los mensajes públicos.

## Objetivo ZTP de la línea 3.0

La pestaña **ZTP** documenta el flujo que construiremos sobre esta base:

```text
discover → seleccionar template → validar parámetros → adoptar
         → preview/diff → confirmar → aplicar → health check/rollback
```

En `3.0.0b2` esas acciones están intencionalmente bloqueadas: esta entrega
implementa la administración y el canal seguro de actualización, no activa aún
la adopción ni el planchado de configuración.

## Solución de problemas

| Síntoma | Revisión |
|---|---|
| `Orchestrator is not configured` | Define `EC_ORCHESTRATOR_URL` y una API key o usuario/contraseña. |
| HTTP 401 del Orchestrator | Revisa la API key o credenciales. |
| HTTP 401 en `/mcp` | Revisa el header Bearer y `EC_MCP_AUTH_TOKEN`. |
| HTTP 421 detrás de proxy | Añade el host público exacto a `EC_MCP_ALLOWED_HOSTS`. |
| Error TLS | Instala la CA correcta. Usa `EC_VERIFY_TLS=false` solo para diagnóstico en laboratorio. |
| Herramientas SSH deshabilitadas | Define `EC_SSH_ENABLED=true` y las credenciales SSH. |
| `run_show_api` falla | Confirma el nePk con `list_appliances` y la conectividad del appliance desde el Orchestrator. |
| Panel muestra `Demasiados intentos` | Espera el tiempo mostrado o inicia sesión con la contraseña correcta; desde 3.0.0b2 un login válido limpia inmediatamente el bloqueo. |
| systemd no toma cambios | Ejecuta `sudo systemctl daemon-reload && sudo systemctl restart ec-mcp`. |

## Seguridad operativa

- Usa una API key de solo lectura para observabilidad.
- Protege `.env` con permisos `600`.
- No publiques el puerto 8000 directamente en Internet; usa TLS mediante
  reverse proxy o ZTNA.
- Mantén el bearer token aunque la capa ZTNA autentique al usuario.
- Revisa `EC_MCP_AUDIT_LOG` y rota el archivo según tu política.
- El MCP añade controles, pero los permisos efectivos siguen siendo los de la
  cuenta configurada en el Orchestrator o appliance.

Ejemplos de Nginx y systemd están en [`packaging/`](packaging/).

## Desarrollo y QA

```bash
python -m pytest tests -q
ruff check ec_mcp tests
bandit -r ec_mcp -q
```

CI ejecuta pruebas, smoke test MCP, Ruff, Bandit, pip-audit y gitleaks.

## Licencia

Consulta [`LICENSE`](../LICENSE).
