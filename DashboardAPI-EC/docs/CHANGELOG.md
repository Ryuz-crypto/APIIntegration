# Changelog

Todos los cambios notables de `DashboardAPI-EC` se documentan aquí.
El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-1.1.0/) y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Documentación
- Añadida guía de arquitectura (`docs/ARCHITECTURE.md`).
- Añadida referencia completa de la API REST (`docs/API.md`).
- Añadida documentación de modelos de datos (`docs/DATA-MODELS.md`).
- Añadida guía de configuración y variables de entorno (`docs/CONFIGURATION.md`).
- Añadida guía de desarrollo local (`docs/DEVELOPMENT.md`).
- Añadida guía de contribución (`CONTRIBUTING.md`).
- README enriquecido con índice, badges y enlaces a la nueva documentación.

## [0.2.0] - Fase 2: Real Data Collection

### Añadido
- Cliente HTTP real para EdgeConnect (`edgeconnect_client.py`) con TLS, timeout y redirects.
- Cifrado de credenciales con Fernet derivado de `SECRET_KEY` (`core/security.py`).
- Autenticación soportada: `none`, `basic`, `bearer`, `api_key`.
- Flujo de validación real basado en `orchestrator.version` con detección de versión.
- Discovery real de appliances basado en `orchestrator.inventory.summary` con upsert.
- Recolección de métricas de appliance basada en `appliance.performance`.
- Persistencia de muestras API crudas (`ApiSample`) para auditoría y troubleshooting.
- Eventos de auditoría (`AuditEvent`) en cada operación de negocio.
- Controles de UI para credenciales, validación, discovery, métricas y revisión de samples.
- [ADR-0002](docs/ADR/ADR-0002-real-api-samples.md) — Persist Raw API Samples.
- [MTDS 0.2](docs/MTDS/MTDS-0.2-Real-Data.md) — Real Data Collection.

## [0.1.0] - Fase 1: Foundation

### Añadido
- Backend FastAPI con API versionada bajo `/api/v1`.
- Models SQLModel para Orchestrators, Appliances, perfiles API y auditoría.
- Compatibility Layer obligatoria para resolver operaciones por versión.
- Perfiles iniciales para EdgeConnect 9.3, 9.4, 9.5 y 9.6.
- Swagger Loader base para generar perfiles desde OpenAPI sin cambiar código.
- Workers Celery preparados para polling (`poll_orchestrator`, `poll_appliance`).
- PostgreSQL con TimescaleDB y Redis.
- Frontend React + TypeScript + Material UI en dark theme.
- Nginx como punto de entrada único.
- Scripts de apoyo (`bootstrap.sh`, `dev-check.sh`).
- [ADR-0001](docs/ADR/ADR-0001-compatibility-layer.md) — Compatibility Layer First.
- [MTDS 0.1](docs/MTDS/MTDS-0.1-Architecture.md) — Architecture.
