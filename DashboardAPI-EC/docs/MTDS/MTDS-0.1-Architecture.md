# MTDS 0.1 - Architecture

## Scope

Phase 1 creates the installable foundation for DashboardAPI-EC.

## Components

- React TypeScript UI for operational administration.
- FastAPI backend with versioned API.
- Compatibility Layer for all EdgeConnect API operation resolution.
- PostgreSQL/TimescaleDB for state and metrics readiness.
- Redis and Celery for future polling workloads.
- Nginx entrypoint for UI and API routing.

## Rules

- EdgeConnect endpoints are never called directly from route or service code.
- Orchestrator polling and Appliance polling are separate concerns.
- All runtime configuration must be represented through API/UI flows.
- Secrets must be masked in responses and audit trails.

## Phase 1 Acceptance

- Docker Compose can build all services.
- Backend exposes health, system, orchestrator, appliance and compatibility endpoints.
- UI can add and validate an Orchestrator, then trigger Appliance discovery.
- Compatibility profiles exist for 9.3, 9.4, 9.5 and preview 9.6.
