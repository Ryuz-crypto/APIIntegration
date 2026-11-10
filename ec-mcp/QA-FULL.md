# Protocolo completo de QA — ec-mcp 9.1.0

Usa [QA-BATTERY.md](QA-BATTERY.md) para T0–T6 y esta guía para ampliar cobertura. Referencia vigente: `main`, paquete `9.1.0`, y **SHA completo de la build aprobada para la sesión**. Ningún resultado de este documento declara que se haya ejecutado la prueba.

## Preparación y reglas

1. Acuerda entorno, appliances, integraciones, ventana y responsable; registra el SHA esperado antes de empezar.
2. Ejecuta T0 primero: `orchestrator_info({})` debe reportar versión y SHA coincidentes. Si no, T0 y sus dependientes son BLOCKED.
3. Registra Orchestrator/version/profile, alcance de inventario, transporte y estados de escritura/SSH. Comprueba el perfil activo y las operaciones publicadas; no fijes una versión de Orchestrator o número de equipos.
4. Usa estados PASS, FAIL, BLOCKED, SKIPPED_NO_ENTITY y SKIPPED_NOT_CONFIGURED como define QA-BATTERY. Un 403, timeout o error de parsing no es entidad ausente.
5. Cada caso registra invocación, fecha UTC, target, ventana, esperado, observado, estado, evidencia saneada y referencia de issue. Compara datos vivos con el origen y tiempo equivalentes; no subas payloads crudos con secretos o datos de clientes.
6. Solo lectura y verificaciones de candados/dry-run. Ningún `confirm=true`, cambio de forwarding, adopción, borrado, commit Axis ni despliegue remoto sin autorización específica separada. No cambies roles ni credenciales para forzar un PASS.
7. JSON truncado con indicador es respuesta parcial: reduce alcance o campos y repite. No declares PASS de integridad si faltan datos. Las salidas de texto CLI se evalúan como texto.

## T0–T6 — Aceptación esencial

Ejecuta íntegramente [QA-BATTERY.md](QA-BATTERY.md): identidad, inventario, alarmas, WAN/MOS, catálogo/API, CLI por API y seguridad/redacción. Conserva resultados separados para cada T.

## A — KPI y estado operativo

| Caso | Invocación | Criterio |
|---|---|---|
| A1 | `get_active_alarms({"appliance_id":"all"})` | Contrastar conteos y severidades con individuales en la misma ventana; registrar cambios entre consultas. |
| A2 | `get_active_alarms({"appliance_id":"<nePk>"})` | Identidad y datos coinciden con el origen vivo. Repetir por equipo en alcance. |
| A3 | `get_wan_health({"appliance_id":"all"})` | JSON válido; identificar respuestas parciales y repetir por equipo/campos. |
| A4 | `get_wan_health({"appliance_id":"all","fields":"mos,min_mos"})` | Proyección coherente con campos existentes; no confundir campo ausente con dato cero. |
| A5 | `get_wan_health({"appliance_id":"<nePk>"})` | Selección y datos corresponden al equipo. |
| A6 | `get_mos({"appliance_id":"<nePk>","granularity":"day"})` | Registrar ventana y escala; contrastar valores crudos antes de normalizar. |
| A7 | `get_tunnel_state({"appliance_id":"<nePk>"})` | Comparar con inventario de túneles y distinguir tipos. |
| A8 | `get_brownout_state({"appliance_id":"<nePk>"})` | Estado y razones coherentes; sin entidad solo si se verifica. |
| A9 | `get_availability({"appliance_id":"all","granularity":"hour"})` | Datos consistentes o SKIPPED_NO_ENTITY si el origen no expone la entidad. |
| A10 | `get_top_talkers({"appliance_id":"<nePk>","granularity":"hour","limit":10})` | Contrastar ventana y fuente; vacío con tráfico observado es WARN para investigar, no PASS de datos. |
| A11 | `get_ha_status({"appliance_id":"all"})` | Distinguir standalone y HA. |
| A12 | `get_firmware_compliance({})` | Versiones y particiones coherentes con inventario. |
| A13 | `get_ztp_status({})` | Estado descubierto/aprobado; no iniciar adopción. |

## B — API y contratos

| Caso | Invocación o procedimiento | Criterio |
|---|---|---|
| B1 | `list_api_operations({"search":"alarm","method":"GET"})` | Operaciones y paginación de acuerdo con el perfil activo. |
| B2 | `call_read_api({"operation_id":"orchestrator.inventory.summary"})` | Inventario consistente con T1 y sin credenciales. |
| B3 | Elegir una lectura documentada con parámetros desde `list_api_operations` | Comparar petición y respuesta con el endpoint vivo; registrar permisos y versión. |
| B4 | Consultar una serie temporal con ventana explícita | Verificar unidades del endpoint y límites temporales; no asumir segundos para todos los endpoints. |
| B5 | Omitir un parámetro requerido de una lectura seleccionada | Error accionable y sin escritura; comparar schema y comportamiento. |
| B6 | Paginar/proyectar una operación que lo soporte | Páginas coherentes; registrar truncamiento y offsets solo si el contrato los ofrece. |
| B7 | Revisar recursivamente respuestas y logs saneados | Ningún secreto en claro; no exigir un marcador si no existe dato sensible. |
| B8 | `call_read_api({"operation_id":"no.existe.op"})` | Error claro y sin stack trace. |
| B9 | `get_orchestrator_infrastructure({})` | Resultado interpretable, sin excepción de lista/dict; contrastar campos disponibles. |
| B10 | `get_appliance_infrastructure({"appliance_id":"<nePk>"})` | Reportar errores internos por campo; no marcar PASS global cuando falte una sección obligatoria. |
| B11 | `get_realtime_stats({"appliance_id":"<nePk>","target_type":"tunnel","name":"<túnel real>","count":5})` | Muestras y objetivo coherentes. Documentar error accionable si el backend exige nombre. |

