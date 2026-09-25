# DashboardAPI-EC 1.1

DashboardAPI-EC es un servicio web para descubrir, consultar y visualizar entornos HPE Aruba Networking EdgeConnect. La aplicación identifica la versión del Orchestrator, carga su perfil de compatibilidad, descubre los appliances administrados y conserva evidencia de cada llamada API utilizada para construir el dashboard.

La versión 1.1 se soporta exclusivamente en Ubuntu con Python 3.12 o superior y se distribuye como paquete `.deb`. Ubuntu 20.04 y 22.04 no son compatibles con su Python predeterminado; versiones posteriores de Ubuntu sí están admitidas.

## Instalación rápida

Para conectar con usuario, contraseña y OTP, el asistente envía las credenciales
y después espera el código vigente de tu aplicación. La [guía de autenticación](docs/AUTHENTICATION.md)
explica el flujo, la duración de la sesión y el diagnóstico de errores 404.

En un servidor Ubuntu con Python 3.12 o superior:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
sudo ./scripts/install-ubuntu.sh
```

El script instala dependencias, construye el `.deb`, configura los servicios y verifica `/api/v1/health`. Al terminar muestra la dirección que debes abrir. La guía completa de instalación, actualización, respaldo y diagnóstico está en [docs/INSTALLATION.md](docs/INSTALLATION.md).

Para actualizar desde la versión 1.0, vuelve a ejecutar `sudo ./scripts/install-ubuntu.sh` o instala el paquete nuevo con `sudo apt install ./dashboardapi-ec_1.1.0_amd64.deb`. Los datos y credenciales se conservan y las migraciones se aplican solas; después ejecuta el descubrimiento de appliances para poblar el `nePk` antes de recolectar métricas.

## Cambios de 1.1

- El descubrimiento persiste el identificador `nePk` (por ejemplo `1.NE`) que devuelve
  `GET /gms/rest/appliance` de cada Orchestrator.
- Las llamadas por-appliance usan el `nePk` del EdgeConnect en lugar de la dirección MAC
  o el hostname; la API del Orchestrator no acepta MAC como identificador de ruta.
- Estadísticas por appliance mediante los endpoints reales del Orchestrator:
  `GET /stats/timeseries/appliance?nePk=...` (rendimiento), `GET /interfaceState/{nePk}`
  (interfaces), `GET /stats/aggregate/tunnel?nePk=...` (túneles) y `POST /health`
  (resumen de pérdida, latencia, jitter y MOS). La recolección usa una ventana de
  15 minutos con granularidad por minuto.
- El panel de appliances muestra la columna `nePk` para verificar el identificador real.

## Alcance de 1.0

- Asistente web para conectar Orchestrator on-premises y Orchestrator as a Service.
- Autenticación mediante API key `X-Auth-Token`, sesión local con CSRF, sesión interactiva con OTP y HTTP Basic.
- Detección de versiones 9.3, 9.4, 9.5 y 9.6, con una equivalencia explícita de Orchestrator 9.7 al perfil API 9.6. Otras versiones desconocidas no se aceptan por aproximación.
- Perfil compatible con EdgeConnect 9.6 basado en la referencia pública de HPE Aruba Networking.
- Importación persistente de documentos OpenAPI 3 y Swagger 2 en JSON o YAML.
- Activación explícita de perfiles importados y checksum SHA-256 del documento original.
- Descubrimiento real de appliances y registro de capacidades declaradas y verificadas.
- Modelo normalizado de appliances, sitios y métricas con referencia a la muestra API original.
- Dashboard ensamblado en tiempo de ejecución según versión y capacidades disponibles.
- Inspector visual con método, ruta, parámetros, valores extraídos, transformaciones, latencia y respuesta sanitizada.
- Ejemplos reproducibles en cURL, Python y JavaScript sin exponer credenciales reales.
- Credenciales cifradas, respuestas sin secretos y OTP de uso único no persistente.
- Varias conexiones simultáneas, cada una con credenciales, versión y capacidades independientes.
- Rotación de credenciales desde la interfaz sin volver a registrar el Orchestrator.
- Recolección automática mediante Celery Beat y selección individual de appliances.
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

Después de la conexión, el frontend solicita `/api/v1/dashboard/{id}`. El backend cruza el perfil de la versión detectada con las operaciones declaradas, las capacidades verificadas y las muestras disponibles. Con ese resultado entrega una definición de dashboard lista para renderizar. Una tarjeta puede estar en uno de estos estados:

| Estado | Significado |
| --- | --- |
| `ready` | La capacidad existe y ya hay una muestra que respalda la visualización. |
| `waiting` | La capacidad existe, pero falta ejecutar la primera consulta. |
| `unavailable` | La versión o el Swagger activo no declara la operación requerida. |

El frontend no supone que todos los Orchestrators ofrecen los mismos datos. Muestra cada módulo según la definición devuelta por el backend y explica por qué una capacidad todavía no está disponible.

## Normalización y trazabilidad

Las respuestas del fabricante se conservan como muestras inmutables en `apisample`. Sobre ellas se construye un modelo común:

- `networkresource`: recursos identificables como appliances y sitios, con atributos del fabricante y estado observado;
- `metricpoint`: valores numéricos con namespace, unidad inferida, dimensiones y fecha de observación;
- `source_sample_id`: enlace desde cada recurso o métrica hacia la llamada que produjo el dato;
- `source_operation_id`: nombre estable de la operación, independiente de la ruta usada en cada versión.

El flujo de datos es:

```text
Swagger / perfil 9.x
        │ resuelve operación estable
        ▼
