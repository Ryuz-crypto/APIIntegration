# DashboardAPI-EC 1.0 stable

DashboardAPI-EC es un servicio web para descubrir, consultar y visualizar entornos HPE Aruba Networking EdgeConnect. La aplicación identifica la versión del Orchestrator, carga su perfil de compatibilidad, descubre los appliances administrados y conserva evidencia de cada llamada API utilizada para construir el dashboard.

La versión 1.0 se soporta exclusivamente en Ubuntu y se distribuye como paquete `.deb`.

## Alcance de 1.0

- Asistente web para conectar Orchestrator on-premises y Orchestrator as a Service.
- Autenticación mediante API key `X-Auth-Token`, sesión local con CSRF, sesión interactiva con OTP y HTTP Basic.
- Detección estricta de versiones 9.3, 9.4, 9.5 y 9.6. Una versión desconocida nunca se acepta por aproximación.
- Perfil compatible con EdgeConnect 9.6 basado en la referencia pública de HPE Aruba Networking.
- Importación persistente de documentos OpenAPI 3 y Swagger 2 en JSON o YAML.
- Activación explícita de perfiles importados y checksum SHA-256 del documento original.
- Descubrimiento real de appliances y registro de capacidades declaradas y verificadas.
- Credenciales cifradas, respuestas sin secretos y OTP de uso único no persistente.
- Backend FastAPI, frontend React, PostgreSQL, Redis, Celery y Nginx.
- Migraciones de base de datos con Alembic.
- Instalación nativa mediante `.deb` y servicios `systemd`.

## Flujo de conexión

El asistente solicita, en orden:

1. Tipo de despliegue: OaaS u on-premises.
2. URL, nombre y tenant o región opcional.
3. Método de autenticación y credenciales.
4. Validación TLS y timeout.
5. Detección de versión, perfil compatible, capacidades e inventario.

Para OaaS se recomienda crear una API key dedicada con permisos de solo lectura. El administrador completa el segundo factor en la interfaz de Orchestrator al crear la clave; DashboardAPI-EC usa después la clave en `X-Auth-Token`. El OTP interactivo también está soportado para instalaciones que lo expongan en el login, pero no se almacena y por ello no puede utilizarse para polling desatendido.

## Swagger y compatibilidad 9.6

La aplicación incluye un perfil 9.6 para las operaciones necesarias durante conexión y descubrimiento. Además, permite importar el Swagger completo proporcionado por el Orchestrator.

Según la documentación de HPE Aruba Networking, el documento del Orchestrator se encuentra en:

```text
/home/gms/gms/webcontent/webclient/html/apiDocs/gmsApiInfo.json
```

También puede obtenerse desde **Support → REST APIs**. El documento de un appliance ECOS se encuentra en:

```text
/opt/tms/lib/web/content/node/apiDocs/vxoaApiInfo.json
```

Importar un documento como borrador:

```bash
curl -F "file=@gmsApiInfo.json" \
  "http://dashboard.example/api/v1/compatibility/swagger?version=9.6"
```

Activarlo después de verificarlo:

```bash
curl -X POST \
  "http://dashboard.example/api/v1/compatibility/profiles/9.6/activate"
```

La importación conserva el documento original, genera un perfil normalizado y calcula un checksum. La extensión opcional `x-dashboard-operation` permite asociar un endpoint Swagger con una operación estable del dashboard.

## Instalación en Ubuntu

### Requisitos

- Ubuntu 24.04 LTS.
- Arquitectura `amd64` o `arm64`.
- 4 GB de RAM como mínimo; 8 GB recomendados.
- Acceso HTTPS desde el servidor hacia el Orchestrator y los appliances que se consultarán.
- Privilegios `sudo` para instalar el paquete.

Instalar el paquete generado:

```bash
sudo apt install ./dashboardapi-ec_1.0.0_amd64.deb
```

El instalador:

- rechaza distribuciones distintas de Ubuntu;
- crea el usuario de sistema `dashboardapi`;
- instala el backend en `/opt/dashboardapi-ec`;
- publica el frontend en `/usr/share/dashboardapi-ec/frontend`;
- crea la configuración en `/etc/dashboardapi-ec/dashboardapi-ec.env`;
- crea la base `dashboardapi_ec` y el rol PostgreSQL local;
- ejecuta las migraciones;
- configura Nginx;
- habilita la API y el worker mediante `systemd`.

Después de instalar, abrir:

```text
http://IP-DEL-SERVIDOR/
```

Swagger de DashboardAPI-EC:

```text
http://IP-DEL-SERVIDOR/api/v1/docs
```

### Construir el `.deb`

La construcción también debe ejecutarse en Ubuntu:

