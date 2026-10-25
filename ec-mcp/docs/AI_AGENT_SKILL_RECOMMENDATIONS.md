# Recomendaciones para un Skill / Agente de IA sobre ec-mcp

Documento de diseño para construir un **skill** (Claude Skills, Cursor, Le Chat, etc.) o un
**agente equivalente** que opere entornos HPE Aruba EdgeConnect a través del servidor MCP
`ec-mcp` (v8.1.0). Complementa los skills existentes:

- `EDGECONNECT_NOC_OPS_SKILL.md` — operación NOC (monitoreo, diagnóstico, runbooks).
- `EDGECONNECT_EXPERT_SKILL.md` — conocimiento experto del dominio (hallazgos de contrato, licenciamiento, ZTP).
- `EDGECONNECT_TROUBLESHOOTING_CATALOG.md` — catálogo de troubleshooting por dominio.
- `MCP_OPERATIONS.md` — hoja de ruta de seguridad operativa (seguimiento #88).

---

## 1. Principios de diseño del agente

### 1.1 Modelo de permisos por defecto (fail-closed)

El agente debe asumir que el servidor MCP arranca **sin permisos de escritura**:

| Variable | Default seguro | Efecto |
|---|---|---|
| `EC_ALLOW_WRITE_TOOLS` | `false` | Todas las tools de escritura lanzan `SecurityError`. |
| `EC_ALLOW_DANGEROUS_WRITES` | `false` | Bloquea operaciones con `reboot|suspend|delete|remove|wipe|factory|purge|halt|shutdown|decommission`. |
| `EC_MAX_WRITES_PER_MINUTE` | `10` | Rate limit de escrituras. |
| `EC_SSH_ENABLED` | `false` | SSH deshabilitado; usar `run_show_api` (vía Orchestrator). |
| `EC_VERIFY_TLS` | `true` | Verificación TLS obligatoria. |

**Regla del agente:** nunca pedir al usuario que habilite escrituras "para acelerar".
Proponer primero el flujo dry-run y, si el usuario insiste, instruir cómo habilitarlo
explícitamente y documentar la razón en el plan de cambio.

### 1.2 Patrón dry-run → confirmación → ejecución → verificación

Toda acción que cambie estado debe seguir este ciclo, usando las tools transaccionales:

```text
prepare_* / preview_*  →  dry-run (devuelve diff + frase de confirmación exacta)
        ↓
apply_*(plan_id, confirmation=<frase exacta>, confirm=true)
        ↓
verify_* / get_*_status  →  evidencia de que el cambio quedó aplicado
        ↓
rollback_*(plan_id, confirmation, confirm=true)   →  solo si la verificación falla
```

El agente **no debe** llamar a `apply_*` sin antes haber mostrado el resultado de
`prepare_*`/`preview_*` al usuario. La frase de confirmación es específica del plan
y expira con él; si cambia, hay que regenerar el plan.

### 1.3 Nunca inventar identificadores

- Los appliances se referencian por **nePk** (`1.NE`), nombre, IP o serial; el servidor
  resuelve contra el inventario. El agente debe preferir `list_appliances` antes de operar.
- No asumir `0.NE` ni ningún nePk concreto: el lab usa `0.NE` como salida a internet y
  **está prohibido tocarlo** (regla de oro del skill NOC).
- Las operaciones de API genérica usan `operation_id` del catálogo (`list_api_operations`),
  no rutas hardcodeadas.

### 1.4 Respuestas siempre con evidencia

Cada respuesta operativa del agente debe citar la tool usada, el nePk/alcance y el
resultado (o el error normalizado). El servidor ya redacta secretos en auditoría y
salidas; el agente no debe pedir ni repetir credenciales.

---

## 2. Capacidades del servidor (inventario real: 125 tools, v8.1.0)

| Dominio | Tools | # | Tipo |
|---|---|---|---|
| Axis Security SSE | `axis_*` (55: CRUD de tags, apps, connectors, zones, IP/web categories, SSL exclusions, groups, users, locations, sublocations, tunnels, certificates, IPsec PoP, health, commit) | 55 | Lectura + escritura (requiere `EC_AXIS_ENABLED` + `EC_AXIS_ADMIN_TOKEN`) |
| ZTP / Onboarding | `prepare_ztp_adoption`, `apply_ztp_plan`, `preview_ztp_plan`, `verify_ztp_plan`, `rollback_ztp_plan`, `prepare_bulk_ztp_adoption`, `apply_bulk_ztp_plan`, `list_bulk_ztp_plans`, `get_ztp_status`, `get_ztp_apply_status`, `list_discovered_appliances` | 11 | Workflow transaccional |
| Red / Túneles / BGP / HA | `get_wan_health`, `get_mos`, `get_tunnel_state`, `get_brownout_state`, `get_availability`, `get_top_talkers`, `get_ha_status`, `get_firmware_compliance`, `get_bgp_neighbors`, `get_site_to_site_tunnels`, `get_sse_status` | 11 | Solo lectura |
| Seguridad / Incidentes | `get_active_alarms`, `get_ids_ips_state`, `get_ids_ips_events`, `get_security_log`, `get_security_posture`, `get_ddos_status`, `get_zone_matrix`, `get_deployment_config`, `list_response_options`, `block_threat` | 10 | Lectura + `block_threat` (escritura, dry-run por defecto) |
| Dashboard NOC | `dashboard_snapshot`, `dashboard_render`, `dashboard_remote_config`, `dashboard_remote_status`, `dashboard_deploy_remote`, `dashboard_refresh_remote` | 6 | Lectura + despliegue remoto (escritura, confirm) |
| CLI / SSH | `run_show_api`, `run_show_command`, `run_cli_command`, `list_cli_commands`, `get_ssh_network_path`, `ensure_ssh_inbound_forwarding` | 6 | `show` por API (seguro); SSH opcional; `run_cli_command` y `ensure_ssh_inbound_forwarding` son escritura |
| Overlays / BIO | `prepare_overlay_clone`, `apply_overlay_plan`, `preview_overlay_plan`, `verify_overlay_plan`, `rollback_overlay_plan`, `list_overlay_sources` | 6 | Workflow transaccional |
| SD-WAN AI embebida | `ask_sdwan_ai`, `get_sdwan_ai_chat_logs`, `clear_sdwan_ai_context`, `get_sase_copilot_status` | 4 | Conversacional (Orchestrator 10.0) |
| Telemetría / Salud | `get_orchestrator_infrastructure`, `get_appliance_infrastructure`, `get_realtime_stats`, `get_appliance_health` | 4 | Solo lectura |
| Troubleshooting asistido | `troubleshoot_flows`, `troubleshoot_tunnel`, `correlate_incidents`, `propose_remediation` | 4 | Solo lectura (devuelve hallazgos + remedios) |
| API genérica | `list_api_operations`, `call_read_api`, `apply_change` | 3 | Lectura + escritura genérica (`apply_change`, dry-run por defecto) |
| Inventario | `list_appliances`, `orchestrator_info`, `orchestrator_metrics` | 3 | Solo lectura |

**Distribución de riesgo:** 73 tools son solo lectura/diagnóstico; 48 cambian estado
(todas detrás de `EC_ALLOW_WRITE_TOOLS` + `confirm=true`; las peligrosas además de
`EC_ALLOW_DANGEROUS_WRITES`); 2 (`troubleshoot_*`) son orquestación de solo lectura.

---

## 3. Matriz de decisión: ¿qué tool usar cuándo?

| Intención del usuario | Tool(s) recomendadas | Escritura |
|---|---|---|
| "¿Qué appliances hay / cuál es su estado?" | `list_appliances` → `get_appliance_health` / `get_realtime_stats` | No |
| "¿El Orchestrator está sano?" | `get_orchestrator_infrastructure`, `orchestrator_info`, `orchestrator_metrics` | No |
| "Hay un túnel caído" | `troubleshoot_tunnel` (antes que `get_tunnel_state` + `get_brownout_state` por separado) | No |
| "Algo va lento / una app no funciona" | `troubleshoot_flows` (correlaciona top talkers + flujos + log firewall del día) | No |
| "Sospecha de ataque / hay drops" | `correlate_incidents` → `propose_remediation` (propuestas dry-run con evidencia/riesgo/reversión) → `list_response_options` → (`block_threat` con confirm) | Opcional |
| "Ver comandos show por CLI" | `run_show_api` (vía Orchestrator, **sin SSH**) — preferir sobre `run_show_command` | No |
| "Onboarding de appliance nuevo" | `list_discovered_appliances` → `prepare_ztp_adoption` → `preview_ztp_plan` → `apply_ztp_plan` → `verify_ztp_plan` / `get_ztp_apply_status` | Sí (flujo transaccional) |
| "Onboarding masivo" | `prepare_bulk_ztp_adoption` → `apply_bulk_ztp_plan` → `list_bulk_ztp_plans` | Sí |
| "Clonar una política/overlay" | `list_overlay_sources` → `prepare_overlay_clone` → `preview_overlay_plan` → `apply_overlay_plan` → `verify_overlay_plan` | Sí |
| "Cambiar algo puntual por API" | `list_api_operations(search=...)` → `apply_change` (dry-run primero) → `call_read_api` (verificar) | Sí |
| "Configurar Axis Security (SSE)" | `axis_health` → `axis_list_*` → `axis_create_*`/`axis_update_*` → **`axis_commit(confirm=true)`** | Sí |
| "Desplegar dashboard NOC en un servidor" | `dashboard_remote_config` → `dashboard_deploy_remote(install=true, confirm=true)` → `dashboard_remote_status` | Sí |
| "Preguntar al asistente del Orchestrator" | `get_sase_copilot_status` → `ask_sdwan_ai` (con `chat_id` para continuar) | No |
| "Ejecutar comando ECOS arbitrario" | `list_cli_commands` → `run_cli_command(confirm=true)` — **último recurso**, preferir `run_show_api` | Sí |

---

## 4. Guardrails que el agente debe imponer

1. **Dry-run primero, siempre.** Ninguna `apply_*`/`block_threat`/`axis_commit`/`run_cli_command`
   sin `confirm=true`, y nunca sin haber mostrado antes el resultado de la fase de preview.
2. **Frase de confirmación exacta.** Los planes ZTP/overlay devuelven una `confirmation`
   que debe copiarse literalmente. Si el agente la parafrasea, el servidor rechaza.
3. **POST /deployment es REPLACE completo.** El servidor ya bloquea bodies parciales
   (`guard_partial_deployment_body`), pero el agente debe preferir el flujo
   GET → clonar → modificar → POST completo, y nunca proponer enviar solo una sección.
4. **No tocar `0.NE`** ni la salida a internet del entorno del usuario sin confirmación
   explícita por escrito.
5. **SSH: ruta correcta.** Antes de `run_show_command`/`run_cli_command`, usar
   `get_ssh_network_path`. Si la ruta es WAN, avisar que hace falta inbound forwarding
   y proponer `ensure_ssh_inbound_forwarding` (dry-run primero).
6. **Axis: commit obligatorio.** Los cambios `axis_create_*`/`axis_update_*`/`axis_delete_*`
   quedan staged; sin `axis_commit(confirm=true)` no persisten. El agente debe cerrar
   siempre con commit + `axis_health`/`axis_connector_status`.
7. **Secretos fuera de contexto.** No pedir API keys ni contraseñas en el chat; si faltan,
   indicar la variable de `.env` correspondiente. El panel web enmascara secretos.
8. **Read-after-write.** Tras cualquier escritura confirmada, ejecutar la verificación
   (`verify_*_plan`, `call_read_api` con `verify_operation_id`, o `get_*_status`) y
   reportar evidencia, no solo "OK".
9. **Rate limit.** Respetar `EC_MAX_WRITES_PER_MINUTE` (default 10); ante un 429/rate-limit,
   esperar 60 s antes de reintentar (el Orchestrator también limita ~10/min).
10. **Versión del Orchestrator.** Antes de operar, `orchestrator_info`; si hay fallback de
    perfil (p. ej. 9.7 → 9.6, o 10.x futuro → 10.0), validar shapes en vivo antes de
    confiar en extractores (ver `PROFILE_VERSION_ROUTINE.md`).

---

## 5. Estructura sugerida del skill

```text
skill-ec-mcp/
├── SKILL.md                  # frontmatter + resumen (este documento, versión corta)
├── references/
│   ├── tool-map.md           # inventario 125 tools por dominio (sección 2)
│   ├── decision-matrix.md    # ¿qué tool cuándo? (sección 3)
│   ├── guardrails.md         # dry-run, confirmación, deployment REPLACE, rate limit
│   ├── ztp-workflow.md       # prepare → preview → apply → verify → rollback
│   ├── overlay-workflow.md   # clonación de BIO con diff y frase de confirmación
│   ├── axis-sse.md           # flujo Axis + commit obligatorio + guías G1–G10
│   ├── ssh-lan-wan.md        # rutas LAN/WAN, inbound forwarding, run_show_api vs SSH
│   └── sdwan-ai.md           # ask_sdwan_ai, chat_id, get_sase_copilot_status
├── examples/
│   ├── tunnel-down.md        # runbook: troubleshoot_tunnel → remedios
│   ├── incident-response.md  # correlate_incidents → propose_remediation → list_response_options → block_threat
│   └── ztp-onboarding.md     # alta de appliance con preconfig YAML
└── evals/
    └── evals.xml             # casos de prueba: dry-run por defecto, rechazo sin confirm, etc.
```

### Prompt del sistema (borrador)

> Operas entornos HPE Aruba EdgeConnect a través del servidor MCP `ec-mcp`.
> Reglas inviolables: (1) toda escritura pasa por dry-run → preview → confirmación exacta
> → apply → verificación; (2) nunca reveles ni solicites credenciales, usa las variables de
> `.env`; (3) identifica appliances por nePk vía `list_appliances`, nunca asumas;
> (4) ante túnel caído usa `troubleshoot_tunnel`, ante app lenta `troubleshoot_flows`;
> (5) en Axis, todo cambio termina en `axis_commit(confirm=true)`; (6) si el Orchestrator
> reporta fallback de perfil, valida contratos en vivo; (7) no toques la salida a internet
> del entorno sin confirmación explícita.

---

## 6. Deuda documental detectada (para corregir al actualizar el skill)

El skill `EDGECONNECT_NOC_OPS_SKILL.md` está etiquetado **v6.0.0 / 112 tools**; el servidor
actual (8.1.0) expone **125 tools**. Faltan por documentar:

- `get_ztp_status` — estado ZTP con filas paginadas sin credenciales.
- `get_ztp_apply_status` — seguimiento de la cadena de tareas async del apply (op 254).
- `list_overlay_sources` — lista de BIO existentes como fuentes seguras de clonación.
- `preview_ztp_plan` / `preview_overlay_plan` — devuelven candidato inmutable + diff + frase.
- `get_site_to_site_tunnels` — estado de túneles site-to-site (incluye bonded y SSE VGW).

Además, el README raíz usa `# gitleaks:allow` en 6 marcadores de ejemplos vacíos
(`EC_ORCHESTRATOR_API_KEY=  # gitleaks:allow; ...`), que son inofensivos (líneas vacías),
pero conviene alinearlos con `.env.example`, que no usa ese marcador.

---

## 7. Métricas de éxito del agente

- **0 escrituras sin dry-run previo** en evaluación.
- **100% de escrituras con read-after-write** (verificación posterior).
- **0 alucinaciones de nePk/operation_id** (todo resuelto vía `list_appliances`/`list_api_operations`).
- **Tiempo a diagnóstico** de túnel caído < 2 llamadas (`troubleshoot_tunnel`).
- **0 secretos en salidas** (el servidor redacta; el agente no debe solicitarlos).
