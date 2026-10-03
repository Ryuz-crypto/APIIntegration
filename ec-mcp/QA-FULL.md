# Protocolo completo de Q&A — EdgeConnect MCP (`edgeconnect_mcp_6244`)

**Audiencia**: QA con acceso al conector MCP (sin acceso al repositorio).
**Build esperada**: ec-mcp `2.0.0b1` — `orchestrator_info().build.package_version == 2.0.0b1` y `build.git_commit` presente y distinto de `unknown` (ver T0).
**Orquestador de referencia**: HPE Aruba EdgeConnect 9.7.2.40591 · perfil 9.6 · 6 appliances (`1.NE, 0.NE, 2.NE, 3.NE, 14.NE, 4.NE`).

**Reglas transversales**:
1. Ejecutar **T0 primero y siempre**. Sin T0 verificado, ningún otro resultado cuenta como evidencia de la revisión bajo prueba.
2. Los tests de datos vivos (alarmas, túneles, inventario) se comparan contra el **endpoint directo**, no contra snapshots históricos.
3. Para cada prueba: registrar invocación exacta + salida completa (si tu entorno trunca: reportar `length` + fragmento inicial y final).
4. Convención de estados: `PASS` · `FAIL` · `SKIPPED_NO_ENTITY` (entidad inexistente en el lab, no es defecto) · `BLOCKED` (prerequisito fallido).
5. Cero operaciones de escritura sin dry-run explícito. Todo lo marcado 🔒 es de solo verificación de controles de seguridad — **nunca** ejecutar `confirm=true` salvo orden expresa del dueño del lab.

---

## SECCIÓN 0 — Verificación de build y contrato base

### T0.1 — Build servida
```json
orchestrator_info({})
```
**PASS**: `build.package_version == 2.0.0b1`; `build.git_commit` está presente, no es `unknown` y corresponde al commit desplegado.
**FAIL conocido**: `git_commit` ausente o `unknown` → el despliegue no es verificable; reportarlo como hallazgo de despliegue.
**Si falla**: detener. Reparar despliegue antes de continuar.

### T0.2 — Versión y perfil del orquestador
Misma salida de T0.1.
**PASS**: `detected_version` empieza con `9.7.` · `active_profile == "9.6"` · `available_profiles` incluye `9.3`–`9.6` · `appliance_count == 6` · los 6 nePk en `appliances`.

### T1 — Inventario
```json
list_appliances({})
```
**PASS**: `count == 6` · nePk exactos `{1.NE, 0.NE, 2.NE, 3.NE, 14.NE, 4.NE}` · cada fila con `name, ip, model, software_version, state` · **ningún** campo `password`/`userName`/`secret`/`token`/`key` en claro.

### T1b — Resolución de identidad (por nombre e IP)
```json
get_active_alarms({"appliance_id": "EC1"})       # por nombre (usa el de tu inventario real)
get_active_alarms({"appliance_id": "10.0.0.1"})  # por IP
```
**PASS**: ambas resuelven al mismo nePk que `list_appliances` reporta para ese appliance (mismo `total` que el modo por nePk).

### T2 — Catálogo de operaciones
```json
list_api_operations({"search": "alarm", "method": "GET"})
list_api_operations({"prefix": "orchestrator.", "page": 1, "page_size": 50})
list_api_operations({"search": "neStatus"})
```
**PASS**: primera devuelve las ops de alarmas con id+path; segunda pagina con `has_more_page`; tercera: doc de coverage (`neStatus` no está indexado — si devuelve >0, reportar, cambió el catálogo).
**Registrar**: `total_operations` de la llamada sin filtros.

### T3 — Métricas
```json
orchestrator_metrics({})
```
**PASS**: JSON con `count >= 1` y filas `operation, calls, avg_seconds, max_seconds, total_kb, cache_hits`. Verificar tras T2 que `/alarm/count/appliance` tiene `calls >= 6`.

---

## SECCIÓN A — Helpers KPI (fan-out `'all'`)

> Prerequisito: T0, T1 PASS.