```bash
sudo apt update
sudo apt install -y build-essential dpkg-dev python3 python3-pip python3-venv nodejs npm
./scripts/build-deb.sh
```

El resultado se guarda en `dist/dashboardapi-ec_1.0.0_<arquitectura>.deb`. El paquete incluye las ruedas Python necesarias, por lo que la instalación del runtime no descarga paquetes desde PyPI.

## Operación del servicio

```bash
sudo systemctl status dashboardapi-ec
sudo systemctl status dashboardapi-ec-worker
sudo journalctl -u dashboardapi-ec -f
sudo journalctl -u dashboardapi-ec-worker -f
```

Reiniciar después de cambiar la configuración:

```bash
sudo systemctl restart dashboardapi-ec dashboardapi-ec-worker
```

Validar Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Configuración

Archivo principal:

```text
/etc/dashboardapi-ec/dashboardapi-ec.env
```

Variables relevantes:

| Variable | Función |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL |
| `REDIS_URL` | Estado y caché de Redis |
| `CELERY_BROKER_URL` | Cola de tareas |
| `CELERY_RESULT_BACKEND` | Resultados de Celery |
| `SECRET_KEY` | Cifra credenciales de EdgeConnect |
| `BACKEND_CORS_ORIGINS` | Orígenes web permitidos |
| `AUTO_CREATE_SCHEMA` | Solo desarrollo; en producción debe ser `false` |

No debe cambiarse `SECRET_KEY` después de guardar credenciales: hacerlo vuelve indescifrables los secretos existentes.

## Arquitectura

```text
Navegador
   │
   ▼
Nginx :80
   ├── /             → React
   └── /api/v1       → FastAPI :8010
                            ├── PostgreSQL
                            ├── Redis / Celery
                            └── EdgeConnect Orchestrator / ECOS
```

Los servicios no codifican rutas de EdgeConnect directamente. Solicitan operaciones estables como `orchestrator.version` u `orchestrator.inventory.summary`; la capa de compatibilidad resuelve el método y la ruta correspondientes a cada versión.

## Endpoints principales

| Método | Ruta | Propósito |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Salud de la API |
| `POST` | `/api/v1/orchestrators` | Registrar una conexión |
| `POST` | `/api/v1/orchestrators/{id}/validate` | Autenticar y detectar versión |
| `GET` | `/api/v1/orchestrators/{id}/capabilities` | Consultar capacidades |
| `POST` | `/api/v1/orchestrators/{id}/discover-appliances` | Descubrir inventario |
| `GET` | `/api/v1/appliances` | Listar appliances |
| `POST` | `/api/v1/appliances/{id}/collect` | Obtener métricas |
| `GET` | `/api/v1/samples` | Revisar llamadas y respuestas |
| `POST` | `/api/v1/compatibility/swagger` | Importar OpenAPI/Swagger |

## Desarrollo

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
pytest -q
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Construcción de producción:

```bash
cd frontend
npm run build
```

## Docker para desarrollo

Docker Compose se conserva para desarrollo y laboratorios:

```bash
cp .env.example .env
docker compose up --build
```

La distribución recomendada para servidores Ubuntu es el paquete `.deb`.

## Copia de seguridad

```bash
sudo -u postgres pg_dump dashboardapi_ec > dashboardapi_ec.sql
sudo cp /etc/dashboardapi-ec/dashboardapi-ec.env dashboardapi-ec.env.backup
```

El respaldo del archivo de entorno contiene la clave utilizada para cifrar credenciales y debe protegerse como un secreto.

## Seguridad operativa

- Usar API keys de solo lectura y con expiración.
- Mantener la verificación TLS activa.
- Instalar una CA interna en Ubuntu cuando el Orchestrator use certificados privados.
- No exponer el puerto interno `8010` fuera del host.
- Colocar TLS en Nginx antes de publicar el servicio fuera de una red administrativa.
- Limitar por firewall el acceso al dashboard.
- Rotar API keys sin cambiar `SECRET_KEY`.

## Estado de la versión

La versión 1.0 cubre estabilización, Swagger 9.6, autenticación, asistente de configuración, detección de versión y descubrimiento inicial de capacidades. El siguiente incremento incorporará composición dinámica de widgets, inspector visual de API, series temporales y alarmas en tiempo real.

## Referencias oficiales

- [EdgeConnect: Making API Requests](https://developer.arubanetworks.com/edgeconnect/docs/making-api-requests)
- [Authentication: CSRF Token & API Key](https://developer.arubanetworks.com/edgeconnect/docs/authentication)
- [Orchestrator and EdgeConnect API endpoints](https://developer.arubanetworks.com/edgeconnect/docs/aruba-orchestrator-and-edgeconnect-api-endpoints)
- [REST API Monitoring](https://developer.arubanetworks.com/edgeconnect/docs/monitoring)
