# Arquitectura

> Documento de referencia de la arquitectura de `DashboardAPI-EC`, plataforma base NOC/SOC para Aruba EdgeConnect.
> Para decisiones de diseño razonadas, ver los [ADR](./ADR/). Para la guía de instalación, ver el [`README.md`](../README.md).

## Visión general

`DashboardAPI-EC` es una plataforma modular para administrar, validar y recolectar telemetría de orquestadores y appliances Aruba EdgeConnect a lo largo de múltiples versiones de API (9.3 → 9.6).

El principio rector es la **Compatibility Layer First** (ver [ADR-0001](./ADR/ADR-0001-compatibility-layer.md)): ningún servicio o ruta llama directamente a los endpoints de EdgeConnect. Toda operación se identifica por un `operation_id` estable y se resuelve a un método + path concreto a través de un perfil de compatibilidad versionado.

## Diagrama de componentes

```text
                         ┌─────────────────────────────────────────────┐
                         │                  Nginx (:8080)               │
                         │   rutea /api/v1/* al backend y / a la UI    │
                         └───────────────┬───────────────┬─────────────┘
                                         │               │
                          ┌──────────────▼────┐   ┌───────▼────────────┐
                          │  Frontend (React)  │   │  Backend (FastAPI)  │
                          │  TS + Material UI  │   │       (:8000)       │
                          │  dark theme        │   └────────┬───────────┘
                          └────────────────────┘            │
                                                  ┌───────────┼───────────────┐
                                                  │           │               │
                                          ┌───────▼──┐  ┌─────▼─────┐  ┌──────▼──────┐
                                          │ Compat.  │  │ Services  │  │  Workers    │
                                          │  Layer   │  │ (CRUD +   │  │  (Celery)   │
                                          │ profiles │  │  EdgeConn │  │  polling)   │
                                          │  engine   │  │  client)  │  └──────┬──────┘
                                          └────┬─────┘  └─────┬─────┘         │
                                               │              │               │
                                               └──────┬───────┘               │
                                                      │                       │
                                          ┌───────────▼────────┐    ┌────────▼─────┐
                                          │  PostgreSQL +       │    │    Redis     │
                                          │  TimescaleDB       │    │ (broker +    │
                                          │  (estado + samples)│    │  result)     │
                                          └────────────────────┘    └──────────────┘
                                                      │
                                          ┌───────────▼────────────┐
                                          │   Aruba EdgeConnect     │
                                          │   (APIs reales 9.3-9.6)  │
                                          └────────────────────────┘
```

## Capas

### 1. Frontend — `frontend/`
- React 18 + TypeScript + Vite + Material UI 6, dark theme.
- Cliente API en `frontend/src/lib/api.ts` (un único módulo `api` centraliza las llamadas).
- Paneles por dominio en `frontend/src/features/`: `orchestrators/`, `appliances/`, `system/`.
- En producción se sirve desde un contenedor Nginx que expone el bundle estático.

### 2. Backend — `backend/app/`
FastAPI con API versionada bajo `/api/v1`. Estructura:

| Módulo | Responsabilidad |
|--------|-----------------|
| `api/routes/` | Definición de endpoints HTTP (thin). |
| `api/router.py` | Agregación y prefijado de routers. |
| `services/` | Lógica de negocio (orchestrator, appliance, samples, audit, system). |
| `services/edgeconnect_client.py` | Único cliente HTTP hacia EdgeConnect. |
| `compatibility/` | Engine + loader de perfiles (la Compatibility Layer). |
| `models/` | Modelos SQLModel (tablas de BD). |
| `schemas/` | DTOs Pydantic de entrada/salida. |
| `core/` | Configuración (`config.py`) y cifrado de secretos (`security.py`). |
| `db/` | Engine SQLModel, sesión e init de BD. |
| `workers/` | Celery app y tareas de polling. |

### 3. Compatibility Layer — `backend/app/compatibility/`
- **Perfiles** (`profiles/edgeconnect-9.{3,4,5,6}.json`): documentan, por versión, cada `operation_id` → `{method, path, polling_hint_seconds, notes}` y el `api_root`.
- **Loader** (`loader.py`): carga los perfiles built-in y genera borradores desde documentos OpenAPI subidos.
- **Engine** (`engine.py`): resuelve un `(version, operation_id, path_params)` en un `ResolvedOperation` (method + path final), validando parámetros de path.

Regla de oro: **ningún código fuera de `edgeconnect_client.py` construye URLs de EdgeConnect**. Todo pasa por `CompatibilityEngine.resolve()`.

### 4. Persistencia — PostgreSQL + TimescaleDB
- Estado operacional: `Orchestrator`, `Appliance`, `ApiCompatibilityProfile`, `AuditEvent`.
- Telemetría/auditoría: `ApiSample` (cada llamada real deja una fila, ver [ADR-0002](./ADR/ADR-0002-real-api-samples.md)).
- Los campos JSON usan `JSONB` en PostgreSQL y `JSON` como fallback (ej. SQLite en tests locales).

### 5. Cola — Redis + Celery
- Broker y result backend en Redis (DBs 1 y 2 respectivamente).
- Tareas: `poll_orchestrator` (cola `orchestrators`) y `poll_appliance` (cola `appliances`).
- Las tareas reutilizan los mismos servicios que las rutas HTTP, garantizando comportamiento idéntico síncrono/asíncrono.

### 6. Entrada — Nginx
- Punto único de entrada en `:8080`.
- Rutea `/api/v1/*` al backend y `/` a la UI.

## Flujo de datos reales (Fase 2)

1. El operador agrega un **Orchestrator** (URL, auth, credenciales) desde la UI.
2. `Validate` → `orchestrator.version` real → detecta versión y guarda un `ApiSample` de éxito/error.
3. `Discover` → `orchestrator.inventory.summary` → upsert de appliances desde el payload real.
4. `Metrics` en un appliance → `appliance.performance` → sample persistido.
5. Todo se audita en `AuditEvent` y se puede inspeccionar en **Real API Samples**.

> Si un endpoint de Aruba cambia, **no se toca el servicio**: se actualiza o genera el perfil de compatibilidad correspondiente.

## Seguridad

- Los secretos (passwords, api tokens) se reciben por API, se **cifran con Fernet** derivado de `SECRET_KEY` antes de persistir, y se **enmascaran** en las respuestas (`mask_secret`).
- `has_secret` expone solo un booleano, nunca el valor.
- **Cambiar `SECRET_KEY` invalida los secretos ya cifrados.**
- TLS al orquestador es configurable por orquestador (`verify_tls`, default `true`).

## Decisiones clave

- [ADR-0001 — Compatibility Layer First](./ADR/ADR-0001-compatibility-layer.md)
- [ADR-0002 — Persist Raw API Samples](./ADR/ADR-0002-real-api-samples.md)
- [MTDS 0.1 — Architecture](./MTDS/MTDS-0.1-Architecture.md)
- [MTDS 0.2 — Real Data Collection](./MTDS/MTDS-0.2-Real-Data.md)