## C — CLI y SSH

| Caso | Procedimiento | Criterio |
|---|---|---|
| C1 | `list_cli_commands({})` | Catálogo disponible; registrar conteo vigente. |
| C2 | `run_show_api({"command":"show version","appliance_id":"<nePk>"})` | Salida del equipo por Orchestrator. |
| C3 | Si SSH está habilitado y autorizado, `get_ssh_network_path({"appliance_id":"<nePk>"})` y `run_show_command({"command":"show version","host":"<host autorizado>"})` | Registrar ruta propuesta y resultado real por separado; una ruta calculada no prueba conectividad ni autenticación. |
| C4 | `run_cli_command({"command":"comando_inventado_xyz"})` | Rechazo sin ejecución remota. |
| C5 | Dry-run de comando de configuración permitido, sin confirmación | Plan o bloqueo según candado, sin cambio. |

Si SSH no está configurado, C3 es SKIPPED_NOT_CONFIGURED. Un cierre de conexión no demuestra por sí solo causa ni autoriza crear reglas de red.

## D — Seguridad y controles de escritura

| Caso | Procedimiento | Criterio |
|---|---|---|
| D1 | `apply_change` con operación y cuerpo de prueba autorizados, sin confirmación | Dry-run o bloqueo según configuración; no escritura upstream. |
| D2 | Verificar EdgeConnect y SSE con sus respectivos candados deshabilitados | Cada familia bloquea escritura; registrar estado efectivo y no modificarlo para la prueba. |
| D3 | Revisar propuestas `propose_remediation` con datos existentes | Propuesta dry-run; sin aplicación automática. |
| D4 | Con HTTP configurado, consultar `/health` y `/mcp` sin credenciales | Health disponible si está habilitado; acceso MCP protegido según despliegue. |
| D5 | Revisar redacción recursiva y auditoría | No registrar ni compartir secretos; verificar resultado y dry-run. |

Las pruebas de cambios reales, rollback de configuración y ampliación de permisos requieren plan, ventana, alcance y autorización específica; quedan fuera de esta batería.

## E — Robustez, dashboard y Axis

| Caso | Procedimiento | Criterio |
|---|---|---|
| E1 | Revisar JSON y errores en todos los casos | Sin JSON cortado; error parcial o truncado explícito no es PASS de cobertura completa. |
| E2 | `dashboard_snapshot({})`, `dashboard_render({})` | Sin error de helpers; datos atribuibles a fuentes disponibles, HTML válido; registrar truncamiento. |
| E3 | Abrir panel, iniciar sesión y revisar Servicios | Carga y muestra estado con evidencia; diferenciar backend caído de error de panel. |
| E4 | `axis_health({})`, `axis_list_connectors({})`, `axis_list_users({})` | Si Axis está configurado, validar estado y paginación; 403 es limitación de permisos, no PASS. |
| E5 | `get_sase_copilot_status({})`, `ask_sdwan_ai({"question":"Status summary"})` | Registrar permiso/habilitación y respuesta; respuesta vacía es fallo o investigación, no PASS. |
| E6 | `get_site_to_site_tunnels({"appliance_id":"<nePk>"})` frente a `get_tunnel_state` | Comparar tipos y alcance de túneles antes de concluir que falta información. |

## Plantilla de resultados y cierre

```text
Fecha UTC / responsable / entorno:
Build esperada: 9.1.0 SHA=<...>; build servida=<...>; T0=<estado>
Orchestrator versión=<...> perfil=<...>; SSH=<...>; candados=<...>
Caso: <T/A/B/C/D/E + número>
Invocación y alcance: <...>
Esperado / observado: <...>
Estado: PASS | FAIL | BLOCKED | SKIPPED_NO_ENTITY | SKIPPED_NOT_CONFIGURED
Evidencia saneada, hora, ventana y origen de contraste: <...>
Issue o seguimiento / impacto / responsable: <...>
Resumen: ejecutadas=<...>, PASS=<...>, FAIL=<...>, BLOCKED=<...>, omitidas=<...>
Alcances no certificados / decisión y aprobador: <...>
```

La aceptación requiere T0 y todos los casos obligatorios definidos para el despliegue en PASS, ausencia de secretos expuestos y ningún FAIL/BLOCKED abierto en ese alcance. Las omisiones deben justificarse y no certifican la función omitida. CI y `/health` no sustituyen las pruebas vivas; esta guía no certifica cambios de red.
