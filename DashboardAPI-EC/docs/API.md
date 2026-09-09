# Referencia de la API REST

> Base URL: `/api/v1` · Documentación interactiva: [`/api/v1/docs`](http://localhost:8080/api/v1/docs) · OpenAPI spec: [`/api/v1/openapi.json`](http://localhost:8080/api/v1/openapi.json)

Todos los endpoints devuelven y aceptan `application/json`. Los `id` son UUID v4. Las fechas siguen ISO 8601 con offset UTC.

## Índice de endpoints

| Grupo | Método | Path | Descripción |
|-------|--------|------|-------------|
| Health | `GET` | `/health` | Estado del servicio |
| System | `GET` | `/system/overview` | Resumen de inventario y servicios |
| Orchestrators | `GET` | `/orchestrators` | Listar orquestadores |
| Orchestrators | `POST` | `/orchestrators` | Crear orquestador |
| Orchestrators | `POST` | `/orchestrators/{id}/validate` | Validar conectividad real |
| Orchestrators | `POST` | `/orchestrators/{id}/discover-appliances` | Descubrir appliances reales |
| Appliances | `GET` | `/appliances` | Listar appliances |
| Appliances | `POST` | `/appliances` | Crear appliance |
| Appliances | `GET` | `/appliances/polling-plan` | Plan de polling sugerido |
| Appliances | `POST` | `/appliances/{id}/collect` | Recolectar métricas de un appliance |
| Compatibility | `GET` | `/compatibility/profiles` | Listar perfiles de compatibilidad |
| Compatibility | `POST` | `/compatibility/resolve` | Resolver una operación a method+path |
| Compatibility | `POST` | `/compatibility/swagger` | Generar borrador de perfil desde OpenAPI |
| Samples | `GET` | `/samples` | Muestras API recientes |

---

## Health

### `GET /health`
Comprueba que el proceso backend responde.

```json
{ "status": "ok", "service": "dashboardapi-ec" }
```

---

## System

### `GET /system/overview`
Devuelve conteos de inventario y estado de servicios.

**Respuesta — `SystemOverview`**
```json
{
  "orchestrators": 2,
  "appliances": 14,
  "selected_appliances": 3,
  "compatibility_profiles": 4,
  "services": {
    "api": "ready",
    "database": "ready",
    "redis": "configured",
    "worker": "configured",
    "api_samples": "47"
  }
}
```

---

## Orchestrators

### `GET /orchestrators`
Lista orquestadores ordenados por `name`.

**Respuesta — `OrchestratorRead[]`**
```json
[
  {
    "id": "4a2b...uuid",
    "name": "Prod DC1",
    "base_url": "https://orchestrator.example.com",
    "api_version": "9.4",
    "status": "validated",
    "polling_enabled": true,
    "polling_active_seconds": 120,
    "polling_idle_seconds": 600,
    "credential_label": "svc-dashboard",
    "auth_type": "basic",
    "username": "svc-dashboard",
    "api_key_header": null,
    "verify_tls": true,
    "timeout_seconds": 20,
    "has_secret": true
  }
]
```

> Los secretos nunca se devuelven. `has_secret` indica únicamente si hay un password o token cifrado almacenado.

### `POST /orchestrators`
Crea un orquestador. Las credenciales se **cifran con Fernet** antes de persistir.

**Cuerpo — `OrchestratorCreate`**
```json
{
  "name": "Prod DC1",
  "base_url": "https://orchestrator.example.com",
  "credential_label": "svc-dashboard",
  "auth_type": "basic",
  "username": "svc-dashboard",
  "password": "super-secret",
  "api_token": null,
  "api_key_header": null,
  "verify_tls": true,
  "timeout_seconds": 20
}
```

| Campo | Tipo | Default | Notas |
|-------|------|---------|-------|
| `name` | string | — | 2-120 chars |
| `base_url` | HttpUrl | — | Se normaliza sin trailing slash |
| `credential_label` | string? | `null` | Etiqueta legible del secreto |
| `auth_type` | string | `"none"` | `none`, `basic`, `bearer`, `api_key` |
| `username` | string? | `null` | Para `basic` |
| `password` | string? | `null` | Se cifra y descarta del output |
| `api_token` | string? | `null` | Para `bearer`/`api_key`; se cifra |
| `api_key_header` | string? | `null` | Header custom para `api_key` |
| `verify_tls` | bool | `true` | Verificación TLS al orquestador |
| `timeout_seconds` | int | `20` | Timeout HTTP por llamada |

**Respuesta** — `201 Created` · `OrchestratorRead`

### `POST /orchestrators/{id}/validate`
Ejecuta una llamada real a `orchestrator.version`, detecta la versión de API y la guarda en el orquestador. Persiste un `ApiSample` (éxito o error) y un `AuditEvent`.

**Respuesta — `OrchestratorValidationResult`**
```json
{
  "orchestrator_id": "4a2b...uuid",
  "status": "validated",
  "detected_version": "9.4",
  "compatibility_profile": "9.4",
  "message": "Real EdgeConnect API response received and stored.",
  "status_code": 200,
  "duration_ms": 142
}
```
- `status` puede ser `validated` o `connection_error`.
- `status_code`/`duration_ms` son `null` si la conexión falla antes de recibir respuesta HTTP.

### `POST /orchestrators/{id}/discover-appliances`
Llama a `orchestrator.inventory.summary`, hace upsert de appliances desde el payload real y los devuelve. En fallo devuelve `502` con el mensaje del `EdgeConnectClientError`.

**Respuesta** — `201` implícito · `ApplianceRead[]`

---

## Appliances

### `GET /appliances`
Lista appliances ordenados por `hostname`.

**Respuesta — `ApplianceRead[]`**
```json
[
  {
    "id": "...",
    "orchestrator_id": "...",
    "hostname": "edge-01",
    "serial_number": "EC12345",
    "site": "DC1",
    "model": "EC-VME",
    "software_version": "9.4.0",
    "status": "sampled",
    "selected_for_monitoring": false,
    "polling_active_seconds": 5,
    "polling_idle_seconds": 300
  }
]
```

### `POST /appliances`
Crea un appliance manualmente ( además del discovery automático).

**Cuerpo — `ApplianceCreate`**
```json
{
  "orchestrator_id": "...",
  "hostname": "edge-01",
  "serial_number": "EC12345",
  "site": "DC1",
  "model": "EC-VME",
  "software_version": "9.4.0",
  "selected_for_monitoring": false
}
```

**Respuesta** — `201 Created` · `ApplianceRead`

### `GET /appliances/polling-plan`
Devuelve el plan de polling sugerido según el estado del dashboard.

```json
{
  "dashboard_active": { "orchestrator_seconds": 120, "appliance_seconds": 5 },
  "dashboard_idle": { "orchestrator_seconds": 600, "appliance_seconds": 300 }
}
```

### `POST /appliances/{id}/collect`
Recolecta métricas reales de un appliance vía `appliance.performance`, persiste el `ApiSample` y marca `status="sampled"`. En fallo devuelve `502`.

**Respuesta** — `200 OK` · el payload JSON bruto devuelto por EdgeConnect.

---

## Compatibility

### `GET /compatibility/profiles`
Lista los perfiles de compatibilidad disponibles.

**Respuesta — `CompatibilityProfileRead[]`**
```json
[
  {
    "version": "9.4",
    "status": "supported",
    "source": "builtin",
    "operations": [
      "appliance.interfaces",
      "appliance.performance",
      "appliance.routing",
      "appliance.tunnels",
      "orchestrator.inventory.summary",
      "orchestrator.topology",
      "orchestrator.version"
    ]
  }
]
```

### `POST /compatibility/resolve`
Resuelve un `(version, operation_id, path_params)` en método HTTP + path final. Útil para inspeccionar qué endpoint se llamaría sin ejecutarlo.

**Cuerpo — `OperationResolveRequest`**
```json
{ "version": "9.5", "operation_id": "appliance.performance", "path_params": { "appliance_id": "edge-01" } }
```

**Respuesta — `OperationResolveResponse`**
```json
{
  "version": "9.5",
  "operation_id": "appliance.performance",
  "method": "GET",
  "path": "/gms/rest/appliances/edge-01/performance",
  "polling_hint_seconds": 5,
  "notes": ["CPU, memory, latency, jitter and loss."]
}
```
- `404` si la versión no tiene perfil o la operación no existe.

### `POST /compatibility/swagger`
Sube un documento OpenAPI (JSON) y genera un borrador de perfil. La persistencia y el diff están programados para fases posteriores.

- Query param: `?version=9.7`
- Cuerpo: archivo `multipart/form-data` campo `file`.

**Respuesta — `SwaggerLoadResult`**
```json
{
  "version": "9.7",
  "status": "generated",
  "operation_count": 12,
  "message": "Profile draft generated. Persistence and diff approval are scheduled for phase 2."
}
```

---

## Samples

### `GET /samples`
Devuelve las muestras API más recientes (orden descendente por `created_at`).

- Query param: `?limit=50` (máx `200`).

**Respuesta — `ApiSampleRead[]`**
```json
[
  {
    "id": "...",
    "orchestrator_id": "...",
    "appliance_id": "...",
    "api_version": "9.4",
    "operation_id": "orchestrator.version",
    "method": "GET",
    "path": "/gms/rest/version",
    "status_code": 200,
    "duration_ms": 142,
    "ok": true,
    "payload": { "version": "9.4.0" },
    "error": null,
    "created_at": "2024-09-09T14:26:00Z"
  }
]
```

Un sample con error se ve así:
```json
{
  "ok": false,
  "status_code": 503,
  "path": "unresolved",
  "error": "EdgeConnect API returned HTTP 503",
  "payload": {}
}
```

---

## Códigos de estado

| Código | Significado |
|--------|-------------|
| `200` | OK |
| `201` | Creado |
| `404` | Recurso u operación no encontrada |
| `400` | Documento Swagger inválido (no JSON) |
| `422` | Validación Pydantic fallida (cuerpo malformado) |
| `502` | Error de EdgeConnect (conexión o HTTP de error) |

## Modelos Pydantic
Los esquemas de entrada/salida viven en `backend/app/schemas/`. La especificación OpenAPI completa se genera automáticamente y se sirve en `/api/v1/openapi.json`.
