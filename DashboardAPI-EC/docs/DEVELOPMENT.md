# Guía de Desarrollo

> Cómo trabajar con el código de `DashboardAPI-EC` en local. Para despliegue con Docker, ver el [`README.md`](../README.md).

## Requisitos

- **Backend**: Python 3.12+
- **Frontend**: Node.js 22+ (o 18+)
- **Docker** (recomendado para Postgres + Redis locales)

## Estructura

```text
DashboardAPI-EC/
├── backend/
│   ├── app/
│   │   ├── api/            # routers
│   │   ├── compatibility/  # Compatibility Layer + perfiles JSON
│   │   ├── core/           # config, seguridad
│   │   ├── db/            # engine, sesión, init
│   │   ├── models/        # SQLModel
│   │   ├── schemas/       # Pydantic DTOs
│   │   ├── services/      # lógica de negocio + edgeconnect_client
│   │   ├── workers/       # Celery
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── features/       # paneles por dominio
│   │   ├── components/     # UI reutilizable
│   │   ├── lib/api.ts      # cliente API
│   │   └── theme/          # dark theme MUI
│   └── package.json
├── docs/
├── infrastructure/nginx/
├── scripts/
└── docker-compose.yml
```

## Scripts de apoyo

| Script | Acción |
|--------|--------|
| `scripts/bootstrap.sh` | Crea `.env` si falta y levanta todo con `docker compose up --build` |
| `scripts/dev-check.sh` | Verifica sintaxis del backend con `python -m compileall` |

```bash
bash scripts/dev-check.sh   # check de sintaxis
bash scripts/bootstrap.sh   # primer arranque con Docker
```

## Backend en local (sin Docker)

```bash
cd backend

# Entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias + dev
pip install -e ".[dev]"

# Configurar (usa SQLite por defecto si no hay .env)
cp ../.env.example ../.env

# Lint
ruff check app
ruff format app

# Tests
pytest -q

# Arrancar (necesita Postgres/Redis si DATABASE_URL apunta ahí)
uvicorn app.main:app --reload --port 8000
```

Para tests locales con SQLite no hace falta Postgres/Redis: la `DATABASE_URL` por defecto es `sqlite:///./dashboardapi_ec.db`.

## Frontend en local

```bash
cd frontend
npm install
npm run dev      # Vite dev server en :5173 con HMR
npm run build    # typecheck + build de producción → dist/
npm run preview  # servir el build
```

El cliente API usa `VITE_API_BASE_URL` (default `/api/v1`). En modo `dev` apunta a `http://localhost:8000/api/v1` solo si configuras un proxy; por defecto asume que Nginx rutea. Para apuntar directamente al backend local:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

## Compatibilidad Layer — añadir una versión de API

1. Copia `backend/app/compatibility/profiles/edgeconnect-9.4.json` a `edgeconnect-9.X.json`.
2. Ajusta `version`, `status` y las `operations` (cada una con `method`, `path`, `polling_hint_seconds`, `notes`).
3. Reinicia el backend: `init_db()` inserta el nuevo perfil si la versión no existe.
4. Verifica con `GET /compatibility/profiles`.

Para generar un borrador desde un documento OpenAPI sin tocar código: `POST /compatibility/swagger?version=9.X` con el JSON del documento.

## Workers Celery

Las tareas se definen en `app.workers.tasks` y se enrutan a colas (`orchestrators`, `appliances`). Para ejecutar el worker localmente:

```bash
cd backend
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

> Requiere Redis accesible (configurado por `CELERY_BROKER_URL`).

## Tests

```bash
cd backend
pytest -q                  # todos
pytest tests/test_compatibility_engine.py -v   # solo compatibilidad
```

Los tests actuales cubren el `CompatibilityEngine` (resolución con path params, rechazo de operaciones inexistentes, resolución de `orchestrator.version`).

## Convenciones de código

- **Python**: line-length 100, target `py312` (ver `pyproject.toml [tool.ruff]`). Sin comentarios en código.
- **TypeScript**: ESLint/Prettier por defecto de Vite + MUI. Sin comentarios en código.
- **Estilo de capa**: rutas finas → servicios → modelos. El `edgeconnect_client` es el único que arma URLs de EdgeConnect.
- **Secretos**: cifrar antes de persistir, enmascarar al responder, nunca loguear.

## Verificación rápida end-to-end (Docker)

```bash
docker compose up -d --build
curl http://localhost:8080/api/v1/health
curl http://localhost:8080/api/v1/system/overview
curl http://localhost:8080/api/v1/compatibility/profiles
```