Cliente EdgeConnect ──► muestra API sin modificar
        │                         │
        │ normaliza               │ conserva evidencia
        ▼                         ▼
recursos + métricas ──► compositor de widgets
                                  │
                                  ▼
                        dashboard + inspector API
```

Durante el descubrimiento, el inventario se transforma en recursos `appliance` y `site`. Durante la colección de rendimiento, todos los campos numéricos se aplanan en puntos métricos. Los booleanos no se interpretan como números. La respuesta original continúa disponible para auditoría.

## Inspector API

Cada widget con evidencia ofrece **Ver API utilizada**. El panel lateral muestra:

1. operación estable, método HTTP y ruta resuelta para la versión;
2. código HTTP y tiempo de respuesta;
3. parámetros utilizados;
4. valores que alimentan la visualización;
5. transformaciones aplicadas;
6. JSON sanitizado;
7. ejemplos equivalentes en cURL, Python y JavaScript.

El sanitizador reemplaza valores asociados con contraseñas, tokens, API keys, cookies, encabezados de autorización y CSRF por `[REDACTED]`. Los ejemplos emplean las variables `ORCHESTRATOR_URL` y `EDGECONNECT_API_KEY`; nunca incluyen el secreto guardado.

Para OaaS se recomienda crear una API key dedicada con permisos de solo lectura. El administrador completa el segundo factor en la interfaz de Orchestrator al crear la clave; DashboardAPI-EC usa después la clave en `X-Auth-Token`. El OTP interactivo también está soportado para instalaciones que lo expongan en el login, pero no se almacena y por ello no puede utilizarse para polling desatendido.

## Administración de varios Orchestrators

La plataforma no usa una credencial global. Cada fila de Orchestrator guarda de forma independiente su URL, tenant, tipo de autenticación, usuario, secreto cifrado y etiqueta. Puedes conectar producción, laboratorios y tenants distintos desde el mismo dashboard y elegir cuál visualizar en el selector superior.

Para rotar una API key o contraseña, pulsa **Credenciales** en la conexión correspondiente. El backend cifra el nuevo secreto antes de persistirlo, elimina el tipo de secreto anterior si cambia el método y registra el evento sin incluir el valor. Después pulsa **Validar** para confirmar el acceso.

El archivo `/etc/dashboardapi-ec/dashboardapi-ec.env` contiene `SECRET_KEY`, que protege todas las credenciales guardadas. Debe respaldarse junto con PostgreSQL y conservar permisos `0640`.

## Paso 9: recolección automática

Celery Beat evalúa cada minuto los intervalos configurados:

- actualiza inventario de cada Orchestrator con polling habilitado;
- recolecta rendimiento de cada appliance con **Auto** activo;
- mantiene muestras y métricas separadas por `orchestrator_id` y `appliance_id`;
- omite sesiones OTP porque requieren intervención humana.

Los equipos descubiertos por primera vez activan el monitoreo automáticamente. El interruptor **Auto** permite excluir un appliance sin eliminar su inventario ni su historial.

## Paso 10: entrega operativa

La instalación oficial usa un paquete `.deb` para Ubuntu. `scripts/install-ubuntu.sh` automatiza la construcción, instalación y comprobación de salud. El workflow de GitHub valida backend y frontend y genera el `.deb` como artefacto descargable en cada ejecución sobre `main`.

## Swagger y compatibilidad 9.6

La aplicación incluye un perfil 9.6 para las operaciones necesarias durante conexión y descubrimiento. Además, permite importar el Swagger completo proporcionado por el Orchestrator.

Orchestrator **9.7.x**, incluida **9.7.1.42046**, se acepta utilizando las mismas rutas, métodos y capacidades del perfil **9.6**. La respuesta de validación conserva la versión completa detectada y distingue el perfil API seleccionado. Esta equivalencia es una configuración explícita del proyecto, no una certificación del fabricante; cada endpoint sigue sujeto a la disponibilidad y permisos del Orchestrator. Un perfil 9.7 importado y activado tendrá prioridad sobre esta equivalencia.

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

- Ubuntu con Python 3.12 o superior.
- Arquitectura `amd64` o `arm64`.
- 4 GB de RAM como mínimo; 8 GB recomendados.
- Acceso HTTPS desde el servidor hacia el Orchestrator y los appliances que se consultarán.
- Privilegios `sudo` para instalar el paquete.

Instalar el paquete generado:

```bash
sudo apt install ./dashboardapi-ec_1.1.0_amd64.deb
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

