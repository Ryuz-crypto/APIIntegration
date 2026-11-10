# Batería de aceptación — ec-mcp 9.1.0

Esta batería comprueba la build de `main` desplegada. La ampliación por dominios y la plantilla detallada están en [QA-FULL.md](QA-FULL.md). Las llamadas siguientes se ejecutan desde un cliente MCP; son ejemplos de herramientas y argumentos, no comandos de shell.

## Reglas y preparación

- Registra fecha UTC, entorno, versión esperada `9.1.0`, **SHA completo esperado** de la publicación aprobada, transporte, versión del Orchestrator y alcance autorizado.
- Ejecuta T0 primero. Si no coincide el SHA o la identidad no puede determinarse, marca T0 **BLOCKED** y no atribuyas los demás resultados a esa build.
- Compara inventario, alarmas y métricas con fuentes vivas y la misma ventana temporal. No supongas cantidad fija de appliances, túneles, alarmas ni perfiles.
- Estados: **PASS**, **FAIL**, **BLOCKED** (prerrequisito fallido), **SKIPPED_NO_ENTITY** (entidad ausente comprobada) y **SKIPPED_NOT_CONFIGURED** (integración no configurada). Un error no es ausencia de entidad.
- Captura argumentos, hora, resultado y evidencia suficiente, saneada. Nunca compartas tokens, contraseñas, cookies, claves, datos personales ni respuestas crudas sin revisar. Ante una fuga, detén la prueba y sigue [SECURITY.md](../SECURITY.md).
- QA de solo lectura: nunca uses `confirm=true`, `axis_commit`, operaciones de configuración ni forwarding sin autorización específica. Los dry-runs no demuestran la seguridad de escrituras reales.
- `/health` confirma el transporte, no la conexión al Orchestrator. Si una respuesta indica truncamiento, consérvala como resultado parcial y acota el objetivo o los campos antes de declarar PASS.

## T0 — Identidad de la build

```text
orchestrator_info({})
```

PASS: `build.package_version` es `9.1.0` y `build.git_commit` coincide con el SHA completo aprobado. Registra `detected_version`, `active_profile`, perfiles disponibles y los estados de escritura/SSH. Comprueba que el perfil corresponde a la versión y al catálogo servido; no presupongas que Orchestrator 10 usa el perfil 9.6.

En el servidor, para contraste, desde `APIIntegration/ec-mcp`:

```bash
git rev-parse HEAD
./.venv/bin/python -c "import ec_mcp; print(ec_mcp.__version__)"
sudo systemctl is-active ec-mcp
```

El checkout y la versión instalada no prueban por sí solos qué proceso está servido; prevalece la identidad reportada por T0.

## T1 — Inventario

```text
list_appliances({})
```

PASS: JSON interpretable, identidades sin duplicados y conteo acorde con el inventario vivo autorizado; credenciales redactadas. Guarda los identificadores saneados que usarás como `<nePk>`.

## T2 — Alarmas

```text
get_active_alarms({"appliance_id":"all"})
get_active_alarms({"appliance_id":"<nePk>"})
```

PASS: la selección individual corresponde al appliance y los conteos/desgloses son coherentes con el origen vivo en una ventana comparable. Repite las llamadas individuales necesarias para contrastar el agregado; anota cambios simultáneos.

## T3 — WAN y MOS

```text
get_wan_health({"appliance_id":"all"})
get_wan_health({"appliance_id":"<nePk>"})
get_mos({"appliance_id":"<nePk>","granularity":"day"})
```

PASS: JSON válido y datos atribuibles al equipo/ventana. Si hay truncamiento, indicar `truncated`, limitar alcance y repetir; no inferir datos ausentes. Registrar valor MOS, unidad y escala de origen; valores de distinta escala requieren contraste antes de compararse.

## T4 — Catálogo y lectura de API

```text
list_api_operations({"search":"alarm","method":"GET"})
call_read_api({"operation_id":"orchestrator.inventory.summary"})
```

PASS: el catálogo y la respuesta concuerdan con el perfil activo; inventario coherente con T1 y secretos protegidos. Si una operación no existe o no tiene permiso, registrar operación, código y contexto saneado; no asumir un fallback concreto sin evidencia.

## T5 — CLI de solo lectura por Orchestrator

```text
list_cli_commands({})
run_show_api({"command":"show version","appliance_id":"<nePk>"})
run_show_api({"command":"show arp","appliance_id":"<nePk>"})
```

PASS: el comando soportado devuelve salida del equipo seleccionado y `transport: orchestrator`. Una tabla ARP vacía puede ser válida si se contrasta. SSH directo es una prueba independiente: ver sección C de QA-FULL.

## T6 — Redacción y controles

Inspecciona recursivamente las respuestas T0–T5 y auditoría, sin copiar secretos. PASS: no aparecen credenciales en claro; la respuesta truncada conserva JSON válido y señala el truncamiento. Registra los estados efectivos de los candados sin activarlos.

## Reporte mínimo

```text
Fecha UTC / entorno / responsable:
Build esperada y servida: versión=<...> SHA=<...> — T0=<estado>
Orchestrator: versión=<...> perfil=<...>; transporte=<...>
T1–T6: <estado por prueba> — objetivo, hora, resultado saneado y evidencia
Truncamientos / permisos / entidades ausentes: <...>
Hallazgos: <issue GitHub o pendiente>, impacto, reproducción saneada
Cobertura: <ejecutadas>/<planificadas>; bloqueadas/omitidas con motivo
Decisión: <apto para siguiente fase / no apto / pendiente>
```

T0 y las pruebas obligatorias deben pasar para aceptar esta batería. Las omisiones documentadas no equivalen a funciones certificadas ni autorizan escrituras; un FAIL o BLOCKED obligatorio impide declarar el alcance completo aprobado.
