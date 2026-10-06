# Batería de QA y protocolo de diagnóstico — MCP `edgeconnect_mcp_6244`

> Esta batería es histórica y contiene referencias de laboratorio de versiones anteriores. Para la revisión vigente de IDS/IPS, DDoS, filtrado web, NGFW y remediaciones usar [QA-SECURITY.md](QA-SECURITY.md); sus casos reales pendientes no se presentan como ejecutados.

**Target**: rev. 8 (commit `35871af`, rama `vibe/edgeconnect-mcp-repairs-1fce9f`)
**Orquestador**: HPE Aruba EdgeConnect 9.7.2.40591 · perfil API 9.6
**Regla de oro**: los tests de datos se comparan contra el **valor vivo del endpoint directo**, nunca contra snapshots históricos (el "33" de Fase 1 es histórico; hoy el vivo manda).

---

## 0. Cómo ejecutar las pruebas

### Opción A — desde tu cliente MCP (Le Chat, Claude, etc.)

Invoca cada herramienta con los argumentos exactos de la tabla y **copia la salida completa sin truncar**.

### Opción B — por HTTP con curl (salida cruda, sin intermediarios)

Con el token de tu `.env` (`EC_MCP_AUTH_TOKEN`), contra el servidor del MCP:

```bash
EC_URL="http://127.0.0.1:8000/mcp"
EC_TOKEN="pega_EC_MCP_AUTH_TOKEN"

mcp_call() {
  curl -s -X POST "$EC_URL" \
    -H "Authorization: Bearer $EC_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d "$1"
}
```

Ejemplo (T1):

```bash
mcp_call '{"jsonrpc":"2.0","id":1,"method":"tools/call",
  "params":{"name":"list_appliances","arguments":{}}}'
```

> Si el servidor responde en formato SSE (`event: message` + `data:`), incluye el `data:` de la respuesta. Si no parseas el envelope JSON-RPC, pega la salida tal cual — el `result.content[0].text` es lo que analizo.

### Regla de captura

Para cada prueba pega **SIEMPRE**:

1. La invocación exacta (tool + argumentos).
2. La salida **completa** (no excerpt). Si tu entorno trunca, indica el `length` del payload y pega el fragmento inicial + final.
3. El `request_echo` completo si aparece en la salida.

---

## 1. Batería de aceptación (T0–T6)

### T0 — Verificación de build (EJECUTAR PRIMERO, SIEMPRE)

```json
orchestrator_info({})
```

**Busca el campo `build`** en la respuesta:

```json
"build": {"package_version": "2.0.0b1", "git_commit": "<deployed-commit>"}
```

**REGLA**: si `git_commit` no es el commit esperado de la revisión bajo prueba, **NINGÚN resultado de T1–T6 es válido como evidencia de esa revisión** — el despliegue está sirviendo una build vieja. Repara el despliegue antes de reportar fallos de código. Si `git_commit` es `unknown`, el paquete no fue instalado desde un checkout git (`pip install -e .` fuera del repo o despliegue por wheel) — también es un hallazgo de despliegue a reportar.

Commit esperado por revisión: rev. 7 = `070ebae` · rev. 8 = `35871af` · rev. 9 = `828eca7` · rev. 10 = el que se anuncie con esta build.

### T1 — Inventario

```json
list_appliances({})
```

**PASS si**: `count == 6` · nePk exactamente `{1.NE, 0.NE, 2.NE, 3.NE, 14.NE, 4.NE}` · sin campos de credencial.

**Si falla, necesito**:
- Salida completa del helper.
- Salida de `call_read_api('orchestrator.inventory.summary')` (mismo `GET /appliance` vía runner) para contrastar helper vs runner.
- Últimas 30 líneas de `tail -30 /tmp/ec-mcp.log` del momento de la llamada.

### T2 — Alarmas 'all' con severidades reales (D1 cerrado + D5)

```json
get_active_alarms({"appliance_id": "all"})
```

**PASS si**:
- 6 filas en `per_appliance`, una por nePk.
- Cada fila: `by_severity` con desglose `{critical, warning, major, minor}` (NO `{"total": N}` plano).
- **Invariante por fila y global**: `critical + warning + major + minor == total`.
- `total_alarms` == suma de las 6 llamadas individuales (abajo).

**Obligatorio — validación viva de equivalencia** (la que atrapó los bugs de rev. 4–5):

```json
get_active_alarms({"appliance_id": "1.NE"})
get_active_alarms({"appliance_id": "0.NE"})
get_active_alarms({"appliance_id": "2.NE"})
get_active_alarms({"appliance_id": "3.NE"})
get_active_alarms({"appliance_id": "14.NE"})
get_active_alarms({"appliance_id": "4.NE"})
```

