# EdgeConnect MCP — Debt-map residual (post Fase 2)

Estado: vigente tras la Fase 2 (resolver dinámico con encadenamiento).
Alcance: operaciones GET read-only del catálogo API v9.6 (1,954 ops totales; 645 GET auditadas en Fase 1).

## Estados del clasificador

| Estado | Significado |
| --- | --- |
| `OK_DATA` | Respuesta con datos |
| `OK_EMPTY` | Respuesta válida sin datos |
| `SKIPPED_NO_ENTITY` | La entidad requerida no existe en el appliance (la operación *list* de origen responde vacía) — no es un error del API |
| `PARAM` | Falta parámetro; registrar en este debt-map |
| `ERR400/403/404/ERR_UPSTREAM/ERR_PARSE/EXC` | Igual que Fase 1 |

## Deuda por parámetros no saneables (requieren contexto de acciones previas)

Estas operaciones exigen identificadores que solo existen como **resultado de una acción POST previa**
(jobId/GUID/PID). No se sanean automáticamente por diseño: exigirlos al caller y documentarlo.

| Operación | Parámetro | Origen del valor |
| --- | --- | --- |
| `get_status_of_a_particular_action_using_guid_key_2` | `guid` | POST de acción async previa (p. ej. upgrade, backup) |
| `getpingtracebypid` | `pid` | POST de ping/trace previo |

## Deuda por ausencia real de configuración (ERR_UPSTREAM)

Limitaciones del appliance, no del MCP: reportarlas, no sanearlas.

| Familia | Motivo |
| --- | --- |
| VRFs / segmentos | Sin VRFs configurados en el appliance auditado |
| NAT maps | Sin NAT maps configurados → las ops `get_nat_map_by_name` quedan como `SKIPPED_NO_ENTITY` |
| Interfaces (algunas) | `/interfaces` OK_EMPTY; usar `orchestrator.getinterfacemeta63` para nombres válidos |
| POE | Solo aplica a appliances físicos con puertos POE |

## Parámetros saneables cubiertos en Fase 2 (ya no generan PARAM)

| Parámetro | Mecanismo |
| --- | --- |
| Path params de entidades (`:id`, `:mapName`, `:zoneId`, `:aclName`, `:interfaceName`, `:certName`) | Resolver dinámico con encadenamiento (list → inyectar ID) + Entity Cache TTL 300s |
| `appliance_id='all'` | Fan-out sobre los nePk del inventario (`groupByNE` cuando el spec lo soporta) |
| Alias de prefijo de operation_id (p. ej. `orchestrator.tunnelsget764619` → `appliance.tunnelsget764619`) | Resolvedor de alias con eco `requested_operation_id` en la respuesta |

## Notas de seguridad

- El inventario reparado expone campos `password`/`userName` en el payload de `GET /appliance`;
  el helper los excluye por construcción (lista blanca de campos) y `redact_secrets`
  redacta ambos en cualquier salida JSON hacia el LLM.
- El resolver nunca invoca operaciones `risk=write` (≈1,239 ops quedan fuera de alcance).
