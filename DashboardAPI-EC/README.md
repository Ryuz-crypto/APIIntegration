# DashboardAPI-EC 1.4.0 stable

[![DashboardAPI-EC](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml)
[![Human Tested](https://img.shields.io/badge/Human%20Tested-EdgeConnect%209.7.1-7B61FF?logo=checkmarx&logoColor=white)](#validación-humana-y-automatizada)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-Python%203.12%2B-E95420?logo=ubuntu&logoColor=white)](docs/INSTALLATION.md)

DashboardAPI-EC es un servicio web para descubrir, consultar y visualizar entornos HPE Aruba Networking EdgeConnect. La aplicación identifica la versión del Orchestrator, carga su perfil de compatibilidad, descubre los appliances administrados y conserva evidencia de cada llamada API utilizada para construir el dashboard.

La versión 1.4 se soporta en Ubuntu con Python 3.12 o superior y se distribuye como paquete `.deb`. El instalador acepta cualquier versión de Ubuntu que cumpla los requisitos técnicos, incluidas las posteriores a 24.04.

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

Para pasar de una versión anterior a 1.2, ejecuta una vez `git pull && sudo ./scripts/install-ubuntu.sh`. A partir de 1.2 puedes instalar versiones oficiales desde **Actualizar** en la cabecera. El motor valida el tag de GitHub, crea un respaldo y conserva el paquete anterior para recuperación. Consulta [docs/UPDATES.md](docs/UPDATES.md).

## Cambios de 1.4

- Pantalla de acceso obligatoria y creación segura del primer administrador con `TLS_ADMIN_TOKEN`.
- Menú **Acceso** para administrar usuarios, roles, estado de cuentas, contraseña propia y auditoría.
- Roles `viewer`, `operator` y `admin` aplicados por el backend.
- Sesiones revocables de 12 horas, tokens almacenados como SHA-256 y contraseñas derivadas con scrypt.
- Motor de actualización desde el dashboard incluido y documentado para instalación nativa en Ubuntu.

La versión 1.3 añadió:

- Nueva pestaña **Try Me** con catálogo completo derivado del Swagger de cada Orchestrator.
- Búsqueda por método, path, operación o tag; formularios interactivos para parámetros de path, query y headers.
- Editor JSON para cuerpos de `POST`, `PUT` y `PATCH`, con ejemplos generados desde el schema.
- Ejecución con las credenciales cifradas ya asociadas al Orchestrator y soporte de la sesión OTP vigente.
- Confirmación reforzada y clave administrativa para operaciones que pueden cambiar configuración.
- Exportación de request/response como JSON o CSV y snapshots persistentes para conservar evidencia.
- Importación del Swagger completo desde Try Me sin activar el documento para el dashboard.

## Cambios de 1.2

- Motor de actualización desde el dashboard, basado exclusivamente en tags estables oficiales con formato `vX.Y.Z-stable`.
- Confirmación explícita de la versión y la misma clave administrativa utilizada para HTTPS.
- Ejecución privilegiada aislada mediante `systemd`; el proceso web sólo puede dejar una solicitud validada.
- Respaldo previo de PostgreSQL, entorno, Nginx y certificados, verificación de salud y reinstalación automática del paquete anterior si falla la actualización.
- Estado visible en tiempo real y registro operativo mediante `journalctl`.

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
- La recolección exige `nePk` y no intenta sustituirlo con hostname, serial o MAC.
- Cada ciclo consulta rendimiento, interfaces y túneles; un endpoint opcional que falle queda registrado sin descartar las respuestas correctas de los demás.
- Editor global inspirado en WAN_SIM para nombre, mensaje, seis colores, tipografía e icono, con vista previa y persistencia en PostgreSQL.
- Crédito fijo **Powered by Emilio Abundis**.

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

## HTTPS y personalización

La cabecera incluye **Certificado HTTPS** y **Apariencia**. HTTPS acepta PEM, DER y PFX/P12, comprueba SAN, vigencia y clave privada, y solicita al servicio privilegiado de Ubuntu que active Nginx de forma transaccional. Consulta [docs/HTTPS.md](docs/HTTPS.md) para la primera carga mediante túnel SSH, renovación, almacenamiento y recuperación.

La opción **Actualizar** consulta el canal oficial, muestra la versión instalada y permite elegir una versión posterior. La operación requiere HTTPS o acceso local por túnel SSH, la clave `TLS_ADMIN_TOKEN` y la frase exacta que muestra el panel. La guía de [actualizaciones administradas](docs/UPDATES.md) explica el flujo, los respaldos y la recuperación.

El menú **Acceso** gestiona identidades locales con tres roles. La [guía de acceso](docs/ACCESS.md) documenta el administrador inicial, sesiones, permisos, auditoría y autenticación Bearer para la API.

La pestaña **Try Me** presenta todas las operaciones del Swagger almacenado, incluidos endpoints que no forman parte del dashboard. Consulta [docs/TRYME.md](docs/TRYME.md) para importar el contrato del Orchestrator, ejecutar lecturas y cambios, exportar resultados y administrar snapshots.

El editor de apariencia guarda globalmente:

- nombre y mensaje principal;
- colores principal, secundario, encabezado, fondo, paneles y texto;
- icono de red, actividad, tablero o flujo;
- tipografía Inter, sistema, humanista, técnica o monoespaciada.

La vista previa se actualiza antes de guardar. La atribución **Powered by Emilio Abundis** es fija y permanece visible con cualquier configuración.

## Validación humana y automatizada

El badge **Human Tested** corresponde a la comprobación manual del acceso a un Orchestrator 9.7.1.42046, autenticación en dos etapas con OTP y detección mediante el perfil API 9.6. La CI ejecuta lint, pruebas backend, compilación frontend, paquete `.deb`, instalación, actualización y activación HTTPS en Ubuntu. Esta validación no sustituye la matriz de permisos ni constituye certificación oficial de HPE.

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

Durante el descubrimiento, el inventario se transforma en recursos `appliance` y `site`. Durante la colección de rendimiento, interfaces y túneles, los campos numéricos se aplanan en puntos métricos con el namespace de su operación. Los booleanos no se interpretan como números. Cada respuesta original continúa disponible para auditoría.

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
sudo apt install ./dashboardapi-ec_1.4.0_amd64.deb
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

La primera pantalla crea la cuenta administradora. Obtén el token de instalación en el servidor y usa una contraseña de al menos 12 caracteres:

```bash
sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env
```

Después inicia sesión y abre **Conectar Orchestrator**. Para transmitir el token inicial mediante un túnel local o configurar usuarios y roles, sigue [docs/ACCESS.md](docs/ACCESS.md).

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

El resultado se guarda en `dist/dashboardapi-ec_1.4.0_<arquitectura>.deb`. El paquete incluye las ruedas Python necesarias, por lo que la instalación del runtime no descarga paquetes desde PyPI.

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
| `SESSION_EXPIRE_HOURS` | Duración de las sesiones locales; 12 horas por defecto |
| `TLS_ADMIN_TOKEN` | Segundo control para alta inicial, HTTPS, actualización y cambios sensibles |

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
| `POST` | `/api/v1/auth/bootstrap` | Crear el primer administrador una sola vez |
| `POST` | `/api/v1/auth/login` | Abrir una sesión y obtener un token Bearer |
| `GET` | `/api/v1/auth/users` | Administrar cuentas con rol administrador |
| `GET` | `/api/v1/auth/audit` | Consultar actividad reciente |
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
| `GET` | `/api/v1/system/releases` | Consultar tags oficiales disponibles |
| `GET` | `/api/v1/system/update` | Consultar el estado del activador |
| `POST` | `/api/v1/system/update` | Programar una actualización validada |
| `GET` | `/api/v1/try-me/catalog/{orchestrator_id}` | Obtener todas las operaciones Swagger |
| `POST` | `/api/v1/try-me/execute` | Ejecutar una operación validada contra el contrato |
| `GET/POST/DELETE` | `/api/v1/try-me/snapshots` | Conservar y administrar evidencia de Try Me |

Salvo salud, estado de acceso, login, bootstrap y OpenAPI, las rutas requieren `Authorization: Bearer TOKEN`. Las mutaciones también validan el rol. Algunas tareas sensibles conservan `TLS_ADMIN_TOKEN` como segundo control.

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

Validaciones utilizadas para la versión 1.4:

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

La versión 1.0 stable cubrió los pasos 1 a 10. La versión 1.1.0 añadió `nePk`, métricas reales, HTTPS administrado y apariencia persistente. La versión 1.2.0 incorporó el canal de actualizaciones. La versión 1.3.0 añadió Try Me, exportaciones y snapshots para el Swagger completo. La versión 1.4.0 añade acceso por usuarios, roles, sesiones revocables y auditoría.

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