Pega las 6 salidas. Verifico: `total_alarms('all') == Σ numOfAlarms(individuales)` y que el `by_severity` de cada fila individual coincida con su fila en el fan-out.

**Si falla, necesito además**:
- `orchestrator_metrics` después de ejecutar T2 (confirma que el fan-out hizo las 6 sub-llamadas a `/alarm/count/appliance`).
- Salida de `call_read_api` sobre el endpoint directo si existe en el catálogo: `list_api_operations(search='alarm/count')` y la llamada cruda.

### T3 — wan_health con proyección (D4)

#### T3a — default (sin `fields`)

```json
get_wan_health({"appliance_id": "all"})
```

**PASS si**: payload JSON **parseable completo** (nada de `truncated: true` ni corte en 12,000 chars), 6 filas, y por túnel solo KPIs (campos tipo `MOS`, `MIN_MOS`, `*JITTER*`, `*LATENCY*`, `*LOSS*`) — **sin** counters crudos tipo `SUM_OHEAD_WTX_PKTS` o `MAX_COMP_L2W`.

**Reporta**: `length` del payload y si parsea como JSON válido (sí/no).

#### T3b — con `fields` (el caso roto en rev. 8)

```json
get_wan_health({"appliance_id": "all",
  "fields": "mos,min_mos,MAX_JITTER,MAX_PRE_PCT_LOSS,MIN_LATENCY_MIN"})
```

**PASS si**: 6 filas y cada fila tiene `nePk` + `stats` con los KPIs pedidos — **cero filas vacías `{}`**.

#### T3c — un solo appliance (aisla el fan-out)

```json
get_wan_health({"appliance_id": "1.NE"})
```

**Si T3 falla, necesito**:
- Las tres salidas completas (T3a, T3b, T3c).
- El **shape crudo** del endpoint tal como llega al cliente antes de proyección: `call_read_api` de la op `orchestrator.tunnelStatsGET7*` o la que sirva `GET /stats/aggregate/tunnel` — búscala con `list_api_operations(search='aggregate/tunnel')` y pega su salida con `appliance_id: '1.NE'`, `granularity: 'hour'`. Esto me dice si `data` llega como lista de filas o como dict-keyed por túnel (`{"data": {"bondedTunnel_13": {"1.NE": {...}}}}`), que son los dos shapes que la proyección maneja.

### T4 — get_role_options vía proxy (D3)

```json
call_read_api({"operation_id": "get_role_options"})
```

**PASS si**: responde 200 con opciones de roles y el `request_echo` contiene:

```json
"request_echo": {"resolved_path": "/appliance/rest", "via_appliance_proxy": true, "query_used": {}}
```

**FALLA con error combinado** (ejemplo):

```
HTTP 400 ... 'Invalid nePk' | appliance-scoped fallback via /appliance/rest also failed: <CAUSA>
```

→ Esa `<CAUSA>` es **lo único que necesito** para reparar: distingue "el proxy también lo rechaza" (p.ej. 404 en `/appliance/rest`, auth, path no soportado) de "el fix no está en la build servida".

**Si falla, necesito además** (en este orden, son 3 llamadas):

```json
list_appliances({})
```
(confirma que el proxy tiene nePk válido que resolver — el fallback resuelve el nePk del inventario)

```json
orchestrator_metrics({})
```
(después del intento: debe mostrar llamadas a `/userProfile/options` Y a `/appliance/rest`; si solo aparece la primera, la build servida no es la rev. 8)

```json
call_read_api({"operation_id": "get_platforminfo"})
```
(una op appliance-scoped que ya funciona vía `/appliance/rest` — me confirma que el proxy en sí está sano en tu orquestador)

**Verificación de versión servida** (si sospechas que el despliegue no actualizó):

```
git -C APIIntegration/ec-mcp rev-parse HEAD
pip show ec-mcp | head -3    # dentro del venv
```

Debe ser `35871af` (o posterior).

### T5 — Getters sin granularity

```json
call_read_api({"operation_id": "get_hostname"})
```

**PASS si**: `{"data": {"hostname": "..."}}` sin `PARAM_REQUIRED`. Estable desde rev. 3; cualquier fallo aquí es **regresión** y la reporto con máxima prioridad.

### T6 — Redacción de credenciales

```json
call_read_api({"operation_id": "orchestrator.inventory.summary"})
```

**PASS si**: todas las apariciones de `password`/`userName`/`secret`/`token`/`key` muestran `***REDACTED***` y no existe ninguna credencial en claro.

