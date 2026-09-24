# DashboardAPI-EC

[![Version](https://img.shields.io/badge/version-1.0%20stable-2fbf9b)](https://github.com/Ryuz-crypto/APIIntegration)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/)
[![Licencia restringida](https://img.shields.io/badge/licencia-uso_restringido-blue.svg)](LICENSE)
[![DashboardAPI-EC](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml)

DashboardAPI-EC es una plataforma web para descubrir, consultar y visualizar entornos **HPE Aruba Networking EdgeConnect** mediante sus APIs. Detecta la versión del Orchestrator, identifica las capacidades disponibles y ensambla un dashboard específico con datos reales.

La versión **1.0 stable** funciona exclusivamente en **Ubuntu 24.04** y se distribuye como paquete `.deb`.

## Contenido

- [Características](#características)
- [Instalación rápida](#instalación-rápida)
- [Primer uso](#primer-uso)
- [Varios Orchestrators](#varios-orchestrators)
- [Cómo funciona](#cómo-funciona)
- [Operación y diagnóstico](#operación-y-diagnóstico)
- [Documentación](#documentación)
- [Seguridad](#seguridad)
- [Licencia](#licencia)
- [Donaciones](#donaciones)
- [Contacto](#contacto)

## Características

- Asistente visual para conectar Orchestrator on-premises y Orchestrator as a Service.
- Compatibilidad controlada con versiones EdgeConnect 9.3, 9.4, 9.5 y 9.6.
- Importación de contratos OpenAPI 3 y Swagger 2.
- Detección automática de versión, capacidades, appliances y sitios.
- Dashboard dinámico construido según las APIs disponibles en cada entorno.
- Inspector que muestra la operación, método, ruta, parámetros, latencia, valores extraídos y JSON sanitizado.
- Ejemplos reproducibles en cURL, Python y JavaScript.
- Credenciales independientes y cifradas para múltiples Orchestrators.
- Rotación de API keys y contraseñas desde la interfaz.
- Polling automático de inventario y rendimiento mediante Celery.
- Backend FastAPI, frontend React, PostgreSQL, Redis y Nginx.
- Instalación nativa con paquete `.deb` y servicios `systemd`.

## Instalación rápida

Requisitos mínimos:

- Ubuntu 24.04 LTS, `amd64` o `arm64`.
- 4 GB de RAM; 8 GB recomendados.
- 10 GB de espacio disponible.
- Acceso HTTPS desde el servidor hacia los Orchestrators.
- Usuario con privilegios `sudo`.

Ejecuta cada comando por separado:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
sudo ./scripts/install-ubuntu.sh
```

El instalador:

1. valida que el sistema sea Ubuntu;
2. instala las dependencias necesarias;
3. construye el paquete `dashboardapi-ec_1.0.0_<arquitectura>.deb`;
4. configura PostgreSQL, Redis, Nginx y `systemd`;
5. ejecuta las migraciones;
6. inicia los servicios;
7. comprueba el endpoint de salud;
8. muestra la URL de acceso.

La interfaz estará disponible normalmente en:

```text
http://IP-DEL-SERVIDOR/
```

Comprueba la instalación:

```bash
curl http://127.0.0.1/api/v1/health
sudo systemctl status dashboardapi-ec dashboardapi-ec-worker nginx
```

## Primer uso

1. Abre la dirección mostrada por el instalador.
2. Pulsa **Conectar Orchestrator**.
3. Selecciona **Orchestrator as a Service** u **On-premises**.
4. Introduce un nombre y la URL HTTPS del Orchestrator.
5. Escribe una etiqueta para identificar la credencial.
6. Selecciona el método de autenticación.
7. Introduce la API key o las credenciales de sesión.
8. Mantén activa la verificación TLS.
9. Pulsa **Conectar y detectar**.

La plataforma validará el acceso, detectará la versión, cargará el perfil compatible, descubrirá los appliances y construirá el dashboard.

Para OaaS se recomienda una API key dedicada con permisos de solo lectura. Las sesiones con OTP se pueden validar de forma interactiva, pero no participan en el polling automático porque el código de un solo uso nunca se almacena.

## Varios Orchestrators

Puedes registrar tantos Orchestrators como necesites. Cada conexión conserva independientemente:

- URL y tenant;
- tipo de despliegue;
- versión y capacidades detectadas;
- método de autenticación;
- usuario y secreto cifrado;
- etiqueta de la credencial;
- inventario, métricas y muestras API.

El selector superior cambia el dashboard activo. Para rotar una credencial, abre **Orchestrators → Credenciales**, introduce el nuevo secreto, guarda y ejecuta **Validar**.

## Cómo funciona

```text
┌──────────────────────────────┐
│ EdgeConnect Orchestrator     │
│ 9.3 · 9.4 · 9.5 · 9.6      │
└──────────────┬───────────────┘
               │ HTTPS / REST API
               ▼
┌──────────────────────────────┐
│ Compatibilidad y detección   │
│ Swagger · versión · métodos  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Normalización                │
│ recursos · métricas · origen │
└──────────────┬───────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
┌─────────────┐ ┌──────────────┐
│ Dashboard   │ │ Inspector API│
│ dinámico    │ │ y evidencia  │
└─────────────┘ └──────────────┘
```

Cada valor normalizado conserva un enlace hacia la muestra API que lo originó. Esto permite abrir una visualización y comprobar la llamada, los datos utilizados y las transformaciones aplicadas.

## Operación y diagnóstico

```bash
# Estado de los servicios
sudo systemctl status dashboardapi-ec dashboardapi-ec-worker

# Logs de la API
sudo journalctl -u dashboardapi-ec -f

# Logs del recolector automático
sudo journalctl -u dashboardapi-ec-worker -f

# Validar Nginx
sudo nginx -t

# Reiniciar la plataforma
sudo systemctl restart dashboardapi-ec dashboardapi-ec-worker nginx
```

Swagger de DashboardAPI-EC:

```text
http://IP-DEL-SERVIDOR/api/v1/docs
```

## Documentación

| Documento | Contenido |
| --- | --- |
| [README técnico](DashboardAPI-EC/README.md) | Arquitectura, APIs, configuración, desarrollo y operación |
| [Instalación y primer uso](DashboardAPI-EC/docs/INSTALLATION.md) | Instalación, actualización, respaldo y diagnóstico |
| [ADR de compatibilidad](DashboardAPI-EC/docs/ADR/ADR-0001-compatibility-layer.md) | Diseño de la capa por versiones |
| [ADR de muestras reales](DashboardAPI-EC/docs/ADR/ADR-0002-real-api-samples.md) | Evidencia, respuestas y trazabilidad |
| [Arquitectura inicial](DashboardAPI-EC/docs/MTDS/MTDS-0.1-Architecture.md) | Componentes y decisiones iniciales |
| [Modelo de datos reales](DashboardAPI-EC/docs/MTDS/MTDS-0.2-Real-Data.md) | Descubrimiento y recolección |

## Seguridad

- Los secretos se cifran antes de guardarse.
- Las credenciales nunca se devuelven mediante la API.
- El inspector elimina contraseñas, tokens, cookies y encabezados sensibles.
- El OTP se utiliza una sola vez y no se persiste.
- El instalador genera una `SECRET_KEY` aleatoria.
- La verificación TLS hacia los Orchestrators está activada de forma predeterminada.
- Para servir el dashboard por HTTPS, carga un certificado desde **Certificado HTTPS** siguiendo la [guía HTTPS](DashboardAPI-EC/docs/HTTPS.md). Nginx redirige HTTP a HTTPS después de activarlo.
- El puerto interno de FastAPI solo escucha en `127.0.0.1`.

El archivo `/etc/dashboardapi-ec/dashboardapi-ec.env` contiene la clave maestra. Debe respaldarse junto con PostgreSQL. Si se pierde o cambia `SECRET_KEY`, las credenciales existentes no podrán descifrarse.

## Licencia

DashboardAPI-EC se distribuye bajo una **licencia de uso restringido**: evaluación, estudio y uso interno. Comercialización, copia fuera de la instalación/respaldo y redistribución requieren autorización escrita. Los derechos de terceros y los permisos de versiones anteriores se conservan. Esta licencia no es MIT.

Consulta el texto completo en [LICENSE](LICENSE).

## Donaciones

```text
╭──────────────────────────────────────────────────────╮
│                                                      │
│              ♥  APOYA DASHBOARDAPI-EC  ♥             │
│                                                      │
│   Si este proyecto te ahorra tiempo o te ayuda a     │
│   mostrar el potencial de las APIs de EdgeConnect,   │
│   considera apoyar su desarrollo y mantenimiento.    │
│                                                      │
│          Donaciones: decameru@outlook.com            │
│                                                      │
╰──────────────────────────────────────────────────────╯
```

Para conocer los medios de donación disponibles, escribe a [decameru@outlook.com](mailto:decameru@outlook.com).

## Contacto

Consultas, soporte, propuestas y donaciones:

**[decameru@outlook.com](mailto:decameru@outlook.com)**