### A1 — Alarmas 'all' con severidades (D1+D5)
```json
get_active_alarms({"appliance_id": "all"})
```
**PASS**:
- 6 filas en `per_appliance`, una por nePk.
- Cada fila: `by_severity` contiene **las 4 severidades explícitas** (`critical`, `warning`, `major`, `minor`, con 0 incluido).
- **Invariante por fila y global**: `suma(by_severity) == total`.
- `total_alarms == Σ` de las llamadas individuales (A2).

### A2 — Alarmas individuales (validación viva)
```json
get_active_alarms({"appliance_id": "1.NE"})
get_active_alarms({"appliance_id": "0.NE"})
get_active_alarms({"appliance_id": "2.NE"})
get_active_alarms({"appliance_id": "3.NE"})
get_active_alarms({"appliance_id": "14.NE"})
get_active_alarms({"appliance_id": "4.NE"})
```
**PASS**: cada una expone `numOfCriticalAlarms`…`numOfAlarms` (o el desglose equivalente). Validar: `total_alarms('all') == Σ numOfAlarms(individuales)` y `by_severity` por fila == desglose de su individual.
**Contraste opcional de nivel 2** (curl directo, fuera del MCP): `GET /gms/rest/alarm/count/appliance?nePk=<ne>` para cada uno — debe coincidir numéricamente.

### A3 — WAN health default (D4)
```json
get_wan_health({"appliance_id": "all"})
```
**PASS**: JSON válido completo (nunca cortado en 12,000 chars) · 6 filas con `nePk` + `stats` · `total_count: 6` · `truncated: false` · por túnel solo KPIs (`mos/min_mos/*JITTER*/*LATENCY*/*LOSS*`), **sin** counters crudos (`SUM_OHEAD_WTX_PKTS`, `MAX_COMP_L2W`).
**Registrar**: `length` del payload y si parsea como JSON.

### A4 — WAN health con fields (el caso roto en rev. 8)
```json
get_wan_health({"appliance_id": "all",
  "fields": "mos,min_mos,MAX_JITTER,MAX_PRE_PCT_LOSS,MIN_LATENCY_MIN"})
```
**PASS**: 6 filas, **cero filas vacías**, cada fila con `nePk` + los KPIs solicitados (case-insensitive). Si un campo pedido no existe en un túnel, se omite o va null — la fila NO queda vacía.

### A5 — WAN health un solo appliance
```json
get_wan_health({"appliance_id": "1.NE"})
```
**PASS**: 1 fila con `nePk == "1.NE"` y stats de sus túneles (`bondedTunnel_*`), mismo criterio de KPIs que A3.

### A6 — MOS
```json
get_mos({"appliance_id": "all", "granularity": "day"})
get_mos({"appliance_id": "1.NE", "granularity": "day"})
```
**PASS**: JSON válido con entradas de MOS por túnel; valores escalados ×100 típicos (440 = MOS 4.40). Con `appliance_id` individual, solo sus túneles.

### A7 — Estado de túneles
```json
get_tunnel_state({"appliance_id": "all"})
```
**PASS**: filas por túnel con estado; o clasificación honesta `SKIPPED_NO_ENTITY` si el lab no reporta. Registrar el shape exacto.

### A8 — Brownout
```json
get_brownout_state({"appliance_id": "all"})
```
**PASS**: filas con `tunnel, state, brownout, reason`. En lab sin brownout: estados normales o `SKIPPED_NO_ENTITY`, no error 500 ni JSON cortado.

### A9 — Availability
```json
get_availability({"appliance_id": "all", "granularity": "hour"})
```
**PASS**: JSON válido con availability por appliance/túnel. `start_time/end_time` en epoch **segundos**.

### A10 — Top talkers
```json
get_top_talkers({"appliance_id": "1.NE", "granularity": "hour", "limit": 10})
```
**PASS**: hasta `limit` filas o `SKIPPED_NO_ENTITY` si el lab no genera tráfico.

### A11 — HA status
```json
get_ha_status({"appliance_id": "all"})
```
**PASS**: JSON válido; en appliances sin HA, estado que lo indique o `SKIPPED_NO_ENTITY`.

### A12 — Firmware compliance
```json
get_firmware_compliance({})
```
**PASS**: versiones por appliance (ECOS 9.7.x esperadas según inventario).