El resultado se guarda en `dist/dashboardapi-ec_1.1.0_<arquitectura>.deb`. El paquete incluye las ruedas Python necesarias, por lo que la instalación del runtime no descarga paquetes desde PyPI.

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
| `GET` | `/api/v1/orchestrators/{id}/credential-status` | Consultar estado seguro de la credencial |
| `PUT` | `/api/v1/orchestrators/{id}/credentials` | Rotar credenciales cifradas |
| `GET` | `/api/v1/orchestrators/{id}/capabilities` | Consultar capacidades |
| `POST` | `/api/v1/orchestrators/{id}/discover-appliances` | Descubrir inventario |
| `GET` | `/api/v1/appliances` | Listar appliances |
| `POST` | `/api/v1/appliances/{id}/collect` | Obtener métricas |
| `PATCH` | `/api/v1/appliances/{id}/monitoring` | Activar o detener recolección automática |
| `GET` | `/api/v1/samples` | Revisar llamadas y respuestas |
| `GET` | `/api/v1/samples/{id}/trace` | Obtener evidencia sanitizada y ejemplos de código |
| `GET` | `/api/v1/dashboard/{orchestrator_id}` | Componer widgets según capacidades y datos disponibles |
| `POST` | `/api/v1/compatibility/swagger` | Importar OpenAPI/Swagger |

### Ejemplo de dashboard dinámico

```bash
curl http://localhost/api/v1/dashboard/ORCHESTRATOR_UUID
```

Respuesta abreviada:

```json
{
  "orchestrator_name": "EdgeConnect Producción",
  "api_version": "9.6",
  "sections": [
    {
      "id": "fleet",
      "widgets": [
        {
          "id": "appliances",
          "status": "ready",
          "value": 12,
          "required_operations": ["orchestrator.inventory.summary"],
          "provenance": {
            "sample_id": "...",
            "method": "GET",
            "path": "/appliance"
          }
        }
      ]
    }
  ]
}
```

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

Validaciones utilizadas para la versión 1.1:

```bash
cd backend
ruff check app tests
pytest -q

cd ../frontend
npm run build
```

Las migraciones `20260923_0002` y `20260924_0004` añaden recursos normalizados, puntos métricos, metadatos de trazabilidad y el identificador `ne_pk` de cada appliance. Pueden aplicarse sobre una instalación 1.0 existente con `alembic upgrade head`; también funcionan en una instalación nueva.

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
- Activar **Certificado HTTPS** antes de publicar el servicio. La [guía de certificados](docs/HTTPS.md) explica la carga PEM/DER/PFX, el túnel SSH inicial, la renovación y la recuperación.
- Limitar por firewall el acceso al dashboard.
- Rotar API keys sin cambiar `SECRET_KEY`.

## Estado de la versión

La versión 1.0 stable cubre los pasos 1 a 10: estabilización, Swagger 9.6, autenticación, asistente de configuración, múltiples Orchestrators con credenciales independientes, detección de versión, inventario normalizado, composición dinámica de widgets, inspector visual de API, recolección automática y entrega `.deb` para Ubuntu. La versión 1.1 añade el identificador `nePk` para las llamadas por-appliance; tras actualizar desde 1.0, ejecuta el descubrimiento de appliances en cada Orchestrator para poblarlo.

## Referencias oficiales

- [EdgeConnect: Making API Requests](https://developer.arubanetworks.com/edgeconnect/docs/making-api-requests)
- [Authentication: CSRF Token & API Key](https://developer.arubanetworks.com/edgeconnect/docs/authentication)
- [Orchestrator and EdgeConnect API endpoints](https://developer.arubanetworks.com/edgeconnect/docs/aruba-orchestrator-and-edgeconnect-api-endpoints)
- [REST API Monitoring](https://developer.arubanetworks.com/edgeconnect/docs/monitoring)

## Licencia

DashboardAPI-EC se distribuye bajo una [licencia de uso restringido](../LICENSE). La comercialización, la copia fuera de la instalación/respaldo y la redistribución requieren autorización escrita. Se permite el uso interno y se conservan los derechos de terceros y los permisos concedidos sobre versiones anteriores. No es una licencia MIT.

## Donaciones

```text
╭──────────────────────────────────────────────────────╮
│              ♥  APOYA DASHBOARDAPI-EC  ♥             │
│   Ayuda al desarrollo y mantenimiento del proyecto. │
│          Donaciones: decameru@outlook.com            │
╰──────────────────────────────────────────────────────╯
```

Para conocer los medios disponibles, escribe a [decameru@outlook.com](mailto:decameru@outlook.com).

## Contacto

**[decameru@outlook.com](mailto:decameru@outlook.com)**
