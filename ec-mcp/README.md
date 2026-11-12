# ec-mcp — EdgeConnect SD-WAN MCP server

**Versión: 9.4.0** en `main`. La validación de esta versión en el entorno real queda pendiente. La [preparación de auditoría](docs/AUDITORIA-9.2.md) no implementa ni certifica no repudio.

El panel usa HTTP por defecto (`EC_ADMIN_TLS_ENABLED=false`). Si ya configuraste `true`, se respeta esa elección. HTTP no cifra las credenciales del panel; habilita HTTPS cuando dispongas de certificados o uses un proxy TLS. Esta opción es independiente de la verificación TLS de Orchestrators y SSE.

Para agregar un destino desde Orquestadores o SSE, completa sus datos y usa **Guardar y activar**: el panel guarda el registro y solicita un reinicio del MCP para cargar los destinos. El reinicio aplica todos los cambios pendientes y puede cambiar la selección automática si no existe un destino predeterminado explícito; fija el destino deseado con **Por defecto** cuando utilices varios. **Guardar** permite posponer el reinicio. La opción **Aplicar a .env** sigue destinada a cambiar la configuración global del destino seleccionado.

Estado actual: **9.4.0 estable** en `main`. Esta línea concentra el soporte vigente y añade: retiro del componente DashboardAPI-EC (el repositorio se enfoca en `ec-mcp`), multi-Orchestrator y multi-SSE (multi-tenant), estado real de servicios en el panel con auditoría estructurada (#88 Fases 1–3: SSH fiable, sondas reales de servicios, detección y remediación asistida con propuestas dry-run).

Esta entrega añade la capa de telemetría (PR #70): KPIs de infraestructura del Orchestrator (platform info, GMS server, disco, particiones BD, stats collectors), KPIs por appliance desde el Orchestrator (CPU/performance timeseries, interface state) y estadísticas real-time del appliance (`POST /stats/realtimeStats`, `POST /health`, disk usage) a través del proxy `/appliance/rest`, que alcanza los equipos por la red gestionada SD-WAN sin acceso WAN directo.

Esta entrega consolida lo existente, incluido el PR #37: creación ZTP con `preConfig`, denegación con el ID numérico descubierto y auditoría de cuerpos JSON tipo lista. Instala dependencias fijadas para runtime y QA; CI valida que la versión instalada, el código y `pyproject.toml` coincidan. Los esquemas del catálogo son referencias: algunos endpoints aún contienen placeholders y requieren validar el contrato antes de una escritura.

`ec-mcp` conecta asistentes compatibles con Model Context Protocol (MCP) con
HPE Aruba Networking EdgeConnect SD-WAN. Puede consultar el Orchestrator y los
appliances mediante sus APIs oficiales y, de forma opcional, ejecutar el
catálogo ECOS por SSH.

## Qué incluye

- Compatibilidad con perfiles API de Orchestrator 9.3–9.6; versiones 9.7 usan
  automáticamente el perfil compatible 9.6.
- Multi-Orchestrator y multi-SSE: N Orchestrators y N plataformas SSE gestionados
  desde el panel; las tools aceptan `target` opcional.
- Detección de incidentes y remediación asistida: `correlate_incidents` y
  `propose_remediation` (propuestas dry-run con evidencia, alcance, riesgo y
  plan de reversión; nunca aplican por sí mismas).
- Inventario, alarmas, salud WAN, MOS, túneles, HA, brownouts, ZTP, firmware,
  top talkers y métricas del Orchestrator.
- `run_show_api`: ejecuta comandos `show` de solo lectura mediante el API del
  appliance a través del Orchestrator. No requiere SSH.
- `run_show_command` y `run_cli_command`: acceso ECOS opcional por SSH.
- Escrituras desactivadas por defecto, dry-run, confirmación explícita, límite
  de frecuencia y segundo candado para operaciones peligrosas.
- Transporte stdio, HTTP streamable y SSE con bearer token.
- Registro de auditoría JSONL y redacción de secretos.
- Panel administrativo para gestionar Orchestrators, editar todas las variables permitidas y aplicar cambios sin entrar por SSH.
- Updater web con detección de GitHub público o privado, commit exacto, pruebas, respaldo y rollback.
- Workflows MCP transaccionales BIO/ZTP (solo vía tools MCP; el panel web ya no incluye pestaña ZTP).
- Sección opcional de **HPE Aruba Networking Central** (nuevas familias REST API v1:
  monitoring, notifications, troubleshooting) con credenciales OAuth2 de HPE
  GreenLake: salud de sites, inventario, clientes, WLANs, alertas, eventos y
  diagnóstico en vivo (`show` commands, tests de red, bounce de puertos/PoE) bajo el mismo
  gating de escrituras y auditoría.

## Herramientas MCP
El servidor expone **142 tools**. La descripción completa de cada una (parámetros y
retorno) está disponible para el cliente MCP en `tools/list`. Resumen por dominio:

| Dominio | Tools | Qué hace |
|---|---|---|
| Inventario y API genérica | `orchestrator_info`, `list_appliances`, `orchestrator_metrics`, `list_api_operations`, `call_read_api`, `apply_change`, `list_discovered_appliances`, `list_orchestrator_targets_tool`, `list_sse_targets_tool` | Consultar inventario, métricas del Orchestrator y llamar cualquier operación del catálogo API (lectura directa; escritura con dry-run + `confirm=true`). `list_orchestrator_targets_tool`/`list_sse_targets_tool` enumeran los targets multi-tenant configurados (sin secretos). |
| Estado operativo y telemetría | `get_wan_health`, `get_mos`, `get_tunnel_state`, `get_brownout_state`, `get_availability`, `get_top_talkers`, `get_active_alarms`, `get_ha_status`, `get_firmware_compliance`, `get_orchestrator_infrastructure`, `get_appliance_infrastructure`, `get_realtime_stats`, `get_appliance_health`, `troubleshoot_flows`, `troubleshoot_tunnel`, `get_bgp_neighbors`, `get_deployment_config`, `get_site_to_site_tunnels`, `get_ztp_status` | Salud WAN, MOS, túneles, brownouts, alarmas, HA, firmware, KPIs de infraestructura y estadísticas real-time; troubleshooting asistido de flujos y túneles. Todas de solo lectura. |
| CLI / SSH | `list_cli_commands`, `run_show_api`, `run_show_command`, `run_cli_command`, `get_ssh_network_path`, `ensure_ssh_inbound_forwarding` | Catálogo ECOS y comandos `show` vía API del Orchestrator (sin SSH). `run_cli_command` (config) y `ensure_ssh_inbound_forwarding` son escritura con dry-run + confirmación; SSH opcional. |
| ZTP (Zero Touch Provisioning) | `prepare_ztp_adoption`, `preview_ztp_plan`, `apply_ztp_plan`, `verify_ztp_plan`, `rollback_ztp_plan`, `get_ztp_apply_status`, `prepare_bulk_ztp_adoption`, `apply_bulk_ztp_plan`, `list_bulk_ztp_plans` | Adopción transaccional de appliances: prepara/valida (nunca escribe), preview, aplica con confirmación escrita, verifica y revierte. Incluye planes bulk. |
| Overlays / BIO | `list_overlay_sources`, `prepare_overlay_clone`, `preview_overlay_plan`, `apply_overlay_plan`, `verify_overlay_plan`, `rollback_overlay_plan` | Clonación y despliegue transaccional de overlays/BIO: diff, plan inmutable, confirmación exacta y rollback. |
| Seguridad e incidentes | `get_ids_ips_state`, `get_ids_ips_events`, `get_security_log`, `get_zone_matrix`, `get_ddos_status`, `get_sse_status`, `get_security_posture`, `correlate_incidents`, `propose_remediation`, `list_response_options`, `block_threat` | Postura IDS/IPS, logs de seguridad, matriz de zonas, DDoS e integraciones SSE. `correlate_incidents` detecta y prioriza; `propose_remediation` genera propuestas **dry-run** con evidencia/alcance/riesgo/reversión (nunca aplica); `block_threat` aplica bloqueos con `confirm=true`. |
| SSE — Axis Security (55 tools) | `axis_health`, `axis_list_tags`, `axis_get_tag`, `axis_create_tag`, `axis_update_tag`, `axis_delete_tag`, `axis_list_applications`, `axis_get_application`, `axis_create_application`, `axis_update_application`, `axis_delete_application`, `axis_list_connectors`, `axis_get_connector`, `axis_connector_status`, `axis_create_connector`, `axis_update_connector`, `axis_delete_connector`, `axis_regenerate_connector`, `axis_list_connector_zones`, `axis_get_connector_zone`, `axis_create_connector_zone`, `axis_update_connector_zone`, `axis_delete_connector_zone`, `axis_list_ip_categories`, `axis_get_ip_category`, `axis_create_ip_category`, `axis_delete_ip_category`, `axis_list_web_categories`, `axis_get_web_category`, `axis_create_web_category`, `axis_delete_web_category`, `axis_list_ssl_exclusions`, `axis_create_ssl_exclusion`, `axis_delete_ssl_exclusion`, `axis_list_groups`, `axis_create_group`, `axis_delete_group`, `axis_list_users`, `axis_get_user`, `axis_create_user`, `axis_delete_user`, `axis_list_locations`, `axis_get_location`, `axis_create_location`, `axis_delete_location`, `axis_list_sub_locations`, `axis_create_sub_location`, `axis_delete_sub_location`, `axis_list_tunnels`, `axis_tunnel_status`, `axis_create_tunnel`, `axis_delete_tunnel`, `axis_list_certificates`, `axis_list_ipsec_locations`, `axis_commit` | Gestión completa de Axis Security: tags, aplicaciones, connectors (+zonas, regeneración), categorías IP/web, exclusiones SSL, grupos, usuarios, locations/sub-locations, túneles IPsec, certificados, estado de salud/commit. Cada herramienta acepta `target` opcional (multi-tenant); las `axis_create/update/delete/regenerate/commit` requieren permisos de escritura. |
| Aruba Central (17 tools) | `central_status`, `list_central_targets_tool`, `central_get_sites`, `central_get_devices`, `central_get_device_details`, `central_get_device_trends`, `central_get_clients`, `central_get_client_analytics`, `central_get_wlans`, `central_get_gateway_cluster`, `central_get_alerts`, `central_get_events`, `central_list_show_commands`, `central_run_show_commands`, `central_run_network_test`, `central_bounce_port`, `central_get_task_result` | HPE Aruba Networking Central (nuevas familias REST API v1): salud de sites, inventario APs/switches/gateways, tendencias, clientes, analytics de clientes (uso, top, trend, roaming, onboarding), WLANs, clusters de gateways, alertas y eventos. Diagnóstico en vivo: catálogo y ejecución de comandos `show`, tests de red (ping/traceroute/nslookup/tcp/http/https), bounce de puertos/PoE y consulta de tareas asíncronas. `central_run_show_commands`, `central_run_network_test` y `central_bounce_port` son escritura con dry-run + `confirm=true` bajo `EC_ALLOW_WRITE_TOOLS`. Sección desactivada por defecto (`EC_CENTRAL_ENABLED`). |
| SD-WAN AI (Orchestrator 10.0) | `ask_sdwan_ai`, `get_sdwan_ai_chat_logs`, `clear_sdwan_ai_context`, `get_sase_copilot_status` | Conversación con la SD-WAN AI embebida del Orchestrator: preguntar, leer logs del chat, limpiar contexto y consultar estado del copiloto SASE. |
| Dashboard NOC | `dashboard_snapshot`, `dashboard_render`, `dashboard_remote_config`, `dashboard_deploy_remote`, `dashboard_remote_status`, `dashboard_refresh_remote` | Snapshots y render del dashboard NOC; despliegue remoto opcional vía SSH (escritura, confirmación). |

Total: **142 tools**.

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
git clone --branch main https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
```

La rama `main` identifica la base estable vigente. El updater web puede fijar un commit concreto de `main` después de ejecutar las pruebas y validar el resultado.

### 2. Ejecutar el instalador

```bash
./scripts/install.sh
```

El instalador crea `.venv`, instala el paquete, solicita la configuración y
genera `.env`. Es idempotente y no reemplaza un `.env` existente. En la versión estable vigente,
el paso final instala y habilita los servicios systemd (`ec-mcp` y, si
`EC_ADMIN_PASSWORD` está configurado, `ec-mcp-admin`) con `systemctl enable --now`:
arrancan automáticamente al reiniciar el servidor y se reinician solos ante
fallos (`Restart=on-failure`).

### 3. Instalar el servicio MCP

Este paso ya lo ejecuta `install.sh` automáticamente; queda documentado
para reinstalaciones manuales.

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

El puerto sigue esta prioridad: `--port`, variable exportada en el proceso, valor `EC_ADMIN_PORT` de `.env` y finalmente `8080`. Reinstalar el servicio conserva el puerto guardado en `.env`.

El instalador habilita ambos servicios. A partir de ese momento la configuración
y las actualizaciones se administran en
`http://<servidor>:<EC_ADMIN_PORT>` (por ejemplo, puerto `9090`); no es
necesario entrar por SSH para cambiar el `.env` o aplicar una publicación.

Define una contraseña fuerte y el puerto deseado en `.env` antes de exponer
el panel:

```dotenv
EC_ADMIN_HOST=0.0.0.0
EC_ADMIN_PORT=9090
EC_ADMIN_PASSWORD=CAMBIA-ESTA-CONTRASENA
EC_ADMIN_LOGIN_MAX_FAILURES=5
EC_ADMIN_LOGIN_WINDOW_SECONDS=60
```

> **Fuente única de configuración:** mantén cada variable exactamente una vez
> en `.env`. El JSON del cliente MCP sólo debe incluir `EC_MCP_ENV_FILE`.
> No declares `EC_ADMIN_PORT`, credenciales ni tokens directamente en la
> unidad systemd, porque el entorno del proceso tiene prioridad sobre `.env`.

Antes de reiniciar, detecta claves duplicadas y verifica los valores no secretos:

```bash
cut -d= -f1 .env | sed 's/^export //' | grep '^EC_' | sort | uniq -d
grep -nE '^(EC_ORCHESTRATOR_URL|EC_VERIFY_TLS|EC_MCP_HOST|EC_MCP_PORT|EC_ADMIN_HOST|EC_ADMIN_PORT|EC_UPDATE_REPOSITORY|EC_UPDATE_BRANCH)=' .env
sudo systemctl cat ec-mcp-admin
sudo systemctl show ec-mcp-admin -p Environment -p WorkingDirectory --no-pager
```

El primer comando no debe producir salida. Si systemd muestra una variable
`EC_ADMIN_*` fijada en la unidad, reinstala el servicio con el script actual.
En la versión estable vigente, `install_admin_service.sh --port 9090` actualiza `.env`
y la unidad sólo define `EC_MCP_ENV_FILE`.

## Instalación manual

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip

git clone --branch main https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-stable.txt -e .

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
`EC_ADMIN_PASSWORD`. La pestaña **Asistente** guía la configuración paso a
paso: cada paso declara qué variables son obligatorias (`*`) y cuáles sólo
aplican si se habilita su feature (p. ej. SSH o Axis), valida antes de avanzar
y muestra un diff del `.env` antes de escribir. La pestaña **Variables**
presenta la lista blanca completa de parámetros de Orchestrator, SSH opcional,
seguridad, transporte, panel y updater. Los secretos se guardan con permisos
`600`, se muestran sólo como “configurado” y un campo secreto vacío conserva
el valor existente. `POST /api/config/diff` devuelve el preview de cambios sin
escribir.

#### Usuarios y roles del panel

Si existe `EC_ADMIN_USERS_FILE` (JSON `0600` con
`{"users": {"nombre": {"password_hash": "sha256:...", "role": "..."}}}`), el
login pide usuario+contraseña y la pestaña **Usuarios** (solo rol `admin`)
permite crear, eliminar y cambiar contraseñas. Roles: `viewer` (solo lectura),
`operator` (configura, aplica, sondea y reinicia) y `admin` (además gestiona
usuarios). Sin archivo de usuarios se mantiene el modo retrocompatible de una
sola contraseña (`EC_ADMIN_PASSWORD`, rol admin). Todas las acciones del panel
quedan en la auditoría estructurada con el campo `user`.

**Guardar variables** actualiza `.env` de forma atómica. **Guardar y reiniciar
servicios** crea una solicitud que procesa el worker privilegiado; el proceso
web nunca ejecuta Git, pip ni systemctl directamente.

La interfaz está en **español e inglés** (botón ES/EN en la cabecera, se
recuerda en `localStorage`) y usa el look and feel del dashboard de WAN_SIM:
paleta HPE viva (`--green:#01a982`, cabecera teal `#073b4c` con borde inferior
verde, acentos cian `#00c8ff`, fondo claro `#edf5f6`, paneles blancos con
borde superior de acento y pestañas con subrayado). Con el engranaje
(**Personalizar**, estilo panel Appearance de WAN_SIM) se configura el nombre
del sitio, **tres colores** (acento, cabecera, acento secundario) con
`input[type=color]`, el **icono** (presets o PNG subido) y **vista previa en
vivo** de la cabecera; se guarda en `localStorage` y la página incluye
transiciones y animaciones suaves. La cabecera muestra la versión y
el usuario/rol conectado con menú propio; los avisos se limpian al cambiar de
pestaña. En **Variables**, los grupos van ordenados por paso del asistente y
son colapsables, con contador de campos por grupo.

En **Variables** (Service settings) hay un selector **por target**: además de
las variables globales, permite ver la configuración guardada de cada
Orquestador/SSE por nombre (URL, usuario, TLS, flags de secretos), junto al
estado de los blobs `EC_ORCHESTRATORS_JSON` / `EC_SSE_PLATFORMS_JSON`.

La pestaña **Debug** (`/api/debug/events`, `/api/debug/export`,
`/api/debug/clear`) muestra en tiempo real (cada 2 s, con filtro) las
solicitudes del panel (middleware propio, fuente `panel-api`) y las llamadas a
tools MCP leídas del audit log (`EC_MCP_AUDIT_LOG`, fuente `mcp-tool`), con
hora/fuente/acción/target/resultado/latencia. Permite **exportar** (JSONL o
CSV como adjunto) y **limpiar los logs** (trunca el audit log y vacía el búfer,
registrado en auditoría) para liberar almacenamiento. En Tools, las tarjetas
usan sliders en cuadrícula sin encimarse.

En Debug, los administradores también pueden consultar **CPU, RAM, disco y
tamaño del log de auditoría** y descargar hasta 500 eventos disponibles como
CSV, Excel (.xlsx) o PDF. La CPU necesita dos muestras; la primera puede
indicar «no disponible». La RAM usa `/proc/meminfo` y el disco corresponde al
sistema de archivos del directorio de trabajo del servicio. El tamaño del log
es el archivo de auditoría activo, no el total de todos los logs del sistema.

El medidor de actividad cuenta eventos MCP observados en el último minuto
dentro de las últimas 500 entradas accesibles; **no mide concurrencia ni la
capacidad del servidor**. La lectura del log está limitada a sus últimos 8 MiB,
por lo que pueden aparecer menos de 500 eventos. No todas las llamadas registran
usuario, Orchestrator u operación API: los campos ausentes se dejan vacíos y
no se infieren. El registro no garantiza capturar todas las solicitudes upstream.
Los informes aplican redacción de patrones y protección contra fórmulas, pero
deben revisarse antes de compartirlos porque pueden contener datos operativos.
El PDF es un resumen y acorta campos largos; CSV y Excel permiten mayor detalle.

La pestaña **Tools** (`/api/tools`, `/api/tools/toggle`) muestra las 142 tools
MCP en **cuadrícula con sliders** (switch) para activar/desactivar sin bajar la
página; se guarda en `EC_MCP_DISABLED_TOOLS`, aplica al reiniciar y también es
editable en Variables. El botón **Sugerencia
para AI Agent** (`/api/agent-prompt`) muestra el prompt completo para el agente,
incluyendo los skills de `ec-mcp/docs/` (`EDGECONNECT_NOC_OPS_SKILL.md`,
`AI_AGENT_SKILL_RECOMMENDATIONS.md`, `EDGECONNECT_EXPERT_SKILL.md`).

La pestaña **Certificados** (estilo WAN_SIM) instala certificados HTTPS con
los modos **PEM** (certificado y llave separados), **PEM bundle**, **PFX/P12**
(con contraseña) y **DER**; los archivos se suben como archivo (base64, límite
3 MB), se validan y normalizan a PEM con `openssl`, se comprueba que la llave
corresponde al certificado, se respalda el anterior (`cert.pem.bak`) y se
pide la confirmación escrita `INSTALAR CERTIFICADO`. Se guardan con `0600` en
`EC_ADMIN_TLS_DIR` y el estado muestra sujeto/emisor/vence/huella; con
`EC_ADMIN_TLS_ENABLED=true` + `EC_ADMIN_TLS_CERT`/`EC_ADMIN_TLS_KEY` el panel
sirve HTTPS (`/api/tls`, `/api/tls/upload`, `/api/tls/delete`).

#### Multi-Orchestrator y multi-SSE (multi-tenant)

El panel administra **N Orchestrators** y **N plataformas SSE** de forma
independiente:

- Pestaña **Orquestadores**: alta/baja/edición de cada Orchestrator (URL, API
  key o usuario/contraseña, TLS, credenciales SSH opcionales). Cada uno es un
  target con nombre propio (p. ej. `prod`, `lab`).
- Pestaña **Plataformas SSE**: alta/baja/edición de cada plataforma SSE (p.
  ej. varias instancias de Axis Security), con su propio `base_url`, token y
  timeout.
- El botón **Aplicar** escribe el target seleccionado en `.env` y **además**
  vuelca el registro completo como `EC_ORCHESTRATORS_JSON` y
  `EC_SSE_PLATFORMS_JSON`. El runtime carga todos los targets como un pool de
  clientes.
- Las tools MCP aceptan un parámetro opcional `target` para operar contra un
  Orchestrator o plataforma SSE concreto. Sin `target`, usan
  `EC_DEFAULT_ORCHESTRATOR` / `EC_DEFAULT_SSE` si apuntan a un target del
  registro; si no, `default` y, como último recurso, el primer target
  ordenado. El panel permite fijar el por defecto con el botón **Por defecto**
  (`POST /api/default`) y sondear cada target con **Probar** (`POST /api/probe`),
  además de **Duplicar** y **Renombrar** cada entrada.
- `list_orchestrator_targets_tool` y `list_sse_targets_tool` enumeran los
  targets configurados (nunca exponen secretos).
- **Backwards compatible**: si los blobs están vacíos, todo funciona como
  antes con un solo Orchestrator (`EC_ORCHESTRATOR_*`) y una sola plataforma
  (`EC_AXIS_*`).

#### Pestaña Servicios: estado real verificado

La pestaña **Servicios** (`GET /api/services/status`) comprueba cada backend
con una petición HTTP real en el momento de la consulta y registra cada
verificación en la auditoría estructurada (`tool=admin_panel`):

- Cada **Orchestrator** del registro recibe un `GET /gms/rest/gmsserver/briefInfo` después de autenticar.
- Cada **plataforma SSE** recibe un `GET /api/v1.0/Health` con su token Bearer. Configura como URL base el origen de la API (sin agregar `/api/v1.0`). Un error 401/403 indica revisar token/permisos; 404 indica revisar la URL. Guardar, aplicar a `.env` y elegir **Por defecto** son acciones distintas; reinicia para cargar cambios en el MCP.
- El **transporte MCP** se comprueba contra `EC_MCP_HOST:EC_MCP_PORT/health`.
- El **worker de actualizaciones** reporta su estado real (`idle`, `pending`,
  `running`, `success` o el último error).

Un servicio solo se muestra como `up` si la última respuesta fue HTTP 200; si
no, se muestra `down` con el error accionable y la marca de tiempo de la
última comprobación. El panel nunca presenta un estado `ready` sin prueba.
Los reinicios (`POST /api/restart`) y actualizaciones se modelan como
solicitudes auditadas (prevalidación, confirmación escrita, worker separado).

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

### Multi-Orchestrator, multi-SSE y multi-Central (multi-tenant)

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_ORCHESTRATORS_JSON` | vacío | Blob JSON con N Orchestrators nombrados. Lo escribe el panel al aplicar. Si está vacío, se usa `EC_ORCHESTRATOR_*` (un solo target `default`). |
| `EC_SSE_PLATFORMS_JSON` | vacío | Blob JSON con N plataformas SSE nombradas. Lo escribe el panel al aplicar. Si está vacío, se usa `EC_AXIS_*` (un solo target `default`). |
| `EC_CENTRAL_PLATFORMS_JSON` | vacío | Blob JSON con N plataformas Aruba Central nombradas (`base_url`, `client_id`, `client_secret`, `token_url`, `verify_tls`, `timeout`). Lo escribe el panel al aplicar. Si está vacío, se usa `EC_CENTRAL_*` (un solo target `default`). |
| `EC_DEFAULT_CENTRAL` | vacío | Target Central por defecto para las tools `central_*` sin `target` explícito. |

Las tools `central_*` aceptan un parámetro opcional `target` (igual que las
`axis_*`); `list_central_targets_tool` enumera los targets configurados sin
exponer secretos. El panel gestiona los targets Central con el mismo registro
0600 (`EC_ADMIN_STORE`), backups antes de cada cambio, auditoría y sondeo real
(OAuth2 + `sites-health`); el `client_secret` nunca regresa al navegador.

### Aruba Central

| Variable | Predeterminado | Uso |
|---|---:|---|
| `EC_CENTRAL_ENABLED` | `false` | Habilita la sección de Aruba Central (nuevas familias REST API v1). |
| `EC_CENTRAL_CLIENT_ID` | vacío | Client ID OAuth2 creado en HPE GreenLake (Personal API clients). |
| `EC_CENTRAL_CLIENT_SECRET` | vacío | Client Secret OAuth2. El token de acceso se obtiene y refresca automáticamente. |
| `EC_CENTRAL_BASE_URL` | `https://us.api.central.arubanetworks.com` | API gateway base URL de tu cuenta Central (p.ej. `https://us5.api.central.arubanetworks.com`). |
| `EC_CENTRAL_TOKEN_URL` | endpoint SSO de HPE | Endpoint OAuth2 alternativo (Central on-prem). |
| `EC_CENTRAL_VERIFY_TLS` | `true` | Verifica el certificado TLS de Central. |
| `EC_CENTRAL_TIMEOUT` | `30` | Timeout HTTP en segundos. |

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
| `EC_ADMIN_STORE` | `.ec-admin.json` | Registro JSON (0600) de Orchestrators y plataformas SSE gestionado desde el panel. |

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

### Detección y remediación asistida (Fase 3)

El flujo de respuesta a incidentes es: **detectar → proponer → decidir →
aplicar con confirmación humana**:

1. `correlate_incidents` correlaciona IDS/IPS, drops del firewall, DDoS,
   alarmas y web filtering en hallazgos priorizados (solo lectura).
2. `propose_remediation` convierte cada hallazgo en una **propuesta estructurada, dry-run**: evidencia, alcance, riesgo, plan de reversión,
   política candidata y el paso siguiente de solo lectura. Nunca aplica nada.
3. Políticas disponibles (plantillas del roadmap):
   - `observation` — solo recopila y correlaciona señales.
   - `containment_proposed` — sugiere clasificación/bloqueo temporal; nunca aplica.
   - `controlled_change` — operación preaprobada para un alcance definido,
     con ventana, confirmación y reversión.
   - `emergency` — reservada a operadores autorizados; exige justificación,
     evidencia y revisión posterior.
4. Para actuar: `list_response_options` (dry-run exacto) y luego
   `block_threat`/`apply_change`/`run_cli_command` con `confirm=true` tras
   aprobación humana explícita. Cada propuesta queda registrada en la
   auditoría estructurada (`tool=propose_remediation`, `dry_run=true`).

La IA nunca ejecuta cambios de red por sí misma: puede explicar por qué
recomienda una acción y qué cambio exacto se haría, pero la aplicación
siempre requiere confirmación humana.

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

## Upgrade por terminal

Procedimiento para actualizar a **9.4.0 estable desde `main`**. Actualiza solamente el servidor MCP; no requiere cambiar firmware ni modificar configuración de red en los appliances. Sustituye `~/APIIntegration` por la ruta real de la instalación.

### 1. Preparar y respaldar

- Comprueba Python 3.12 o superior con `python3 --version`; si la `.venv` anterior usa una versión menor, crea una nueva con Python 3.12 antes de instalar.
- Termina los planes BIO/ZTP pendientes. Los planes BIO y ZTP bulk viven en memoria y se pierden al reiniciar; los planes ZTP individuales solo persisten si configuraste `EC_ZTP_STATE_DIR`.
- Si `git status --short` muestra cambios, respáldalos o haz un commit local antes de continuar. No uses `reset --hard` para resolverlos.
- Mantén una ventana de mantenimiento. Guarda los puertos existentes y deja las escrituras deshabilitadas durante la validación.

```bash
cd ~/APIIntegration
git status --short
BACKUP_DIR="$HOME/ec-mcp-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/previous-commit.txt"
git diff --binary > "$BACKUP_DIR/local-changes.patch"
./ec-mcp/.venv/bin/python -m pip freeze --exclude-editable > "$BACKUP_DIR/requirements-before.txt"
for item in .env .ec-admin.json .ec-admin-pass logs; do
  if [ -e "ec-mcp/$item" ]; then cp -a "ec-mcp/$item" "$BACKUP_DIR/"; fi
done
```

Respalda además las rutas externas que uses para `EC_ADMIN_STORE`, `EC_ADMIN_PASSWORD_FILE`, `EC_MCP_AUDIT_LOG`, `EC_MCP_PROFILES_DIR`, `EC_ZTP_STATE_DIR` y `EC_UPDATE_STATE_DIR`. El respaldo contiene secretos: conserva permisos privados. Si usas systemd, guarda también las unidades y overrides locales en el respaldo.

Para una instalación con ambos servicios, pausa el timer del updater y detén los servicios durante la instalación:

```bash
sudo systemctl stop ec-mcp-update.timer
sudo systemctl stop ec-mcp ec-mcp-admin
```

Ejecuta únicamente los comandos de los servicios que ya existen. En stdio, cierra el cliente MCP; en instalaciones manuales, detén el proceso por su mecanismo habitual.

### 2. Instalar la referencia estable

```bash
cd ~/APIIntegration
git fetch origin
git switch --detach origin/main
cd ec-mcp
./scripts/install.sh --non-interactive
./.venv/bin/python -c "from ec_mcp import __version__; assert __version__ == '9.4.0'; print(__version__)"
```

El instalador conserva `.env` y usa `requirements-stable.txt` para instalar runtime y QA, incluido pytest. Revisa las claves nuevas de `.env.example` y añade solo las que falten; no reemplaces el archivo ni regeneres secretos, conexiones o puertos. La configuración del proceso/systemd prevalece sobre `.env`.

| Instalación anterior | Revisión necesaria |
|---|---|
| Python anterior a 3.12 | Actualizar Python/venv; comprobar `EC_MCP_ENV_FILE`, autenticación HTTP y variables actuales. |
| 3.x y betas | Revisar overrides antiguos de systemd y claves duplicadas; el puerto del panel se toma de `EC_ADMIN_PORT`. |
| 4.0.x | Mismo procedimiento; las pruebas y dependencias quedan instaladas y la identidad de versión deja de esperar `4.0.0b1`. |

Las variables SSH vigentes son `EC_SSH_USER`, `EC_SSH_PASSWORD`, `EC_SSH_ENABLE_PASSWORD`, `EC_SSH_PORT` y `EC_SSH_AUTH_METHOD`. `EC_SSH_USERNAME`, `EC_SSH_PRIVATE_KEY`, `EC_SSH_STRICT_HOST_KEY`, `EC_SSH_KNOWN_HOSTS`, `EC_WRITE_DRY_RUN_DEFAULT` y `EC_WRITE_AUDIT_LOG` no son opciones implementadas; la ruta de auditoría es `EC_MCP_AUDIT_LOG`. SSH sigue deshabilitado por defecto.

### 3. Reactivar y comprobar

Si utilizas systemd, reinstala solo los servicios ya utilizados. Los scripts conservan los puertos de `.env`; `--port` cambia el puerto explícitamente.

```bash
./scripts/install_service.sh
./scripts/install_admin_service.sh
sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
systemctl --no-pager status ec-mcp ec-mcp-admin
./.venv/bin/python -m pytest tests -q
git rev-parse HEAD
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1:9090/login
```

Sustituye 8000/9090 por tus puertos. `/health` comprueba el transporte; valida también `orchestrator_info()`, `list_appliances()` y `run_show_api(command="show version", appliance_id="<nePk-real>")` desde el cliente. Confirma versión 9.4.0, inventario real, respuesta por API y funcionamiento del login del panel antes de habilitar escrituras. En stdio, reinicia el cliente MCP.

### 4. Recuperar si falla

Mantén los servicios detenidos si la instalación o sus pruebas fallan. Vuelve al commit guardado y reinstala sus dependencias. Usa el mismo `BACKUP_DIR` del primer paso:

```bash
cd ~/APIIntegration
git switch --detach "$(cat "$BACKUP_DIR/previous-commit.txt")"
cd ec-mcp
./.venv/bin/python -m pip install -r "$BACKUP_DIR/requirements-before.txt" -e .
# Restaura .env/configuración/estado únicamente si cambiaron durante la actualización.
# Reinstala las unidades anteriores si ya reemplazaste los servicios systemd.
sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
```

Verifica de nuevo versión, transporte y conexión. Reactiva el timer del updater solo cuando el servidor esté validado. Para seguir futuras publicaciones con Git, usa `git switch main` y avance rápido después de revisar el commit y ejecutar las pruebas.

### Diagnóstico de acceso al panel

```bash
grep -nE '^(EC_ADMIN_HOST|EC_ADMIN_PORT|EC_ADMIN_LOGIN_MAX_FAILURES|EC_ADMIN_LOGIN_WINDOW_SECONDS)=' .env
sudo systemctl cat ec-mcp-admin
sudo ss -lntp | grep -E ':(8080|9090)\\b'
curl -I http://127.0.0.1:9090/login
sudo journalctl -u ec-mcp-admin -n 50 --no-pager
```

- Conserva una sola línea `EC_ADMIN_PASSWORD=`; una definición duplicada puede
  hacer que se use una contraseña distinta de la esperada.
- Si cambias contraseña o puerto, reinicia `ec-mcp-admin`.
- Tras alcanzar el límite de intentos, espera
  `EC_ADMIN_LOGIN_WINDOW_SECONDS` antes de volver a probar.

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

## Flujo transaccional de Business Intent Overlays

La versión estable vigente permite crear un BIO a partir de un overlay válido ya
existente, sin depender del esquema placeholder del OpenAPI:

```text
list_overlay_sources()
prepare_overlay_clone(source_overlay="RealTime", target_name="NuevaSucursal")
preview_overlay_plan(plan_id="...")
apply_overlay_plan(plan_id="...", confirmation="CREAR OVERLAY ...", confirm=true)
verify_overlay_plan(plan_id="...")
rollback_overlay_plan(plan_id="...", confirmation="ROLLBACK ...", confirm=true)
```

El flujo:

1. lee el objeto fuente desde el Orchestrator;
2. elimina IDs y metadatos administrados por el servidor;
3. aplica `overrides_json` mediante deep merge;
4. exige nombre nuevo, topología y reglas de match válidas;
5. presenta candidato y diff sin escribir;
6. genera una confirmación única con vencimiento;
7. crea exactamente una vez;
8. vuelve a leer el inventario para verificar nombre e ID;
9. conserva únicamente el ID verificado para un posible rollback.

Los planes viven en memoria durante 15 minutos. Reiniciar el MCP invalida planes
no aplicados. El rollback requiere además `EC_ALLOW_DANGEROUS_WRITES=true`,
porque elimina configuración. No se permite usar este flujo para borrar un
overlay que no haya sido creado por el mismo plan.

## Flujo transaccional de adopción ZTP

La versión estable **9.2.0** extiende el patrón transaccional a la adopción
de equipos descubiertos por ZTP, siguiendo el modelo real de preconfiguración
del Orchestrator: la preconfiguración es un documento YAML con nombre propio
que se crea vía `createpreconfiguration247_1` y se aplica al equipo descubierto
con `discoveredId` + `preconfigId` reales:

```text
list_discovered_appliances()
prepare_ztp_adoption(appliance_selector="001BBC462C04", preconfig_yaml="...")
preview_ztp_plan(plan_id="...")
apply_ztp_plan(plan_id="...", confirmation="ADOPTAR ...", confirm=true)
get_ztp_apply_status(preconfig_id="...")
verify_ztp_plan(plan_id="...")
rollback_ztp_plan(plan_id="...", confirmation="ROLLBACK ...", confirm=true)
```

El flujo:

1. lista equipos descubiertos pendientes (no aprobados ni denegados);
2. selecciona el equipo por **número de serie** (preferido; con o sin
   guiones, ej. `001BBC462C04` o `00-1B-BC-46-2C-04`) o por UUID;
3. valida el YAML de preconfiguración contra las reglas documentadas
   (secciones requeridas `applianceInfo`/`deploymentInfo` con `group`,
   `networkRole`, `location`, `contact`; lan exige `ipAddressMask`; wan
   exige `nextHop` + anchos de banda + `firewallMode`; lat/long en par o
   vacíos; `deploymentMode` solo `inline-router`);
4. verifica que los template groups y overlays referenciados existan;
5. genera una confirmación ligada a plan + id de fila discovered + nombre
   de preconfig desechable (`Codex-ZTP-<plan>`);
6. en apply: valida el preconfig (`250`), lo crea (`247_1`, body con
   `name` + `configData` base64 + `autoApply=false`) y lo aplica (`255`).
   **El `discoveredId` es el id numérico de la fila discovered** — con el
   UUID el Orchestrator 9.7.2 responde 200-vacío (no-op silencioso);
   verificado en producción: con el id numérico ejecuta la cadena completa
   de tareas (Add Appliance → Appliance Info → Zones → license →
   deployment → **Reboot** → templates → overlays);
7. el apply es **asíncrono**: `get_ztp_apply_status` consulta el estado de
   la cadena de tareas (`254`) y `verify_ztp_plan` confirma que el equipo
   desapareció de discovered y aparece en el inventario por serial;
8. registra el `preconfigId` creado para limpieza en rollback;
9. rollback: deny (`55`) + delete del preconfig creado por el plan (`251`).

### Adopción masiva (bulk)

```text
prepare_bulk_ztp_adoption(
    appliance_selectors="001BBC462C04,001BBC462C05,...",
    base_preconfig_yaml="...",          # con {{hostname}} / {{site}}
    hostnames="EC10,EC11,...",
    sites="Calimaya,Calimaya,...",
)
apply_bulk_ztp_plan(bulk_id="...", confirmation="ADOPTAR-BULK ...", confirm=true)
list_bulk_ztp_plans()
```

La plantilla base acepta los placeholders `{{hostname}}` y `{{site}}`,
sustituidos por equipo desde las listas separadas por comas. Cada equipo
recibe su propio sub-plan y preconfig desechable; un fallo en un equipo no
detiene a los demás y el resultado reporta el estado individual.

Los planes pueden persistirse a disco con `EC_ZTP_STATE_DIR` para sobrevivir
a reinicios del MCP. El rollback (deny + delete) requiere además
`EC_ALLOW_DANGEROUS_WRITES=true`. No se permite adoptar un equipo ya
aprobado ni enviar cuerpos vacíos.

## Suite de seguridad y troubleshooting

La versión estable `9.2.0` añade herramientas curadas de solo lectura sobre el
catálogo crudo, agrupadas por dominio:

| Herramienta | Dominio | Descripción |
|---|---|---|
| `get_ids_ips_state(appliance_id)` | IDS/IPS | Postura IDS/IPS por equipo: modo (Off/IDS Only/IPS-Performant/IPS-Inline), perfil, activo o no. Acepta `all`. |
| `get_ids_ips_events(appliance_id, start_time, end_time)` | IDS/IPS | Eventos de intrusión recientes para detección de incidentes. |
| `get_zone_matrix(appliance_id)` | Zone matrix | Zonas, security maps con políticas zona↔zona por prioridad y **pares de zonas sin política explícita**. |
| `get_ddos_status(appliance_id)` | DDoS | Threshold status y protection profiles por zona. |
| `get_deployment_config(appliance_id)` | LAN/WAN | Modo de deployment, bandwidths e interfaces con addressing/labels/zones/firewall modes. |
| `get_site_to_site_tunnels(appliance_id, include_third_party)` | Túneles | Estado de túneles site-to-site, bonded y de terceros/SSE (VGWs). |
| `get_bgp_neighbors(appliance_id)` | Routing | Vecinos BGP con estado y sesiones BFD; acepta `all`. |
| `get_sse_status(provider)` | SSE | Estado de integración SSE (Zscaler, Netskope, Axis Security/HPE SSE): conectividad y appliances asociados. `provider=all` o individual. |
| `get_security_posture(appliance_id)` | Incidentes | Snapshot de una llamada: IDS/IPS + zone matrix + túneles por equipo, con lista priorizada de hallazgos (severidad high/medium/low). |

Todas son de solo lectura (`call_read_api`/`appliance_api_call`), sin
dry-run ni confirmación. Para cambios de configuración de seguridad usa
`apply_change` con las operaciones crudas (`orchestrator.idpsstateput`,
`appliance.securitymapspost`, etc.) o los flujos transaccionales.

## Mejoras de operación e inconsistencias en desarrollo

La base estable 9.2.0 conserva los workflows MCP existentes. El roadmap ZTP de la UI administrativa sigue pendiente. Estas correcciones deben pasar por pruebas de regresión antes de integrarse en `main`:

- Evitar repetir POST/PUT/PATCH/DELETE ante una respuesta vacía o por fallback de rutas.
- Verificar adopción ZTP solo con tareas confirmadas, inventario fresco y salida de discovered.
- Aplicar validación de comandos y candado de operaciones peligrosas a SSH, `/cli`, `/cliMultiple` y broadcast.
- Conservar valores de parámetros como `0`/`false` y distinguir una escritura aplicada de una comprobación posterior fallida.
- Sanear el registro de auditoría antes de persistirlo.

Pendientes posteriores: validación de host keys SSH, aislamiento del worker privilegiado de actualización, cobertura de contratos API y correcciones de unidades/riesgo por sitio y sesiones WebSocket del dashboard. La validación automatizada no sustituye una prueba de actualización en un servidor real ni certifica todos los endpoints del catálogo.

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
| Panel muestra `Demasiados intentos` | Espera el tiempo mostrado o inicia sesión con la contraseña correcta; un login válido limpia inmediatamente el bloqueo. |
| systemd no toma cambios | Ejecuta `sudo systemctl daemon-reload && sudo systemctl restart ec-mcp`. |
| `EC_ADMIN_PORT` vuelve a `8080` | Vuelve a guardar el puerto y reinstala `install_admin_service.sh` con la versión estable vigente. |

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