**Chequeo automatizado opcional** (pega el resultado):

```bash
RESP=$(mcp_call '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"call_read_api","arguments":{"operation_id":"orchestrator.inventory.summary"}}}')
echo "$RESP" | grep -c 'REDACTED'        # > 0
echo "$RESP" | grep -c '"userName": "admin"'   # 0
echo "$RESP" | grep -oE '"password": "[^*]'     # sin output
```

---

## 2. Diagnóstico nivel 2 (solo si algo falla)

### 2.1 — Contraste directo contra el orquestador (sin MCP)

Con la API key (`X-Auth-Token`), fuera del MCP — me dice si el defecto es del conector o del orquestador:

```bash
ORCH="https://lac-wan-sewan-orchge-useast1.silverpeak.cloud"
KEY="pega_EC_ORCHESTRATOR_API_KEY"

# Inventario
curl -s -H "X-Auth-Token: $KEY" "$ORCH/gms/rest/appliance" | python3 -m json.tool | head -60

# Conteo de alarmas por appliance (el endpoint de referencia de T2)
for ne in 1.NE 0.NE 2.NE 3.NE 14.NE 4.NE; do
  echo "== $ne"
  curl -s -H "X-Auth-Token: $KEY" "$ORCH/gms/rest/alarm/count/appliance?nePk=$ne"
done

# El endpoint del proxy de T4, directamente
curl -s -H "X-Auth-Token: $KEY" \
  "$ORCH/gms/rest/appliance/rest?nePk=1.NE&url=/userProfile/options"

# El endpoint de T3, crudo (primeros 3000 chars)
curl -s -H "X-Auth-Token: $KEY" \
  "$ORCH/gms/rest/stats/aggregate/tunnel?nePk=1.NE&granularity=hour&startTime=<epoch_s>&endTime=<epoch_s>" \
  | head -c 3000
```

Pega la salida de cada uno. Con el contraste `curl directo vs salida del MCP` identifico en qué capa se pierde el dato.

### 2.2 — Logs del servidor

```bash
tail -100 /tmp/ec-mcp.log
tail -5 <EC_AUDIT_LOG>   # path en tu .env, JSONL: una línea por operación con ok/error
```

### 2.3 — Captura del HTTP real (nivel máximo, solo T4 si persiste)

Si T4 sigue fallando con el error combinado, esto cierra el caso definitivamente:

```bash
# En el servidor del MCP, durante 60s mientras ejecutas el test T4:
sudo tcpdump -i any -A -s 0 'tcp port 443 and host <IP_DEL_ORCHESTRATOR>' -w /tmp/t4.pcap
# o más simple, log de httpx: en .env agrega EC_LOG_LEVEL=DEBUG (si está soportado) y pega
tail -50 /tmp/ec-mcp.log tras el intento
```

Lo que necesito ver: la URL **exacta** de las dos requests (la directa a `/gms/rest/userProfile/options` y la del retry a `/gms/rest/appliance/rest?nePk=...&url=...`) con sus query strings y los status/bodies de respuesta.

---

## 3. Formato de reporte (plantilla)

```
BUILD: <git rev-parse HEAD> | servidor: <donde corre>
T1: PASS/FAIL — <salida completa>
T2: PASS/FAIL — fan-out: <salida> | individuales: <6 salidas> | Σ=<> vs total_alarms=<>
T3a: PASS/FAIL — length=<N>, parseable JSON: sí/no — <salida>
T3b: PASS/FAIL — filas vacías: cuántas — <salida>
T3c: PASS/FAIL — <salida>
T4: PASS/FAIL — request_echo: <...> | error completo: <...> | metrics: <...>
T5: PASS/FAIL — <salida>
T6: PASS/FAIL — REDACTED=<n>, admin=<n>
EXTRA (solo con fallos): contraste curl directo + logs
```

## 4. Prioridad de reparación con tu reporte

| Con esto... | Reparo esto |
|---|---|
| T2 filas con `total: 0` o `by_severity: {"total": N}` | D1/D5 — extractor del fan-out |
| T3b filas vacías + shape crudo de 2.1 (`/stats/aggregate/tunnel`) | D4 — nivel de anidamiento de la proyección |
| T4 error combinado con `<CAUSA>` | D3 — ajuste del rerouting (path, params o auth del proxy) |
| T4 sin `via_appliance_proxy` y sin "also failed" | La build servida no es rev. 8 — problema de despliegue, no de código |
| T1/T5/T6 fallan | Regresión — máxima prioridad, revertir al último estado estable |
