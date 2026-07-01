# DashboardAPI-EC

Primera fase en codigo para una plataforma NOC/SOC de Aruba EdgeConnect.

Esta fase deja una base instalable y modular:

- Backend FastAPI con modelos para Orchestrators, Appliances, perfiles API y auditoria.
- Compatibility Layer obligatorio para resolver operaciones por version.
- Perfiles iniciales para EdgeConnect 9.3, 9.4, 9.5 y 9.6.
- Swagger Loader base para generar perfiles sin cambiar codigo.
- Workers Celery preparados para polling.
- PostgreSQL con TimescaleDB y Redis.
- Frontend React, TypeScript y Material UI en dark theme.
- Nginx como punto de entrada.
- Documentos MTDS y ADR para guiar las siguientes fases.
- Fase 2: cliente HTTP real para EdgeConnect, credenciales cifradas, discovery real y muestras API persistidas.

## Arranque local

1. Copiar variables:

```bash
cp .env.example .env
```

2. Levantar la plataforma:

```bash
docker compose up --build
```

3. Abrir:

- UI: `http://localhost:8080`
- API: `http://localhost:8080/api/v1`
- Docs API: `http://localhost:8080/api/v1/docs`

## Flujo con datos reales

1. Entrar a la UI.
2. Agregar un Orchestrator con URL real, tipo de autenticacion y credenciales.
3. Usar `Validate` para ejecutar una llamada real a `orchestrator.version`.
4. Usar `Discover` para leer inventario real desde `orchestrator.inventory.summary`.
5. Usar `Metrics` en un Appliance para recolectar `appliance.performance`.
6. Revisar `Real API Samples` para ver HTTP status, latencia, operacion y payload almacenado.

Si un endpoint de Aruba cambia, no se modifica el servicio: se actualiza el perfil de compatibilidad o se genera uno nuevo con Swagger/OpenAPI.

## Principios de fase 1

- Ningun servicio llama endpoints de EdgeConnect directamente.
- Toda operacion se resuelve por `backend/app/compatibility`.
- La configuracion operativa se modela para ser administrada desde UI.
- El backend separa Orchestrator y Appliance.
- Secretos se reciben por API, se enmascaran en respuestas y quedan preparados para cifrado.
- La fase 2 guarda secretos cifrados con `SECRET_KEY`; cambiar ese valor invalida secretos ya cifrados.

## Estructura

```text
DashboardAPI-EC/
  backend/
  frontend/
  infrastructure/
  docs/
  scripts/
  docker-compose.yml
```
