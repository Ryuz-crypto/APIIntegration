# Contribuir a DashboardAPI-EC

¡Gracias por tu interés en contribuir! Este documento describe el flujo de trabajo y las convenciones del proyecto.

## Flujo de trabajo

1. **Abre un issue** describiendo el cambio propuesto (bug, mejora, nueva feature).
2. **Crea una rama** desde `main`:
   ```bash
   git checkout main
   git pull
   git checkout -b <tipo>/<descripcion-corta>
   ```
   Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
3. **Haz commits enfocados** con mensajes en imperativo:
   - `Add compatibility profile for EdgeConnect 9.7`
   - `Fix orchestrator validation when API version is null`
4. **Verifica** tu cambio antes de abrir PR (ver sección de checks).
5. **Abre un Pull Request** hacia `main` describiendo el qué y el por qué.

## Checks antes de abrir un PR

### Backend
```bash
cd backend
ruff check app
ruff format --check app
pytest -q
```

### Frontend
```bash
cd frontend
npm install
npm run build   # typecheck (tsc --noEmit) + build
```

### Sintaxis rápida
```bash
bash scripts/dev-check.sh
```

## Convenciones de código

- **Sin comentarios en el código** (ni standalone ni inline). La documentación va en `docs/` y en los mensajes de commit.
- **Python**: line-length 100, target `py312` (ruff). Tipado con anotaciones modernas (`str | None`).
- **TypeScript**: configuración por defecto de Vite + MUI. Sin `any` implícito.
- **Arquitectura**:
  - Rutas finas → servicios → modelos.
  - Solo `edgeconnect_client.py` construye URLs de EdgeConnect; el resto pasa por la Compatibility Layer.
  - Los servicios son reutilizados por rutas HTTP y tareas Celery.
- **Secretos**: cifrar antes de persistir, enmascarar al responder, nunca loguear ni exponer.

## Documentación

- Decisiones de diseño razonadas → [ADR](docs/ADR/) (un `ADR-NNNN-titulo.md` por decisión).
- Cambios de alcance/fase → [MTDS](docs/MTDS/).
- Cambios notables de release → [CHANGELOG.md](docs/CHANGELOG.md).
- Al añadir un endpoint, actualiza [docs/API.md](docs/API.md).
- Al añadir/modificar un modelo, actualiza [docs/DATA-MODELS.md](docs/DATA-MODELS.md).
- Al añadir una variable de entorno, actualiza [docs/CONFIGURATION.md](docs/CONFIGURATION.md) y `.env.example`.

## ADR

Para registrar una nueva decisión de arquitectura:
1. Crea `docs/ADR/ADR-NNNN-titulo-descriptivo.md` con el siguiente número disponible.
2. Estructura: `# ADR NNNN - Título`, `## Status`, `## Context`, `## Decision`, `## Consequences`.
3. Enlázalo desde `docs/ARCHITECTURE.md` si es relevante.

## Estilo de commits

- Usa el imperativo: "Add", "Fix", "Update", no "Added" ni "Adds".
- Línea de asunto ≤ 72 caracteres.
- Body opcional explicando el porqué (no el qué, que se ve en el diff).

## Reportar bugs

Abre un issue con:
- Versión de DashboardAPI-EC (o commit).
- Pasos para reproducir.
- Comportamiento esperado vs. actual.
- Logs relevantes (sin secretos).