### A13 — ZTP
```json
get_ztp_status({})
```
**PASS**: estado ZTP (vacío válido si no hay dispositivos pendientes).

---

## SECCIÓN B — Runner `call_read_api` (operaciones del catálogo)

> Prerequisito: T2 PASS.

### B1 — Getters estáticos sin granularity (T5 histórico)
```json
call_read_api({"operation_id": "get_hostname"})
call_read_api({"operation_id": "get_platforminfo"})
call_read_api({"operation_id": "get_httpport"})
```
**PASS**: dato real (`hostname` = fqdn del orquestador, `platform` = `DOCKER`, `httpport` = `8080`) · `query_used: {}` · **sin** `PARAM_REQUIRED`.

### B2 — get_role_options vía proxy (D3)
```json
call_read_api({"operation_id": "get_role_options"})
```
**PASS**: 200 con opciones de roles y `request_echo` conteniendo:
```json
{"resolved_path": "/appliance/rest", "via_appliance_proxy": true, "query_used": {}}
```
**FAIL tipo 1** (error combinado): `... 'Invalid nePk' | appliance-scoped fallback via /appliance/rest also failed: <CAUSA>` → pegar la `<CAUSA>` completa.
**FAIL tipo 2** (error en formato viejo, sin `also failed` y sin `via_appliance_proxy`): la build no contiene el fix → volver a T0.

### B3 — Ops con path params (recuperadas en rev. 1)
Ejecutar las 12; **PASS** = 200 (OK_DATA o OK_EMPTY válido):
```json
call_read_api({"operation_id": "appliance.getsegmentbgp60446", "extra_path_params_json": "{\"vrfId\":\"0\"}"})
call_read_api({"operation_id": "appliance.getbfdvrfconfig245784", "extra_path_params_json": "{\"vrfId\":\"0\"}"})
call_read_api({"operation_id": "appliance.getneighbor408214", "extra_path_params_json": "{\"IP\":\"172.17.201.117\"}"})
call_read_api({"operation_id": "appliance.getvrfneighbor495708", "extra_path_params_json": "{\"vrfId\":\"0\"}"})
call_read_api({"operation_id": "appliance.getsegmentstate864434", "extra_path_params_json": "{\"vrfId\":\"0\"}"})
call_read_api({"operation_id": "appliance.nslookupget727226", "extra_path_params_json": "{\"FQDN\":\"google.com\"}"})
call_read_api({"operation_id": "appliance.loopbackget642996", "extra_path_params_json": "{\"loopbackName\":\"loopback0\"}"})
call_read_api({"operation_id": "appliance.vtiget145095", "extra_path_params_json": "{\"vtiName\":\"vti1\"}"})
call_read_api({"operation_id": "appliance.xcvrget442860", "extra_path_params_json": "{\"interfaceName\":\"wan1\"}"})
call_read_api({"operation_id": "appliance.userappgroupsbynameget535619", "extra_path_params_json": "{\"groupName\":\"default\"}"})
call_read_api({"operation_id": "appliance.userappsbygetpriority355703", "extra_path_params_json": "{\"priority\":\"1\"}"})
call_read_api({"operation_id": "appliance.systemconfigattribget502145", "extra_path_params_json": "{\"attribute\":\"hostname\"}"})
```

### B4 — Parametrización de series temporales
```json
call_read_api({"operation_id": "orchestrator.mos_aggregate_stats645",
  "appliance_id": "1.NE", "granularity": "day",
  "start_time": "<epoch_s de hace 24h>", "end_time": "<epoch_s ahora>"})
```
**PASS**: MOS real por túnel (malla ~440). `granularity` jamás numérico; alarm endpoints en epoch **s**, stats3/timeseries en epoch **ms** (el error hint del MCP lo avisa).

### B5 — Preflight de params (rechazo local)
```json
call_read_api({"operation_id": "orchestrator.mos_aggregate_stats645", "granularity": "day"})
call_read_api({"operation_id": "appliance.getzone263649", "extra_path_params_json": "{\"zoneId\":\"5\"}", "appliance_id": "1.NE"})
```
**PASS**: la primera → `PARAM_REQUIRED` con `appliance_id (nePk)` (sin llamada upstream); la segunda → 200 OK_EMPTY con `zoneId` 5..18.

