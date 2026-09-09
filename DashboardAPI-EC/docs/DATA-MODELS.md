# Modelos de Datos

> Esquemas de la base de datos (SQLModel → SQLAlchemy). Generados por `app.db.init_db.init_db()` al arrancar el backend.

## Diagrama de relaciones

```text
┌────────────────────┐       ┌────────────────────┐
│  ApiCompatibility  │       │     Orchestrator    │
│     Profile        │       │  (1) ────────────── │
│  (PK: version)     │       └─────────┬──────────┘
└────────────────────┘                 │ 1
                                        │
                                        │ N
                              ┌─────────▼──────────┐
                              │     Appliance       │
                              │  (FK → orchestrator)│
                              └─────────┬──────────┘
                                        │ 1
                                        │ N (opcional)
                              ┌─────────▼──────────┐        ┌────────────────────┐
                              │     ApiSample      │        │    AuditEvent      │
│  (FK → orchestrator)│        │  (autónomo)        │
                              │  (FK → appliance?)  │        └────────────────────┘
                              └────────────────────┘
```

---

## `Orchestrator`

Tabla: `orchestrator` · hereda timestamps (`created_at`, `updated_at`).

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | UUID | PK, index | UUID v4 autogenerado |
| `name` | string | index, 2-120 chars | Nombre legible |
| `base_url` | string | max 500 | URL base del orquestador (sin trailing slash) |
| `api_version` | string? | index | Versión detectada por `validate` |
| `status` | string | index, default `pending` | `pending`, `validated`, `connection_error` |
| `polling_enabled` | bool | default `false` | Activo tras validación exitosa |
| `polling_active_seconds` | int | default `120` | Intervalo con dashboard activo |
| `polling_idle_seconds` | int | default `600` | Intervalo con dashboard inactivo |
| `credential_label` | string? | max 120 | Etiqueta del secreto |
| `auth_type` | string | max 40, default `none` | `none`, `basic`, `bearer`, `api_key` |
| `username` | string? | max 160 | Usuario para `basic` |
| `encrypted_password` | string? | — | Password cifrado con Fernet |
| `encrypted_api_token` | string? | — | Token cifrado con Fernet |
| `api_key_header` | string? | max 120 | Header custom para `api_key` |
| `verify_tls` | bool | default `true` | Verificación TLS |
| `timeout_seconds` | int | default `20` | Timeout HTTP |
| `created_at` | datetime | not null | UTC |
| `updated_at` | datetime | not null | UTC |

> Propiedad `has_secret` (no persistida): `true` si hay `encrypted_password` o `encrypted_api_token`.

## `Appliance`

Tabla: `appliance` · hereda timestamps.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | UUID | PK, index | UUID v4 |
| `orchestrator_id` | UUID | FK `orchestrator.id`, index | Pertenencia |
| `hostname` | string | index, max 160 | Nombre de host |
| `serial_number` | string? | index, max 120 | Número de serie |
| `site` | string? | index, max 160 | Sitio lógico |
| `model` | string? | max 120 | Modelo |
| `software_version` | string? | index, max 40 | Versión de software |
| `status` | string | index, default `discovered` | `discovered`, `sampled`, etc. |
| `selected_for_monitoring` | bool | default `false` | Seleccionado para polling fino |
| `polling_active_seconds` | int | default `5` | Intervalo dashboard activo |
| `polling_idle_seconds` | int | default `300` | Intervalo dashboard inactivo |
| `created_at` | datetime | not null | UTC |
| `updated_at` | datetime | not null | UTC |

## `ApiSample`

Tabla: `api_sample` · sin mixin de timestamps (tiene su propio `created_at`).

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | UUID | PK, index | UUID v4 |
| `orchestrator_id` | UUID | FK, index | Orquestador origen |
| `appliance_id` | UUID? | FK, index, nullable | Appliance (si aplica) |
| `api_version` | string? | index, max 40 | Versión de API usada |
| `operation_id` | string | index, max 160 | Operación resuelta |
| `method` | string | max 12 | Método HTTP |
| `path` | string | max 600 | Path resuelto (`unresolved` en error) |
| `status_code` | int? | index | Código HTTP (null si no hubo respuesta) |
| `duration_ms` | int? | — | Latencia en ms |
| `ok` | bool | index, default `false` | Éxito de la llamada |
| `payload` | JSON / JSONB | default `{}` | Payload bruto de EdgeConnect |
| `error` | string? | max 800 | Mensaje de error |
| `created_at` | datetime | not null, index | UTC |

> En PostgreSQL `payload` usa `JSONB`; en SQLite/tests usa `JSON` (ver `JSON().with_variant(JSONB(), "postgresql")`).

## `ApiCompatibilityProfile`

Tabla: `api_compatibility_profile`.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `version` | string | PK, max 40 | Versión de API (ej. `9.4`) |
| `status` | string | index, default `supported` | Estado del perfil |
| `source` | string | max 80, default `builtin` | `builtin` o `generated` |
| `profile` | JSON / JSONB | default `{}` | Documento de perfil completo |
| `created_at` | datetime | not null | UTC |

> Se carga desde los JSON built-in en `init_db()` (solo inserta si no existe la versión).

## `AuditEvent`

Tabla: `audit_event`.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | UUID | PK, index | UUID v4 |
| `actor` | string | index, max 120, default `system` | Quién generó el evento |
| `action` | string | index, max 160 | Ej. `orchestrator.validated` |
| `resource_type` | string | index, max 80 | `orchestrator`, `appliance`... |
| `resource_id` | string? | max 160 | ID del recurso afectado |
| `ip_address` | string? | max 80 | IP del actor (si aplica) |
| `duration_ms` | int? | — | Duración de la operación |
| `details` | JSON / JSONB | columna `metadata`, default `{}` | Contexto adicional |
| `created_at` | datetime | not null | UTC |

## Inicialización

`init_db()` ejecuta al arrancar el backend (lifespan de FastAPI):
1. `SQLModel.metadata.create_all(engine)` — crea las tablas si no existen.
2. Inserta los perfiles built-in (`edgeconnect-9.3/9.4/9.5/9.6.json`) en `ApiCompatibilityProfile` si la versión aún no existe.

> No se usan migraciones automáticas en esta fase. En fases posteriores se prevé Alembic.

## Convenciones
- IDs: UUID v4.
- Timestamps: `datetime.now(UTC)`.
- Secretos: cifrados con Fernet (`app.core.security`), nunca almacenados en claro ni devueltos por la API.
