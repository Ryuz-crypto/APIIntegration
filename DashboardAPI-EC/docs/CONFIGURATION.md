# Configuración

> Toda la configuración del backend se gestiona con variables de entorno cargadas desde `.env` vía `pydantic-settings` (`app.core.config.Settings`).
> Copia `.env.example` a `.env` y ajusta los valores. Las variables de entorno del SO tienen prioridad sobre `.env`.

## Variables

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PROJECT_NAME` | `DashboardAPI-EC` | Nombre del proyecto (título OpenAPI) |
| `ENVIRONMENT` | `local` | Entorno actual (`local`, `prod`...) |
| `API_V1_PREFIX` | `/api/v1` | Prefijo de la API versionada |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173,http://localhost:8080` | Orígenes CORS permitidos (separados por coma) |
| `DATABASE_URL` | `sqlite:///./dashboardapi_ec.db` | URL SQLAlchemy. En Docker: `postgresql+psycopg://...` |
| `REDIS_URL` | `redis://redis:6379/0` | Redis para uso general |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Broker Celery |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Result backend Celery |
| `SECRET_KEY` | `change-me-before-production` | Clave de cifrado Fernet de secretos. **Cámbiala en producción.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Reservado para auth futura |

## Frontend (Vite)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `/api/v1` | Base URL del backend para el cliente `api` |

## Docker Compose

| Variable | Default | Servicio | Notas |
|----------|---------|----------|-------|
| `POSTGRES_USER` | `edgeconnect` | postgres | Usuario de BD |
| `POSTGRES_PASSWORD` | `edgeconnect` | postgres | Password de BD |
| `POSTGRES_DB` | `edgeconnect` | postgres | Base de datos |

> Las variables `POSTGRES_*` se interpolan en `DATABASE_URL` manualmente en `.env`. Manténlas consistentes.

## Seguridad

- **`SECRET_KEY`** deriva la clave Fernet (SHA-256 → base64 urlsafe). Cambiarla **invalida** todos los secretos ya cifrados (`encrypted_password`, `encrypted_api_token`).
- En producción usa un valor aleatorio de al menos 32 bytes, por ejemplo:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `verify_tls` se controla por orquestador (default `true`). Desactívalo solo para orquestadores con certs autofirmados en entornos controlados.

## Ejemplo de `.env` completo

```env
PROJECT_NAME=DashboardAPI-EC
ENVIRONMENT=local
API_V1_PREFIX=/api/v1
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:8080
POSTGRES_USER=edgeconnect
POSTGRES_PASSWORD=edgeconnect
POSTGRES_DB=edgeconnect
DATABASE_URL=postgresql+psycopg://edgeconnect:edgeconnect@postgres:5432/edgeconnect
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
SECRET_KEY=change-me-before-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
```
