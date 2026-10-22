# Rutina operativa de perfiles de versión — MCP `edgeconnect_mcp_6244`

**Perfiles cargados**: 9.3, 9.4, 9.5, 9.6 y 10.0 (desde la rev. con soporte 10.0).
**Fuente del perfil 10.0**: `api-collections/apiDocs.json` (OpenAPI oficial del Orchestrator 10.0, 1227 operaciones) fusionado con las operaciones curadas del perfil 9.6 para mantener los ids de operación estables (p. ej. `orchestrator.searchallbondedtunnels889`, `orchestrator.flows242`, `orchestrator.appliancegetapi70`).

El importador OAS resuelve los parámetros por `$ref` (p. ej. `nePkRequired`), por lo que operaciones como `orchestrator.flows242`, `orchestrator.bfdsessions139` y `orchestrator.appliancegetapi70` conservan su parámetro `nePk`. Los perfiles futuros se importan igual y heredan las operaciones curadas del perfil anterior para mantener los ids estables.

---

## 1. Matching de versión

`CompatibilityEngine.match_version` resuelve la versión detectada (`/gms/rest/gmsserver/briefInfo`) en este orden:

1. Igualdad exacta contra un perfil (`10.0` detectado → perfil `10.0`).
2. Coincidencia `major.minor` (`10.0.0.40204` → perfil `10.0`).
3. **Fallback**: perfil mayor disponible cuya versión sea ≤ la detectada, con `warning` en el log del conector. Ejemplos:
   - `10.0.0.40204` → `10.0` (paso 2)
   - `9.7.2.40591` → `9.6` (fallback: no existe perfil 9.7)
   - `10.1.0.x` o `11.0` → `10.0` (fallback)
   - `9.2.x` → sin perfil (`PROFILE_MISMATCH`)

Regla: una versión detectada **mayor o igual** a un perfil cargado nunca bloquea por mismatch; se usa el perfil mayor disponible y se registra el warning. Una versión **menor** que el perfil más antiguo sí bloquea.

## 2. Rutina post-deploy

1. `orchestrator_info` → comparar `detected_version` vs `available_profiles` y `active_profile`.
   - `active_profile` no nulo → catálogo completo disponible (`call_read_api`, SOC, flujos, proxy REST).
   - `active_profile` con warning de fallback → catálogo disponible pero posible deriva semántica entre la build detectada y el perfil usado; registrar el par (detected, profile).
   - `active_profile: null` → sondear solo las funciones nativas seguras (ver §4) y asumir bloqueadas las dependientes de perfil.
2. Probar SSH **por nombre de appliance o nePk** — el parámetro `host` no resuelve IPs (`Appliance not found in inventory` con IP). Si responde `Authentication failed` → SSH habilitado pero credenciales sin configurar en el conector; no reintentar.
3. Registrar el resultado en el Knowledge del proyecto: fecha, `detected_version`, `active_profile`, sondas OK/bloqueadas.
4. Tras cualquier upgrade del Orchestrator, re-ejecutar la batería completa (QA-BATTERY.md).

## 3. Tras un upgrade del Orchestrator

1. Si el proveedor publica un OpenAPI nuevo (p. ej. `apiDocs.json` de 10.1), importarlo:
   ```bash
   python -m ec_mcp.import_oas api-collections/apiDocs.json --version 10.1 \
       --prefix orchestrator --output ec_mcp/profiles
   ```
   y luego fusionar las operaciones curadas del perfil inmediatamente inferior para conservar ids estables (mismo procedimiento usado para construir `edgeconnect-10.0.json`).
2. Verificar que los ids usados por el código (grep de `orchestrator.` / `appliance.` en `ec_mcp/*.py`) existen en el nuevo perfil.
3. Correr `python3 -m pytest tests/` (los tests de `test_unit.py` validan el matching y las operaciones clave).

## 4. Notas de compatibilidad 9.6 → 10.0 verificadas contra el swagger 10.0

- `GET /flow` (`orchestrator.flows242`) existe en 10.0; re-verificar índices del array de flujos (WAN bytes) en vivo antes de confiar en top talkers.
- `GET /appliance/rest` (`orchestrator.appliancegetapi70`) existe en 10.0 — proxy genérico para `/neighbors`, `/vrrp`, `/networkInterfaces`, `/ha`, `/cluster` vía appliance.
- `POST /stats/realtimeStats` (`appliance.realtimestats88590`, riesgo `write` aunque solo consulta) existe en 10.0.
- `/gms/appliance/preconfiguration*` existe en 10.0 (`orchestrator.getpreconfigurations246`, `orchestrator.getmatchingpreconfiguration250`, `orchestrator.createpreconfiguration247_1`, `orchestrator.getpreconfigurationapplystatus254`) — flujo ZTP completo.
- `GET /gms/wanOverlay/tunnels` **no existe** en el swagger 10.0; la fuente de WAN health se mantiene desde el perfil 9.6 curado (operación heredada).
- `GET /cluster/state` y `GET /bondedTunnels/aliases` no aparecen como paths literales en 10.0; se usan `appliance.tunnelsconfigandstate*` (`/bondedTunnels/state`) y el alias masivo vía `orchestrator.searchallbondedtunnels889` (`/tunnels2/bonded`).
- `GET /dhcpConfig` es global (ignora `nePk`) — confirmado presente en 10.0 (`dhcpConfigGet219`); mantener la salvedad.
- `get_wan_health`: anidación `appliances[].stats.<tunnelId>.<nePk>` y escala MOS inconsistente (`v>10 → v/100`) — manejar en el extractor, no en el perfil.
- `get_tunnel_state` con `fields`: la proyección falla en algunos appliances; fallback con `max_chars` alto + extracción por regex del excerpt.