### B6 — Paginación y proyección del runner
```json
call_read_api({"operation_id": "orchestrator.inventory.summary", "fields": "nePk,hostName", "limit": 2})
call_read_api({"operation_id": "orchestrator.inventory.summary", "offset": 2, "limit": 2})
```
**PASS**: primera: filas proyectadas a solo `nePk,hostName` con `total_count: 6, returned: 2`; segunda: `next_offset: 4` (página siguiente válida).

### B7 — Redacción de credenciales (T6)
```json
call_read_api({"operation_id": "orchestrator.inventory.summary"})
```
**PASS**: todas las apariciones de `password`/`userName`/`secret`/`token`/`key` → `***REDACTED***`; ninguna credencial en claro.
**Chequeo automatizado** (curl contra el MCP, `RESP` = respuesta):
```bash
echo "$RESP" | grep -c 'REDACTED'                 # > 0
echo "$RESP" | grep -c '"userName": "admin"'      # 0
echo "$RESP" | grep -oE '"password": "[^*]'       # sin output
```

### B8 — Operación inexistente
```json
call_read_api({"operation_id": "no.existe.op"})
```
**PASS**: error accionable con sugerencias (ops parecidas o cómo buscarlas), no stack trace.

---

## SECCIÓN C — Catálogo CLI y SSH

> Prerequisito: SSH habilitado en el despliegue (`orchestrator_info().ssh_enabled == true`); si no, marcar toda la sección `SKIPPED_NO_SSH`.

### C1 — Catálogo CLI
```json
list_cli_commands({})
list_cli_commands({"category": "monitoring"})
```
**PASS**: `total == 1367` (o el valor del catálogo servido) · categorías `monitoring, troubleshooting, alarm, administration, configuration, negation` · filtro por categoría reduce el conteo.

### C2 — show whitelisteado
```json
run_show_command({"command": "show system"})
```
**PASS**: salida del appliance (uptime, versión), no error de whitelist ni timeout SSH.
**Registrar**: qué appliance respondió (el pool elige host).

### C3 — Comando fuera de catálogo 🔒
```json
run_cli_command({"command": "comando_inventado_xyz"})
```
**PASS**: rechazo `Command not in the official ECOS CLI catalog` — sin intento SSH.

### C4 — CLI de configuración en dry-run 🔒
```json
run_cli_command({"command": "<comando de configuration del catálogo>"})
```
**PASS**: respuesta `dry-run` con el comando que se ejecutaría — **sin** cambios en el appliance (verificar con `show` antes/después si es sensible).

---

## SECCIÓN D — Seguridad y controles de escritura 🔒 (solo verificación de controles)

### D1 — apply_change en dry-run
```json
apply_change({"operation_id": "<op POST/PUT del catálogo>", "body_json": "{}"})
```
**PASS**: devuelve el método+path+body que **se ejecutaría**, marcado dry-run — **sin** llamar upstream (validar en `orchestrator_metrics`: sin llamadas nuevas a la op).

### D2 — apply_change sin confirm bloqueado
Igual invocación de D1 pero analizando el output: si `EC_ALLOW_WRITE_TOOLS` está deshabilitado en el servidor, debe rechazar con el error de kill-switch; si está habilitado, el dry-run de D1 aplica. **Nunca** pasar `confirm: true` en QA salvo orden expresa.

### D3 — kill switch reportado
De `orchestrator_info`: `write_tools_enabled` refleja el `.env` del servidor (`EC_ALLOW_WRITE_TOOLS`).

### D4 — Token/autenticación (modo HTTP)
```bash
curl -s -o /dev/null -w "%{http_code}" http://<host>:8000/health        # 200 sin auth
curl -s -o /dev/null -w "%{http_code}" -X POST http://<host>:8000/mcp \
  -H "Content-Type: application/json" -d '{}'                          # 401 sin Bearer
```
**PASS**: `/health` público 200; `/mcp` sin token → 401.

