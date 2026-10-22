# EdgeConnect NOC Ops Skill (ec-mcp v7.0.1)

Guía operativa para NOC: cómo usar el MCP `ec-mcp` v7.0.1 para monitorear, diagnosticar y operar EdgeConnect + Axis Security (SSE). Actualizado con la capa de telemetría, respuesta a incidentes, plataforma Axis, **guías por tarea de SSE (§1.7, G1–G10)**, **dashboard NOC desplegable en servidor (G10)**, **SD-WAN AI / SASE Copilot** y **resiliencia SSH (timeouts + reintentos)**.

**Novedades 7.0.0 / 7.0.1 (ver §0.1):**
- Perfil EdgeConnect **10.0** con fallback de versión mayor (PR #80)
- Resolución de `$ref` OAS y correcciones 10.0 verificadas en vivo (PR #81)
- **SD-WAN AI / SASE Copilot** expuesto como 4 tools MCP (PR #82)
- Endurecimiento: SSE con techo de 2000 eventos / 2 MB, `clear_sdwan_ai_context` exige guardas de escritura (PR #86)
- **SSH resiliente**: `EC_SSH_CONNECT_TIMEOUT`, `EC_SSH_COMMAND_TIMEOUT`, `EC_SSH_RETRIES` con backoff exponencial limitado (PR #89)
- Hoja de ruta de operaciones seguras: `docs/MCP_OPERATIONS.md` (Fases 1–3, políticas, prohibiciones)

---

## 0. Perfiles de versión del Orchestrator (NUEVO v6.0.0)

El MCP debe poder leer **cualquier Orchestrator**: perfiles cargados 9.3, 9.4, 9.5, 9.6 y **10.0** (desde `api-collections/apiDocs.json`, el OpenAPI oficial 10.0 con parámetros `$ref` resueltos).

**Resolución de versión (automática, en este orden):**
1. Igualdad exacta → 2. coincidencia `major.minor` (`10.0.0.40204` → `10.0`) → 3. **fallback al perfil mayor disponible ≤ versión detectada** + warning en el log (`9.7.2.40591` → `9.6`; un futuro `10.1`/`11.0` → `10.0`).

**Rutina NOC al conectar a un Orchestrator nuevo o tras un upgrade:**
1. `orchestrator_info` → verificar `active_profile` no nulo y `package_version` del conector.
2. Si `active_profile` es null → solo sondear funciones nativas (telemetría básica, alarmas, ZTP) y asumir bloqueadas las de perfil (`call_read_api`, SOC, flujos, proxy).
3. Si hay fallback (perfil menor que la versión detectada) → catálogo disponible, pero validar shapes en vivo antes de confiar en extractores.
4. Registrar (fecha, versión, perfil, sondas OK/bloqueadas) en el Knowledge; tras cualquier upgrade, re-ejecutar la batería completa (`QA-BATTERY.md`). Detalle en `docs/PROFILE_VERSION_ROUTINE.md`.

**Notas 10.0 conocidas (verificadas en vivo):**
- `GET /flow` del Orchestrator requiere `nePk` (validado); si la versión del appliance rechaza la consulta, `troubleshoot_flows` hace fallback automático al proxy del appliance `GET /flows` (`appliance.flows263831`).
- `POST /stats/realtimeStats` cambió de body en 10.0: `{"type", "name"}` (+`filter`/`count` según categoría); los tipos válidos incluyen `traffic_type`, `traffic_class`, `dscp`, `flow`, `drops`, `interface`.
- BFD `GET /bfd/state/vrfs` requiere `nePk` en 10.0; sin vecinos BGP configurados devuelve listas vacías (normal).
- `POST /health` vía proxy requiere `nePk` correcto; si el appliance responde 404, el resto de `get_appliance_health` (system info, disk usage, disks) sigue siendo válido.
- SSH: el parámetro `host` se resuelve por **nombre de appliance o nePk**, nunca por IP (`Appliance not found in inventory` con IP).
- **IA embebida (SD-WAN AI / SASE Copilot)**: `ask_sdwan_ai` conversa con el asistente del propio Orchestrator (10.0). Si responde error, verificar `get_sase_copilot_status` (default false) y el rol READ_WRITE. En perfiles sin `/sdwanai/*` (9.x) la tool lo indica sin romper.

---

### 0.1 Cambios operativos en 7.0.0 / 7.0.1

#### 7.0.0 — Endurecimiento MCP (PR #86, refs #83 #84 #85 #87)

| Cambio | Impacto NOC |
|--------|-------------|
| `clear_sdwan_ai_context` ahora llama `require_writes()` | La tool exige `EC_ALLOW_WRITE_TOOLS=true` antes de ejecutarse (era una omisión de la guarda global, issue #83). |
| `stream_post_sse` con techo duro | El consumidor SSE se limita a **2000 eventos** y **2 MB** aunque el caller pida más. Devuelve `truncated: true` si se alcanza el límite. |
| `opentelemetry-api` 1.45.1 | Actualización de dependencia (PYSEC). |
| `SECURITY.md` + redacción en `apiDocs.json` | Playbook de respuesta ante exposición de secretos; ejemplos OpenAPI ya no contienen valores sensibles. |

#### 7.0.1 — Resiliencia SSH (PR #89, refs #88)

**Nuevas variables de entorno (añadir a `.env` o panel web):**
```bash
EC_SSH_CONNECT_TIMEOUT=30   # timeout de conexión TCP/banner/auth (segundos)
EC_SSH_COMMAND_TIMEOUT=30   # timeout de lectura por comando show (segundos)
EC_SSH_RETRIES=1            # reintentos ante fallos transitorios (0 = sin reintento)
```

**Comportamiento:**
- Los reintentos solo aplican a **errores transitorios** detectados por `is_transient_ssh_error()`: `timeout`, `timed out`, `temporarily unavailable`, `connection reset`, `ssh protocol banner`, `channel closed`, `socket is closed`.
- Backoff exponencial limitado: `0.25s`, `0.5s`, `1.0s` (máximo entre intentos).
- Los errores de autenticación (`Authentication failed`) **no** se reintentan.
- Los errores de conexión rechazada en WAN mantienen el diagnóstico de `ensure_ssh_inbound_forwarding`.
- `run_show` usa `min(10, command_timeout)` para `page off` y `command_timeout` para el comando.
- `run_raw` usa `max(60, command_timeout)`.

**Rutina NOC ante fallos SSH intermitentes:**
1. Si un `run_show_command` falla con timeout esporádico → el MCP ya reintentó `EC_SSH_RETRIES` veces. Si persiste, subir `EC_SSH_COMMAND_TIMEOUT` (ej. 60).
2. Si la conexión se cae a mitad de sesión → el pool descarta la sesión y reconecta en la siguiente llamada.
3. Nunca subir `EC_SSH_RETRIES` por encima de 2: más reintentos enmascaran problemas de red reales.
4. Verificar `get_ssh_network_path(appliance_id)` para confirmar LAN vs WAN antes de diagnosticar.

---

## 0.2 Rutina de operaciones seguras (MCP_OPERATIONS — refs #88)

Fuente: `docs/MCP_OPERATIONS.md`. Define cómo debe comportarse el MCP en operación real: rápido, predecible y seguro. **La IA detecta, correlaciona y propone; nunca aplica cambios sin aprobación explícita.**

### Fases

| Fase | Estado | Qué cubre |
|------|--------|-----------|
| **Fase 1** | Parcial (7.0.1) | Consultas y SSH fiables: contrato de respuesta común, límites de consulta, reintentos SSH limitados, timeout configurable, diagnóstico LAN/WAN, métricas y auditoría sin secretos. |
| **Fase 2** | Planificada | Panel de administración con estado real de servicios, reinicios como solicitudes con confirmación escrita, allowlist de servicios, auditoría. |
| **Fase 3** | Planificada | Detección y remediación asistida: correlación IDS/IPS + DDoS + alarmas + firewall + túneles, propuestas de remediación con evidencia y reversión, todo en `dry_run` hasta aprobación humana. |

### Plantillas de política (aplicar al operar)

1. **Observación**: solo recopila y correlaciona señales. Sin escrituras.
2. **Contención propuesta**: sugiere clasificación/bloqueo temporal, **nunca aplica**.
3. **Cambio controlado**: permite una operación preaprobada para un alcance definido, con ventana, confirmación y reversión.
4. **Emergencia**: reservada a operadores autorizados; registra justificación, evidencia y revisión posterior.

### Prohibiciones absolutas

- No habilitar SSH expuesto a WAN automáticamente.
- No aceptar comandos arbitrarios desde el panel o una herramienta MCP.
- No desactivar ni reducir validaciones de seguridad para acelerar una acción.
- No guardar tokens, contraseñas o datos de producción en ejemplos, auditorías o respuestas.

### Contrato de respuesta esperado (Fase 1)

Toda respuesta operativa debe incluir: **resultado, fuente, tiempo, truncamiento y error normalizado**. Si una respuesta no tiene estos campos, tratarla como incompleta.

---

## 1. Mapa de herramientas MCP (v7.0.1 — 122 tools)

### 1.1 Telemetría (v5.0.0; perfiles 10.0 en v6.0.0; SD-WAN AI en 7.0.0)

| Tool | Uso |
|------|-----|
| `get_orchestrator_infrastructure` | KPIs del Orchestrator: platform, GMS, disco, particiones BD, stats collectors. Salud propia del Orchestrator. |
| `get_appliance_infrastructure(appliance_id)` | KPIs por appliance desde el Orchestrator: CPU timeseries, performance/throughput, interface state (histórico/agregado). |
| `get_realtime_stats(appliance_id, type, name, filter, count)` | Stats **real-time** por segundo del appliance vía proxy SD-WAN (`POST /stats/realtimeStats`). Tipos: `tunnel`, `port`, `port_pair`, `boosted_tunnel`, `shaper`, `traffic_type`, `traffic_class`, `dscp`, `flow`, `drops`, `interface`. Filtro: `all`/`average`/`peak` (los tipos `drops` no usan filter/count). El body se arma según los ejemplos oficiales de la versión detectada. |
| `get_appliance_health(appliance_id)` | Salud viva del appliance: `POST /health` (loss/latency/jitter/MOS), system info, disk usage, discos. |
| `ask_sdwan_ai(question, chat_id, max_events)` | **SD-WAN AI / SASE Copilot (10.0)**: pregunta en lenguaje natural al asistente de IA del Orchestrator (`POST /sdwanai/search`, streaming SSE consumido hasta el final). Devuelve `answer` + `chat_id`/`msg_id` para continuar la conversación. `max_events` tiene **techo duro de 2000** (7.0.0). Requiere el feature habilitado (`get_sase_copilot_status`) y rol READ_WRITE. |
| `get_sdwan_ai_chat_logs()` | Historial completo de la sesión de chat activa del SD-WAN AI (preguntas, respuestas, timestamps, documentos de referencia). |
| `clear_sdwan_ai_context()` | Reinicia el contexto del chat de IA y crea una sesión nueva. **Desde 7.0.0 exige `EC_ALLOW_WRITE_TOOLS=true`** (guarda de escritura, issue #83). |
| `get_sase_copilot_status()` | Indica si el SASE Copilot está habilitado en el Orchestrator (advanced property, default false). |

**Flujo NOC recomendado:**
1. `get_orchestrator_infrastructure` → ¿el Orchestrator está sano?
2. `list_appliances` → ¿qué appliances hay y su reachability?
3. `get_appliance_health` → salud viva por appliance
4. `get_realtime_stats` → tráfico por túnel/puerto en tiempo real

**Troubleshooting SD-WAN AI:**
1. Si `ask_sdwan_ai` devuelve error → llamar `get_sase_copilot_status()`. Si `enabled: false`, el feature está apagado en el Orchestrator.
2. Si el feature está on pero falla → verificar que la API key tenga rol **READ_WRITE** (el endpoint `/sdwanai/search` lo exige).
3. Si la respuesta viene truncada (`truncated: true`) → bajar `max_events` (default 2000, techo 2000 eventos / 2 MB en 7.0.0).
4. Si el Orchestrator es 9.x → las tools devuelven `"SD-WAN AI is not available in the active API profile"` sin romper.

### 1.2 Seguridad y respuesta a incidentes

| Tool | Uso |
|------|-----|
| `correlate_incidents(appliance_id, date)` | Correlaciona IDS/IPS + firewall drops + DDoS + web filtering + alarmas activas → lista priorizada de incidentes. |
| `get_security_posture(appliance_id)` | Snapshot de posture: IDS/IPS, DDoS, zone matrix, túneles. |
| `get_ids_ips_state` / `get_ids_ips_events` | Estado y eventos IDS/IPS por appliance. |
| `get_active_alarms` | Alarmas activas por severidad. |
| `get_security_log` | Firewall logs (con `summarize=true` incluye web filtering). |
| `list_response_options(target, domain, application, context)` | Enumera TODAS las opciones de respuesta de EdgeConnect ante una amenaza (ipIntelligence, DNS, ACL, IPS inline, zona deny, interfaz shutdown, blackhole, DDoS). |
| `block_threat(target/domain, category, confirm)` | Aplica bloqueo: clasifica IP/CIDR (ipIntelligence) o dominio (dnsClassification2) en categoría de bloqueo. Dry-run por defecto. |

**Flujo de respuesta a incidentes:**
1. `correlate_incidents` → detectar
2. `list_response_options(target=..., context=...)` → ver opciones
3. `block_threat(target=..., category=..., confirm=true)` → aplicar (requiere `EC_ALLOW_WRITE_TOOLS=true`)

### 1.3 SSH — Rutas de red LAN/WAN + resiliencia (v5.0.0, endurecido en 7.0.1)

| Tool | Uso |
|------|-----|
| `get_ssh_network_path(appliance_id)` | Muestra cómo se alcanzaría el appliance por SSH: LAN (misma subred, directo) o WAN (IP de interfaz WAN, NO la pública/NAT). Incluye notas y diagnóstico. |
| `ensure_ssh_inbound_forwarding(appliance_id, external_port, internal_port, source_ip, confirm)` | Crea una regla de port-forwarding (inbound) para SSH en la WAN del appliance. Dry-run por defecto. |
| `run_show_command(command, host)` | Ejecuta `show ...` por SSH (whitelist). |
| `run_cli_command(command, host, confirm)` | Ejecuta cualquier comando ECOS por SSH (config = dry-run + confirm). |
| `run_show_api(command, appliance_id)` | Ejecuta `show ...` vía API del Orchestrator (sin SSH). |
| `list_cli_commands(category)` | Catálogo de 1367 comandos ECOS. |

**Reglas de red SSH:**
- **LAN**: si la IP LAN del appliance está en la misma subred /24 que una interfaz local → SSH directo a la IP LAN.
- **WAN**: si no → SSH a la **IP de la interfaz WAN** del appliance (la configurada en la interfaz, NO la IP pública/NAT de salida).
- Si se rechaza en WAN → falta **inbound forwarding** (port-forward/DNAT para TCP/22). Usar `ensure_ssh_inbound_forwarding` para crearlo.

**Resiliencia SSH (7.0.1 — PR #89):**

| Variable | Default | Descripción |
|----------|---------|-------------|
| `EC_SSH_CONNECT_TIMEOUT` | 30 | Timeout de conexión TCP + banner + auth (segundos). Aplica a netmiko (`conn_timeout`, `banner_timeout`, `auth_timeout`) y paramiko. |
| `EC_SSH_COMMAND_TIMEOUT` | 30 | Timeout de lectura por comando `show` (segundos). `run_show` usa este valor; `page off` usa `min(10, command_timeout)`. `run_raw` usa `max(60, command_timeout)`. |
| `EC_SSH_RETRIES` | 1 | Reintentos ante **fallos transitorios** (0 = desactivado). Backoff: 0.25s, 0.5s, 1.0s (máx). |

**Errores transitorios que se reintentan:** `timeout`, `timed out`, `temporarily unavailable`, `connection reset`, `ssh protocol banner`, `channel closed`, `socket is closed`.

**Errores que NO se reintentan:** `Authentication failed` (credenciales malas), conexión rechazada en WAN (diagnóstico de inbound forwarding), comandos prohibidos.

**Configurar en el panel web:** Variables → SSH → `EC_SSH_CONNECT_TIMEOUT`, `EC_SSH_COMMAND_TIMEOUT`, `EC_SSH_RETRIES` → Guardar y reiniciar.

### 1.4 Axis Security (SSE) — 55 tools (v5.0.0)

Plataforma SSE de Axis Security. Solo requiere **un token de administración** (`EC_AXIS_ADMIN_TOKEN`, Bearer JWT).

#### Configuración (solo estas variables)
```bash
EC_AXIS_ENABLED=true
EC_AXIS_ADMIN_TOKEN=eyJhbGciOi...   # Bearer JWT
# Opcionales:
EC_AXIS_BASE_URL=https://admin-api.axissecurity.com
EC_AXIS_VERIFY_TLS=true
EC_AXIS_TIMEOUT=30
```

#### Recursos y tools

| Recurso | Tools |
|---------|-------|
| **Health** | `axis_health` |
| **Tags** (Application Groups) | `axis_list_tags`, `axis_get_tag`, `axis_create_tag`, `axis_update_tag`, `axis_delete_tag` |
| **Applications** | `axis_list_applications`, `axis_get_application`, `axis_create_application`, `axis_update_application`, `axis_delete_application` |
| **Connectors** | `axis_list_connectors`, `axis_get_connector`, `axis_create_connector`, `axis_update_connector`, `axis_delete_connector`, `axis_regenerate_connector`, `axis_connector_status` |
| **Connector Zones** | `axis_list_connector_zones`, `axis_get_connector_zone`, `axis_create_connector_zone`, `axis_update_connector_zone`, `axis_delete_connector_zone` |
| **IP Categories** (custom) | `axis_list_ip_categories`, `axis_get_ip_category`, `axis_create_ip_category`, `axis_delete_ip_category` |
| **Web Categories** | `axis_list_web_categories`, `axis_get_web_category`, `axis_create_web_category`, `axis_delete_web_category` |
| **SSL Exclusions** | `axis_list_ssl_exclusions`, `axis_create_ssl_exclusion`, `axis_delete_ssl_exclusion` |
| **Groups** | `axis_list_groups`, `axis_create_group`, `axis_delete_group` |
| **Users** | `axis_list_users`, `axis_get_user`, `axis_create_user`, `axis_delete_user` |
| **Locations** | `axis_list_locations`, `axis_get_location`, `axis_create_location`, `axis_delete_location` |
| **SubLocations** | `axis_list_sub_locations`, `axis_create_sub_location`, `axis_delete_sub_location` |
| **Tunnels** | `axis_list_tunnels`, `axis_tunnel_status`, `axis_create_tunnel`, `axis_delete_tunnel` |
| **Certificates** | `axis_list_certificates` |
| **IPSec PoP Locations** | `axis_list_ipsec_locations` |
| **Commit** | `axis_commit(confirm=true)` — **persistir todos los cambios** |

#### Flujo de trabajo Axis

1. **Lectura**: `axis_health`, `axis_list_connectors`, `axis_connector_status(id)`, `axis_list_applications`, etc.
2. **Escritura (dry-run primero)**: `axis_create_*` / `axis_update_*` / `axis_delete_*` → sin `confirm=true` muestra qué se ejecutaría.
3. **Aplicar**: repetir con `confirm=true` (requiere `EC_ALLOW_WRITE_TOOLS=true`).
4. **Persistir**: `axis_commit(confirm=true)` — **sin commit los cambios no se aplican**.

> **Para estructurar una tarea específica de Axis, usar las guías por tarea de §1.7** (G1 escritura genérica, G2 troubleshooting, G3 habilitar/desactivar, G4 desplegar app, G5 activar reglas, G6 desactivar reglas, G7 política CASB, G8 DEM, G9 monitoreo).

#### Tipos de Application (Axis)
`Web`, `Rdp`, `RdpPool`, `Ssh`, `Database`, `NetworkRange`, `SshRange`, `Git`, `Saas`, `Vnc`, `ActiveDirectory`, `Saml`

#### Tipos de Connector Zone
- **type**: `Regular`, `InternetZone`, `ExternalPublicZone`
- **purpose**: `Access`, `LogStreaming`

#### Ejemplo: crear una aplicación web en Axis
```python
# 1. Ver las zonas disponibles
axis_list_connector_zones()

# 2. Crear la aplicación (dry-run)
axis_create_application(
    name="mi-app-web",
    app_type="Web",
    connector_zone_id="zone-id-aqui",
    confirm=False
)

# 3. Aplicar
axis_create_application(
    name="mi-app-web",
    app_type="Web",
    connector_zone_id="zone-id-aqui",
    confirm=True
)

# 4. Persistir
axis_commit(confirm=True)
```

### 1.5 Workflows (ZTP, Overlays)

| Tool | Uso |
|------|-----|
| `prepare_ztp_adoption` / `apply_ztp_plan` / `verify_ztp_plan` / `rollback_ztp_plan` | ZTP transaccional (dry-run → apply → verify → rollback). |
| `prepare_bulk_ztp_adoption` / `apply_bulk_ztp_plan` / `list_bulk_ztp_plans` | ZTP masivo por seriales. |
| `prepare_overlay_clone` / `apply_overlay_plan` / `verify_overlay_plan` / `rollback_overlay_plan` | Clonar BIO/overlay. |
| `apply_change(operation_id, body_json, confirm)` | Ejecutar cualquier operación del catálogo (dry-run por defecto). |

### 1.6 Monitoreo y red

| Tool | Uso |
|------|-----|
| `get_wan_health` | Latency/jitter/loss/MOS por túnel. |
| `get_mos` / `get_availability` / `get_top_talkers` | KPIs de calidad. |
| `get_brownout_state` / `get_ha_status` / `get_firmware_compliance` | Estado operacional. |
| `get_tunnel_state` / `troubleshoot_tunnel` | Túneles site-to-site + remedios. |
| `get_bgp_neighbors` / `get_sse_status` | BGP y SSE (Zscaler/Netskope/Axis vía Orchestrator). |
| `get_ddos_status` / `get_zone_matrix` / `get_deployment_config` | Seguridad y config. |
| `list_appliances` / `list_discovered_appliances` | Inventario. |
| `list_api_operations(search)` | Buscar operaciones del catálogo. |
| `call_read_api` / `orchestrator_info` / `orchestrator_metrics` | API genérica e info. |
| `dashboard_snapshot` / `dashboard_render` | Dashboard NOC (EdgeConnect + Axis): JSON + HTML autocontenido. |
| `dashboard_remote_config` / `dashboard_deploy_remote` / `dashboard_remote_status` / `dashboard_refresh_remote` | Dashboard remoto: despliegue vía SSH a Ubuntu (nginx). Variables SSH en el panel web. Ver **G10**. |

### 1.7 Guías por tarea — Axis Security (SSE)

Cómo estructurar cada tipo de tarea sobre los 55 tools `axis_*`. **Regla universal de escritura**:
1. Dry-run: llamar sin `confirm` → muestra exactamente qué se ejecutaría.
2. Aplicar: repetir con `confirm=true` (requiere `EC_ALLOW_WRITE_TOOLS=true`).
3. **Persistir**: `axis_commit(confirm=true)` — sin commit, nada se aplica.

Las listas `*_json` son **strings JSON** (p.ej. `'[{"id":"abc"}]'`). `included_ips`, `included_domains`, `excluded_domains`, `ip_ranges` son **strings separados por comas**.

#### G1. Escritura genérica (crear / actualizar / borrar cualquier entidad)
Patrón para cualquier recurso (Tags, Applications, Connectors, ConnectorZones, IpCategories, WebCategories, SslExclusions, Groups, Users, Locations, SubLocations, Tunnels):
```python
# 1. Verificar estado actual
axis_list_applications()                 # o axis_get_application(app_id)
# 2. Dry-run
axis_create_application(name="...", app_type="Web", connector_zone_id="...", confirm=False)
# 3. Aplicar
axis_create_application(name="...", app_type="Web", connector_zone_id="...", confirm=True)
# 4. Persistir
axis_commit(confirm=True)
```
Para borrar: `axis_delete_*(id, confirm=True)` → `axis_commit(confirm=True)`.

#### G2. Troubleshooting (diagnóstico)
```python
# ¿La plataforma Axis está sana?
axis_health()                            # status: Healthy / Degraded / Unhealthy + componentes
# ¿Qué connectors hay y cómo están?
axis_list_connectors()                   # inventario
axis_connector_status(connector_id="...")  # status + CPU/mem/disk/red por connector
# ¿Los túneles IPSec están arriba?
axis_list_tunnels()
axis_tunnel_status(tunnel_id="...")      # status: Online / Offline / Error / Unknown
# ¿Una app responde?
axis_get_application(app_id="...")       # verificar enabled + connectorZoneId
```
**Interpretación de `ConnectorStatus`**: `Unavailable` (caído — revisar host/IP pública), `Pending` (regenerar comando de instalación con `axis_regenerate_connector`), `AvailableTcpOnly`/`AvailableUdpOnly` (conectividad parcial — revisar NAT/firewall), `Available` (sano), `AvailableAgentlessOnly` (sin agente — apps con agente no funcionarán).
**Umbrales de alerta**: CPU/mem/disk ≥ 80% = warning, ≥ 90% = crítico.

#### G3. Configuración — habilitar / desactivar entidades
> ⚠️ **Trampa**: `axis_update_application` y `axis_update_connector` **siempre** envían `enabled` en el body, con default `True`. Para desactivar hay que pasar `enabled=False` explícito. Para cambiar solo el nombre/zona sin tocar el estado, leer primero con `axis_get_*` y pasar el `enabled` actual.
```python
# Desactivar una app
axis_update_application(app_id="...", enabled=False, confirm=True)
axis_commit(confirm=True)
# Reactivar
axis_update_application(app_id="...", enabled=True, confirm=True)
axis_commit(confirm=True)
# Desactivar un connector (saca el tráfico del pool)
axis_update_connector(connector_id="...", enabled=False, confirm=True)
axis_commit(confirm=True)
# Renombrar SIN cambiar estado (este tool no toca enabled)
axis_update_connector_zone(zone_id="...", name="nuevo-nombre", confirm=True)
axis_commit(confirm=True)
```

#### G4. Despliegue de una aplicación
Orden recomendado: **zona → tag (opcional) → aplicación → commit**.
```python
# 1. Verificar la zona destino
axis_list_connector_zones()
# 2. (Opcional) crear tag para agrupar
axis_create_tag(name="apps-criticas", confirm=True)
# 3. Dry-run de la app
axis_create_application(
    name="crm-interno",
    app_type="Web",                      # Web|Rdp|RdpPool|Ssh|Database|NetworkRange|SshRange|Git|Saas|Vnc|ActiveDirectory|Saml
    connector_zone_id="zone-id",
    tags_json='[{"id":"tag-id"}]',       # opcional
    confirm=False,
)
# 4. Aplicar
axis_create_application(name="crm-interno", app_type="Web", connector_zone_id="zone-id",
                        tags_json='[{"id":"tag-id"}]', confirm=True)
# 5. App de tipo NetworkRange: pasar network_range_json
axis_create_application(
    name="red-servidores",
    app_type="NetworkRange",
    connector_zone_id="zone-id",
    network_range_json='{"ipRangesOrCIDRs":["10.20.0.0/16"],"portsAndProtocols":["TCP/443","TCP/22"],"enableIcmp":true}',
    confirm=True,
)
# 6. Persistir
axis_commit(confirm=True)
```

#### G5. Activación de reglas (web filtering / SSL inspection)
```python
# 1. Crear categoría web (dominios a bloquear/permitir)
axis_create_web_category(
    name="bloqueo-redes-sociales",
    included_domains="facebook.com,instagram.com,tiktok.com",
    connector_zone_id="zone-id",
    confirm=True,
)
# 2. Crear categoría IP custom
axis_create_ip_category(
    name="ips-maliciosas",
    included_ips="203.0.113.10/32,198.51.100.0/24",
    connector_zone_id="zone-id",
    confirm=True,
)
# 3. Exclusión SSL (dominios que no se inspeccionan)
axis_create_ssl_exclusion(
    name="excepcion-banca",
    exclusion_type="Custom",             # Predefined | Custom
    excluded_domains="banco.com,visa.com",
    confirm=True,
)
# 4. Persistir todo junto
axis_commit(confirm=True)
```

#### G6. Desactivación de reglas
```python
# Desactivar una app (regla de acceso) — ver trampa en G3
axis_update_application(app_id="...", enabled=False, confirm=True)
# Borrar categoría web / IP / exclusión SSL
axis_delete_web_category(category_id="...", confirm=True)
axis_delete_ip_category(category_id="...", confirm=True)
axis_delete_ssl_exclusion(exclusion_id="...", confirm=True)
# Persistir
axis_commit(confirm=True)
```

#### G7. Generación de política CASB
Secuencia completa: **zona → categorías web/IP → tag → aplicaciones con tag → commit**.
```python
# 1. Zona destino (acceso de usuarios)
axis_list_connector_zones()
# 2. Categorías de la política (ver G5) — una por tema
axis_create_web_category(name="casb-social", included_domains="facebook.com,twitter.com",
                         connector_zone_id="zone-id", confirm=True)
axis_create_web_category(name="casb-gambling", included_domains="bet365.com,poker.com",
                         connector_zone_id="zone-id", confirm=True)
axis_create_ip_category(name="casb-tor-exit", included_ips="185.220.101.0/24",
                        connector_zone_id="zone-id", confirm=True)
# 3. Tag que agrupa las apps sujetas a la política
axis_create_tag(name="politica-casb-2026", confirm=True)
# 4. Crear/actualizar apps asociando el tag
axis_create_application(name="app-afectada", app_type="Web", connector_zone_id="zone-id",
                        tags_json='[{"id":"tag-id"}]', confirm=True)
# 5. Persistir
axis_commit(confirm=True)
```

#### G8. DEM (Digital Experience Monitoring) — despliegue de medición
Secuencia: **zona LogStreaming → location → sub-location (CIDRs) → túnel IPSec → connector → commit**.
```python
# 1. Zona dedicada a monitoreo (NO de acceso de usuarios)
axis_create_connector_zone(name="dem-monitoring", zone_type="Regular",
                           purpose="LogStreaming", confirm=True)   # purpose: Access|LogStreaming
# 2. Location (sitio medido)
axis_create_location(name="sede-monterrey", confirm=True)   # → devuelve id
# 3. Sub-location con los rangos internos del sitio
axis_create_sub_location(location_id="loc-id", name="lan-monterrey",
                         ip_ranges="10.50.0.0/24,10.51.0.0/24", confirm=True)
# 4. Túnel IPSec hacia el PoP (ver axis_list_ipsec_locations para PoPs)
axis_create_tunnel(name="tun-monterrey", location_id="loc-id",
                   auth_id="MONTERREY-POP", auth_psk="<psk-segura>", confirm=True)
# 5. Connector dedicado al monitoreo en la zona DEM
axis_create_connector(name="conn-dem-mty", connector_zone_id="zone-dem-id", confirm=True)
# 6. Obtener el comando de instalación para el host del connector
axis_regenerate_connector(connector_id="conn-id", confirm=True)  # → command
# 7. Persistir
axis_commit(confirm=True)
```

#### G9. Monitoreo (loop NOC por turno)
```python
# 1. Salud de plataforma
axis_health()                            # Healthy?
# 2. Estado de todos los connectors
axis_list_connectors()                   # ids
axis_connector_status(connector_id="...")  # repetir por connector: status, CPU, mem, disk, red
# 3. Estado de túneles
axis_list_tunnels()
axis_tunnel_status(tunnel_id="...")      # repetir: Online?
# 4. Inventario de apps habilitadas
axis_list_applications()                 # enabled=true?
# Alertas: status != Available, CPU/mem/disk ≥ 80%, túnel != Online → diagnosticar con G2
```

#### G10. Dashboard NOC (EdgeConnect + Axis) — generar, previsualizar y desplegar en servidor

El dashboard es un **HTML autocontenido** (sin dependencias externas) que se puede previsualizar al momento o **desplegar fijo en un servidor Ubuntu vía SSH** (instala nginx y publica `index.html`). No queda solo en la respuesta: queda sirviendo en `http://<servidor>:8090/`.

**Tools:**
| Tool | Uso |
|------|-----|
| `dashboard_snapshot` | JSON compacto: inventario + reachability + WAN health + túneles + alarmas + HA (EdgeConnect) y health/connectors/túneles (Axis). Solo lectura. |
| `dashboard_render(refresh_seconds)` | Genera el HTML interactivo autocontenido (auto-refresh). Solo lectura. |
| `dashboard_remote_config` | Estado de la config remota (qué falta). Nunca devuelve el password. |
| `dashboard_deploy_remote(install, confirm)` | **Instala en el Ubuntu remoto**: nginx + `index.html` vía SSH/SFTP. Dry-run por defecto; `confirm=true` para aplicar. |
| `dashboard_remote_status` | Verifica en el remoto: nginx activo + archivo presente + puerto escuchando. Solo lectura. |
| `dashboard_refresh_remote(confirm)` | Regenera con datos vivos y re-sube al remoto ya instalado (para cron). Dry-run por defecto. |

**Variables (panel web → Variables → "Dashboard remoto (SSH)", o `.env`):**
```bash
EC_DASHBOARD_REMOTE_ENABLED=true
EC_DASHBOARD_REMOTE_HOST=10.0.0.5        # IP del servidor Ubuntu
EC_DASHBOARD_REMOTE_USER=ubuntu
EC_DASHBOARD_REMOTE_PASSWORD=...         # o EC_DASHBOARD_REMOTE_KEY_PATH=/ruta/llave
# EC_DASHBOARD_REMOTE_PORT=22
# EC_DASHBOARD_PORT=8090                  # puerto HTTP del dashboard en el remoto
# EC_DASHBOARD_DIR=/var/www/ec-mcp-dashboard
# EC_DASHBOARD_REFRESH_SECONDS=30
```
El usuario remoto necesita **sudo** (el instalador hace `apt-get install nginx`).

**Flujo de despliegue (vía MCP):**
```python
# 1. Verificar config remota
dashboard_remote_config()                # -> configured: true/false + missing
# 2. Dry-run del despliegue
dashboard_deploy_remote(install=True, confirm=False)   # muestra qué hará
# 3. Instalar (nginx + subir dashboard)
dashboard_deploy_remote(install=True, confirm=True)
# -> devuelve url: http://<host>:8090/
# 4. Verificar
dashboard_remote_status()
# 5. Refrescar datos (cron cada 5 min recomendado)
dashboard_refresh_remote(confirm=True)
```

**Panel web (`ec-mcp control plane`)**: solo administra **variables** y **actualizaciones**. Las variables de conexión SSH al servidor remoto se editan en **Variables → "Dashboard remoto (SSH)"** (usuario/contraseña/IP) → Guardar y reiniciar. El panel **no** despliega ni previsualiza el dashboard: eso se hace por los tools MCP de arriba.

**Reglas:**
- El despliegue remoto es una **escritura** (requiere `EC_ALLOW_WRITE_TOOLS=true` + `confirm=true`).
- El instalador es **idempotente**: reinstalar no rompe nginx ni el sitio.
- El HTML generado incluye auto-refresh (`EC_DASHBOARD_REFRESH_SECONDS`); para datos vivos continuos usar `dashboard_refresh_remote` vía cron local.
- El dashboard nunca expone secretos: el payload pasa por redacción antes de renderizar.


---

## 2. Panel web de administración (`ec-mcp control plane`)

El MCP incluye un **panel web** (`ec-mcp admin`, puerto 8080 por defecto) que es **solo de administración**:
- Editar **todas las variables** de `.env` (solo las necesarias son obligatorias, el resto opcionales)
- Ver el estado de los servicios
- **Reiniciar el MCP** para aplicar los cambios
- Gestionar orquestadores (múltiples URLs/credenciales)
- **Actualizaciones** desde GitHub (detectar, confirmar y aplicar)

> El panel **no** ejecuta operaciones de red (no despliega dashboards ni conecta por SSH a otros servidores). Esas acciones se hacen por los **tools MCP**. El panel solo expone las variables para configurarlas.

**Variables ahora editables en el panel (incluye Axis y Dashboard remoto):**
- Orchestrator: URL, API key, user, password, verify TLS
- SSH: enabled, host, user, password, enable password, port, auth method
- **Axis Security: enabled, admin token (Bearer JWT), base URL, verify TLS, timeout**
- **Dashboard remoto (SSH): enabled, host, user, password/key, puerto SSH, puerto dashboard, directorio, refresh**
- Servidor MCP: host, port, auth token, admin password
- Seguridad: write tools, dangerous writes, rate limits, output chars, cache TTL

**Flujo:**
1. Abrir `http://<host>:8080`
2. Login con `EC_ADMIN_PASSWORD`
3. Editar variables → Guardar
4. "Reiniciar servicios" → el MCP recarga con la nueva config

**Actualización desde el panel (worker web):**
1. Pestaña **Actualizaciones** → "Detectar GitHub" → muestra commit instalado vs remoto.
2. Si hay update, escribe la frase de confirmación exacta → "Aplicar actualización".
3. El worker (`ec-mcp-update.service`, corre como **root**) hace `git fetch` + `merge --ff-only` + instala deps + corre tests + reinicia servicios. Si falla, hace rollback automático al commit anterior.

**Requisito de permisos (fix conocido):** el worker hace `git fetch` como el **dueño del proyecto**. Si el checkout quedó con `.git` propiedad de root (o el FS es read-only para el usuario del servicio), `git fetch` falla con `cannot open '.git/FETCH_HEAD': Read-only file system`. El worker ahora corrige solo el propietario (`chown -R <owner>: .git`) antes de fetch; si no puede, el diagnóstico indica el `chown` exacto. Además el unit `ec-mcp-update.service` ya no usa `ProtectHome=read-only` (rompe proyectos bajo `/home`).

---

## 3. Runbooks NOC

### 3.1 Chequeo de salud general (cada turno)
```python
get_orchestrator_infrastructure()      # Orchestrator sano
list_appliances()                      # Inventario + reachability
get_security_posture(appliance_id="all")  # Posture de seguridad
correlate_incidents()                  # Incidentes correlacionados
```

### 3.2 Túnel caído
```python
troubleshoot_tunnel(appliance_id="...")  # Diagnóstico + remedios
get_tunnel_state(appliance_id="...")     # Estado de túneles
get_wan_health(appliance_id="...")       # Calidad WAN
```

### 3.3 Sospecha de ataque
```python
correlate_incidents()                          # Detectar
list_response_options(target="x.x.x.x", context="scan")  # Ver opciones
block_threat(target="x.x.x.x", category="BLOCKED-SEC", confirm=True)  # Bloquear
```

### 3.4 SSH no conecta a un appliance
```python
get_ssh_network_path(appliance_id="...")   # ¿LAN o WAN?
# Si WAN y falla:
ensure_ssh_inbound_forwarding(appliance_id="...", confirm=True)  # Crear port-forward
run_show_command("show version", host="...")  # Verificar
```

### 3.4b SSH intermitente / timeouts esporádicos (7.0.1)
```python
# 1. Verificar la ruta de red primero
get_ssh_network_path(appliance_id="...")     # LAN o WAN, IP esperada
# 2. Si falla con timeout transitorio, el MCP ya reintentó EC_SSH_RETRIES veces.
#    Ajustar timeouts en el panel web (Variables → SSH) o .env:
#    EC_SSH_CONNECT_TIMEOUT=45
#    EC_SSH_COMMAND_TIMEOUT=60
#    EC_SSH_RETRIES=2                          # máximo recomendado
# 3. Guardar y reiniciar el servicio.
# 4. Si persiste: probar conectividad manual
run_show_command("show version", host="<nombre-appliance>")  # host = nombre o nePk, NUNCA IP
# 5. Si auth falla: revisar EC_SSH_USER / EC_SSH_PASSWORD / EC_SSH_AUTH_METHOD en el panel.
```

### 3.4c SD-WAN AI no responde (SASE Copilot)
```python
# 1. ¿Está habilitado el feature?
get_sase_copilot_status()                    # -> {"sase_copilot": {"enabled": true/false}}
# 2. Si enabled=false -> habilitar en el Orchestrator (advanced property) o no usar ask_sdwan_ai.
# 3. Si enabled=true pero ask_sdwan_ai falla:
ask_sdwan_ai(question="¿Cuál es el estado del túnel principal?")   # ver el error exacto
# 4. Verificar rol de la API key: /sdwanai/search requiere READ_WRITE.
# 5. Si la respuesta está truncada:
ask_sdwan_ai(question="...", max_events=500)  # bajar max_events (techo duro: 2000)
# 6. Limpiar contexto si la conversación se desvirtuó (requiere EC_ALLOW_WRITE_TOOLS=true):
clear_sdwan_ai_context()
```

### 3.5 Axis Security — onboarding de aplicación
Ver guía **G4** (§1.7). Resumen:
```python
axis_health()                              # Plataforma sana
axis_list_connector_zones()                # Zonas disponibles
axis_create_application(name="app", app_type="Web", connector_zone_id="...", confirm=True)
axis_commit(confirm=True)                  # Persistir
```

### 3.6 Axis Security — revisar connector
Ver guía **G2** (§1.7). Resumen:
```python
axis_list_connectors()
axis_connector_status(connector_id="...")  # CPU/mem/disk/red
```

### 3.7 Axis Security — onboarding de connector nuevo
```python
axis_health()                              # Plataforma sana
axis_list_connector_zones()                # elegir zona
# 1. Crear el connector (dry-run → confirm)
axis_create_connector(name="conn-sede-x", connector_zone_id="zone-id", confirm=True)
# 2. Obtener el comando de instalación para el host
axis_regenerate_connector(connector_id="conn-id", confirm=True)  # → command (instalar en el host)
# 3. Persistir
axis_commit(confirm=True)
# 4. Verificar que levantó
axis_connector_status(connector_id="conn-id")   # status debe pasar a Available
```

### 3.8 Axis Security — desplegar política CASB / sitio DEM
Ver guías **G7** (CASB) y **G8** (DEM) en §1.7. Ambas terminan con `axis_commit(confirm=True)`.

### 3.9 Axis Security — loop de monitoreo por turno
Ver guía **G9** (§1.7): `axis_health` → `axis_list_connectors` + `axis_connector_status` → `axis_list_tunnels` + `axis_tunnel_status` → `axis_list_applications`. Alertar si: status ≠ `Available`, CPU/mem/disk ≥ 80%, o túnel ≠ `Online`.

### 3.10 Dashboard NOC — desplegar en servidor Ubuntu (fijo y estable)
Ver guía **G10** (§1.7). Resumen:
```python
# 1. Configurar en panel web: Variables → Dashboard remoto (SSH) → guardar y reiniciar
# 2. Verificar config
dashboard_remote_config()
# 3. Instalar (nginx + dashboard) en el remoto — dry-run primero
dashboard_deploy_remote(install=True, confirm=True)   # -> http://<host>:8090/
# 4. Verificar y refrescar
dashboard_remote_status()
dashboard_refresh_remote(confirm=True)                 # para cron cada 5 min
```
Las variables SSH del servidor remoto se configuran en el panel web: **Variables → "Dashboard remoto (SSH)"** → Guardar y reiniciar. El despliegue se ejecuta por MCP (arriba).

---

## 4. Reglas de oro

1. **Dry-run primero**: todas las escrituras (`apply_change`, `block_threat`, `axis_create_*`, `run_cli_command`, `clear_sdwan_ai_context`, `dashboard_deploy_remote`) son dry-run sin `confirm=true`.
2. **Commit en Axis**: los cambios en Axis no persisten sin `axis_commit(confirm=true)`. Para cualquier tarea de Axis, estructurar la secuencia según las **guías G1–G10 de §1.7** (escritura, troubleshooting, config, despliegue, reglas, CASB, DEM, monitoreo).
3. **SSH WAN**: usar la IP de la interfaz WAN del appliance, nunca la pública/NAT. Si falla, crear inbound forwarding.
4. **SSH resiliente (7.0.1)**: ante timeouts esporádicos, el MCP reintenta automáticamente (`EC_SSH_RETRIES`). Ajustar `EC_SSH_CONNECT_TIMEOUT` / `EC_SSH_COMMAND_TIMEOUT` antes de escalar. Nunca subir `EC_SSH_RETRIES` por encima de 2.
5. **SD-WAN AI (7.0.0)**: `ask_sdwan_ai` requiere SASE Copilot habilitado + rol READ_WRITE. `clear_sdwan_ai_context` exige `EC_ALLOW_WRITE_TOOLS=true`. El SSE tiene techo de 2000 eventos / 2 MB.
6. **Operar por fases (MCP_OPERATIONS)**: la IA detecta y propone; **nunca aplica** sin aprobación explícita. Respetar las 4 plantillas de política (Observación, Contenición propuesta, Cambio controlado, Emergencia).
7. **POST /deployment es REPLACE**: nunca enviar body parcial sin `modeIfs` (borra interfaces).
8. **NO tocar `0.NE` (ECV-CALIMAYA)**: es la salida a internet del lab.
9. **Secretos**: el panel web enmascara valores secretos; nunca loguearlos. Si un secreto se expone, seguir `SECURITY.md` (rotar inmediatamente).
10. **Panel web**: solo exponer en localhost o detrás de reverse proxy con auth.
11. **Contrato de respuesta**: toda respuesta operativa debe traer resultado, fuente, tiempo, truncamiento y error normalizado. Si falta alguno, tratarla como incompleta.