### D5 — Redacción recursiva en payloads profundos
Cualquier respuesta de la sección A/B con payloads anidados: buscar recursivamente (visual o grep) valores de las claves sensibles — no solo nivel 1. Reportar si alguna credencial aparece en un nivel anidado.

---

## SECCIÓN E — Robustez y contrato de transporte

### E1 — JSON siempre válido
Toda respuesta de T0–D5 debe ser JSON parseable o texto de error explícito. **Nunca** una cadena JSON cortada a mitad (el corte en 12,000 chars es defecto si ocurre).

### E2 — Payloads grandes
```json
get_wan_health({"appliance_id": "all", "granularity": "day"})
```
**PASS**: si excede el límite de salida del MCP, debe llegar con `truncated: true` y metadata de paginación (`next_offset`) — no JSON inválido. En la build actual, con la proyección KPI activa, no debería exceder nada.

### E3 — Errores accionables
Cada `Error:` de la sesión debe contener: qué falló, contra qué path, y un hint de qué param verificar. Reportar cualquier error genérico sin contexto.

### E4 — Auditoría
Si tienes acceso al servidor: `tail` del audit log JSONL — cada operación de la sesión con su registro (tool, target, ok/error, dry_run). Verificar que las llamadas de esta sesión aparecen.

---

## Plantilla de reporte

```
BUILD (T0.1): git_commit=<...> package=<...> — PASS/FAIL
ORCH (T0.2): version=<...> profile=<...> appliance_count=<...>
T1: PASS/FAIL — count=<n>
T1b: PASS/FAIL — name→<nePk>, ip→<nePk>
T2: PASS/FAIL — total_operations=<n>
T3: PASS/FAIL — alarm endpoint calls=<n>
A1: PASS/FAIL — total_alarms=<n> vs Σ individuales=<n> · invariante por fila: OK/FAIL
A2: PASS/FAIL — <6 salidas>
A3: PASS/FAIL — length=<n> parseable=sí/no counters_crudos=sí/no
A4: PASS/FAIL — filas vacías=<n>
A5: PASS/FAIL
A6–A13: PASS/FAIL/SKIPPED_NO_ENTITY — uno por helper, con observación breve
B1: PASS/FAIL — hostname/platform/httpport
B2: PASS/FAIL — via_appliance_proxy=<bool> | error completo si FAIL
B3: PASS/FAIL — x/12 recuperadas (listar las que fallen)
B4: PASS/FAIL
B5: PASS/FAIL
B6: PASS/FAIL
B7: PASS/FAIL — REDACTED=<n> admin=<n>
B8: PASS/FAIL
C1–C4: PASS/FAIL/SKIPPED_NO_SSH
D1–D5: PASS/FAIL/SKIPPED
E1–E4: PASS/FAIL
EXTRA (solo con fallos): curl directo de contraste (ver QA-BATTERY.md §2.1) + logs
```

## Criterio de cierre

La revisión se acepta cuando:
- **T0 PASS** (build verificada — obligatorio e innegociable);
- T1, T1b, T2, T3, A1–A5, B1, B2, B5, B6, B7, E1 PASS;
- A6–A13 y B3–B4, C, D: PASS o `SKIPPED_NO_ENTITY`/`SKIPPED_NO_SSH` documentado;
- Cero credenciales en claro en cualquier salida, log o métrica;
- Cero cadenas JSON cortadas;
- `get_role_options` con `via_appliance_proxy: true` explícito en `request_echo`.

## Anexo — Envío de resultados

Prioridad de reparación por evidencia:

| Con esto... | Reparo |
|---|---|
| T0 FAIL | Despliegue — nada de lo demás es evidencia |
| A1 filas con severidad plana `{"total":N}` | Extractor del fan-out |
| A4 filas vacías | Proyección fields / nivel de anidamiento |
| B2 error combinado con `<CAUSA>` | Rerouting del proxy (path/params/auth) |
| B2 error en formato viejo | Build sin el fix → T0 de nuevo |
| B7 credencial en claro | P0 de seguridad — prioridad máxima |
| E1 JSON cortado | Serialización/paginación del transporte |
