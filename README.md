# APIIntegration — EdgeConnect SD-WAN Platform

[![DashboardAPI-EC](https://img.shields.io/badge/DashboardAPI--EC-1.5.1%20stable-2fbf9b)](DashboardAPI-EC/README.md)
[![ec-mcp](https://img.shields.io/badge/ec--mcp-3.0.0b3%20MCP%20server-7B61FF)](ec-mcp/README.md)
[![DashboardAPI-EC CI](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/dashboardapi-ec.yml)
[![ec-mcp CI](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml/badge.svg)](https://github.com/Ryuz-crypto/APIIntegration/actions/workflows/ec-mcp.yml)
[![Licencia restringida](https://img.shields.io/badge/licencia-uso_restringido-blue.svg)](LICENSE)

Plataforma para descubrir, consultar, visualizar y **conversar** con entornos **HPE Aruba Networking EdgeConnect SD-WAN** mediante sus APIs y su CLI ECOS.

| Componente | Qué hace | Documentación |
| --- | --- | --- |
| **DashboardAPI-EC** | Plataforma web: detecta la versión del Orchestrator, identifica capacidades y ensambla un dashboard con datos reales. Paquete `.deb` para Ubuntu, Python 3.12+. | [DashboardAPI-EC/README.md](DashboardAPI-EC/README.md) |
| **ec-mcp** | Servidor MCP (Model Context Protocol) para asistentes de IA (Claude Desktop, Le Chat, Cursor, ChatGPT): consulta la API REST del Orchestrator, ejecuta comandos `show ...` mediante la API del Orchestrator o SSH opcional, y aplica cambios con dry-run, whitelist y audit log. | [ec-mcp/README.md](ec-mcp/README.md) |

## ec-mcp 3.0 — MCP y panel de administración web

Versión estable en `main`: **3.0.0b3**. Esta versión incorpora configuración web, updater desde GitHub y ejecución de comandos `show` mediante la API del Orchestrator. La referencia exhaustiva está en [ec-mcp/README.md](ec-mcp/README.md) y la plantilla completa en [ec-mcp/.env.example](ec-mcp/.env.example).

> **Regla principal:** `ec-mcp/.env` es la única fuente de configuración. No dupliques las credenciales del Orchestrator en el JSON del cliente MCP ni declares `EC_ADMIN_PORT` o `EC_ADMIN_PASSWORD` directamente en systemd. Cada variable debe aparecer una sola vez en `.env`.

### Instalación limpia en Linux

Requiere Ubuntu/Debian con Python 3.12 o superior:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl

git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
./scripts/install.sh --non-interactive

cp -n .env.example .env
nano .env
```

Configura como mínimo estos valores. No dejes espacios alrededor de `=` ni repitas claves:

```dotenv
# Orchestrator: usa API key o usuario/contraseña.
EC_ORCHESTRATOR_URL=https://TU-ORCHESTRATOR-REAL
EC_ORCHESTRATOR_API_KEY=TU-API-KEY-REAL
EC_ORCHESTRATOR_USER=
EC_ORCHESTRATOR_PASSWORD=
EC_VERIFY_TLS=true

# SSH permanece deshabilitado si sólo usarás el API del Orchestrator.
EC_SSH_ENABLED=false
EC_SSH_USERNAME=
EC_SSH_PASSWORD=
EC_SSH_PRIVATE_KEY=
EC_SSH_PORT=22
EC_SSH_STRICT_HOST_KEY=true
EC_SSH_KNOWN_HOSTS=

# Escrituras deshabilitadas hasta habilitarlas expresamente.
EC_ALLOW_WRITE_TOOLS=false
EC_ALLOW_DANGEROUS_WRITES=false
EC_WRITE_DRY_RUN_DEFAULT=true
EC_WRITE_AUDIT_LOG=/var/log/ec-mcp/write-audit.jsonl

# Transporte MCP remoto. Genera un token aleatorio para producción.
EC_MCP_AUTH_TOKEN=CAMBIA-ESTE-TOKEN
EC_MCP_HOST=0.0.0.0
EC_MCP_PORT=8000
EC_MCP_ALLOWED_HOSTS=mcp.example.com
EC_MCP_JSON_RESPONSE=true
EC_MCP_STATELESS=false

# Panel web administrativo.
EC_ADMIN_HOST=0.0.0.0
EC_ADMIN_PORT=9090
EC_ADMIN_PASSWORD=CAMBIA-ESTA-CONTRASENA
EC_ADMIN_LOGIN_MAX_FAILURES=5
EC_ADMIN_LOGIN_WINDOW_SECONDS=60

# Updater web. Para repositorios privados, configura usuario y token.
EC_UPDATE_ALLOW_WEB=true
EC_UPDATE_REPOSITORY=Ryuz-crypto/APIIntegration
EC_UPDATE_BRANCH=main
EC_UPDATE_GITHUB_USER=
EC_UPDATE_GITHUB_TOKEN=
EC_UPDATE_STATE_DIR=/var/lib/ec-mcp-update
EC_UPDATE_SERVICE_NAME=ec-mcp.service
EC_UPDATE_ADMIN_SERVICE_NAME=ec-mcp-admin.service
```

Genera secretos largos, por ejemplo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

La plantilla contiene variables adicionales de timeouts, caché, API, SSH y updater. Revisa [ec-mcp/.env.example](ec-mcp/.env.example) antes de arrancar.

### Instalar los servicios

```bash
cd ~/APIIntegration/ec-mcp
./scripts/install_service.sh
./scripts/install_admin_service.sh --port 9090

sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
systemctl --no-pager status ec-mcp ec-mcp-admin
sudo ss -lntp | grep -E ':(8000|9090)\b'
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1:9090/login
```

Desde **3.0.0b3**, `install_admin_service.sh` conserva el puerto definido en `.env`; `--port` lo actualiza explícitamente. El panel queda en `http://IP-DEL-SERVIDOR:9090`.

### Configuración del cliente MCP local (stdio)

El cliente sólo necesita la ruta al archivo `.env`. Sustituye `TU-USUARIO` por el usuario Linux real:

```json
{
  "mcpServers": {
    "ec-mcp": {
      "command": "/home/TU-USUARIO/APIIntegration/ec-mcp/.venv/bin/ec-mcp",
      "env": {
        "EC_MCP_ENV_FILE": "/home/TU-USUARIO/APIIntegration/ec-mcp/.env"
      }
    }
  }
}
```

No coloques `EC_ORCHESTRATOR_API_KEY`, contraseñas ni tokens directamente en este JSON.

Para un conector remoto usa `https://TU-HOST/mcp` y el Bearer token definido en `EC_MCP_AUTH_TOKEN`. La publicación TLS/ZTNA/nginx está explicada en [ec-mcp/README.md](ec-mcp/README.md).

### Upgrade por terminal

```bash
cd ~/APIIntegration
git status --short
git pull --ff-only origin main

cd ec-mcp
./scripts/install.sh --non-interactive
./scripts/install_service.sh
./scripts/install_admin_service.sh

sudo systemctl daemon-reload
sudo systemctl restart ec-mcp ec-mcp-admin
./.venv/bin/python -c "import ec_mcp; print(ec_mcp.__version__)"
git rev-parse HEAD
```

Si `git status --short` muestra cambios locales, respáldalos antes del `pull`; no los descartes automáticamente.

### Validación y errores comunes

Comprueba claves duplicadas sin mostrar los secretos:

```bash
cd ~/APIIntegration/ec-mcp
cut -d= -f1 .env | sed 's/^export //' | grep '^EC_' | sort | uniq -d
grep -nE '^(EC_ADMIN_HOST|EC_ADMIN_PORT|EC_ADMIN_LOGIN_MAX_FAILURES|EC_ADMIN_LOGIN_WINDOW_SECONDS)=' .env
sudo systemctl cat ec-mcp-admin
sudo systemctl show ec-mcp-admin -p Environment -p WorkingDirectory --no-pager
```

- Si el primer comando imprime una clave, elimínala hasta dejar una sola definición.
- Si systemd muestra `Environment=EC_ADMIN_PORT=8080`, esa variable prevalece sobre `.env). Reinstala el servicio con el script de 3.0.0b3 o elimina el override.
- Si el puerto correcto abre pero rechaza la contraseña, busca varias líneas `EC_ADMIN_PASSWORD=`; conserva exactamente una y reinicia `ec-mcp-admin`.
- Después de demasiados intentos, espera el valor de `EC_ADMIN_LOGIN_WINDOW_SECONDS` o reinicia el servicio una vez corregida la contraseña.
- `run_show_api(command="show arp", appliance_id="0.NE")` usa el API del Orchestrator. No requiere habilitar SSH ni usar `run_show_command`.

Guía completa de variables, seguridad, updater, HTTP/SSE, systemd y nginx: [ec-mcp/README.md](ec-mcp/README.md).

---

## DashboardAPI-EC

DashboardAPI-EC es una plataforma web para descubrir, consultar y visualizar entornos **HPE Aruba Networking EdgeConnect** mediante sus APIs. Detecta la versión del Orchestrator, identifica las capacidades disponibles y ensambla un dashboard específico con datos reales.

La versión **1.5.1 stable** funciona en **Ubuntu con Python 3.12 o superior** y se distribuye como paquete `.deb`. Se admiten versiones posteriores de Ubuntu siempre que cumplan estos requisitos.

### Contenido

- [Características](#características)
- [Instalación rápida](#instalación-rápida)
- [Actualizar una instalación existente a 1.5.1](#actualizar-una-instalación-existente-a-151)
- [Primer uso](#primer-uso)
- [Varios Orchestrators](#varios-orchestrators)
- [Cómo funciona](#cómo-funciona)
- [Operación y diagnóstico](#operación-y-diagnóstico)
- [HTTPS y apariencia](#https-y-apariencia)
- [Validación](#validación)
- [Documentación](#documentación)
- [Seguridad](#seguridad)
- [Licencia](#licencia)
- [Donaciones](#donaciones)
- [Contacto](#contacto)

## Características

- Asistente visual para conectar Orchestrator on-premises y Orchestrator as a Service.
- Autenticación en dos fases: usuario/contraseña, espera del OTP y descubrimiento con la misma sesión. Consulta la [guía de autenticación](DashboardAPI-EC/docs/AUTHENTICATION.md).
- Compatibilidad controlada con EdgeConnect 9.3, 9.4, 9.5 y 9.6; Orchestrator 9.7.x (incluida 9.7.1.42046) utiliza el perfil API 9.6.
- Importación de contratos OpenAPI 3 y Swagger 2.
- Importación de Postman Collection 2.0/2.1, incluidas carpetas, variables, parámetros y cuerpos JSON.
- Detección automática de versión, capacidades, appliances y sitios.
- Dashboard dinámico construido según las APIs disponibles en cada entorno.
- Canal WebSocket autenticado con reconexión automática y actualizaciones sin recargar la página.
- Correlación por sitio y equipo de rendimiento, salud, interfaces, túneles, latencia y errores API.
- Inspector que muestra la operación, método, ruta, parámetros, latencia, valores extraídos y JSON sanitizado.
- Ejemplos reproducibles en cURL, Python y JavaScript.
- Credenciales independientes y cifradas para múltiples Orchestrators.
- Rotación de API keys y contraseñas desde la interfaz.
- Inicio de sesión local, sesiones revocables y roles de consulta, operador y administrador.
- Polling automático de inventario y rendimiento mediante Celery.
- Recolección por `nePk` de rendimiento, interfaces y túneles con evidencia independiente por API.
- HTTPS administrado desde la interfaz con certificados PEM, DER o PFX/P12.
- Actualización de versiones estables oficiales desde el dashboard, con respaldo, verificación de salud y recuperación del paquete anterior.
- Pestaña Try Me para ejecutar todas las APIs del Swagger, exportar salidas y guardar snapshots.
- Editor global de nombre, mensaje, seis colores, icono y tipografía.
- Backend FastAPI, frontend React, PostgreSQL, Redis y Nginx.
- Instalación nativa con paquete `.deb` y servicios `systemd`.

## Instalación rápida

Requisitos mínimos:

- Ubuntu con Python 3.12 o superior, `amd64` o `arm64`.
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
3. construye el paquete `dashboardapi-ec_1.5.1_<arquitectura>.deb`;
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

### Actualizar una instalación existente a 1.5.1

Si ya tienes 1.2, 1.3, 1.4.0, 1.4.1 o un intento fallido de 1.5.0, abre **Actualizar**, pulsa **Buscar versiones en GitHub**, elige `v1.5.1-stable` y escribe la confirmación exacta. Las conexiones, credenciales, certificados, apariencia y muestras existentes se conservan.

Si vienes de 1.0 o 1.1, o el motor no puede consultar GitHub, actualiza una vez desde la terminal:

```bash
cd ~/APIIntegration
git switch main
git pull --ff-only
cd DashboardAPI-EC
sudo ./scripts/install-ubuntu.sh
```

La instalación y las actualizaciones son nativas en Ubuntu mediante `.deb` y `systemd`; no requieren Vagrant ni una máquina virtual.

## HTTPS y apariencia

En la cabecera del dashboard encontrarás tres apartados administrativos:

- **Certificado HTTPS** acepta PEM, DER y PFX/P12, valida SAN, vigencia y correspondencia de la clave, y aplica la configuración de Nginx mediante el servicio privilegiado de Ubuntu. La rutina completa está documentada en [HTTPS.md](DashboardAPI-EC/docs/HTTPS.md).
- **Apariencia** permite cambiar el nombre y mensaje del panel, seis colores, cinco familias tipográficas y cuatro iconos. La configuración se guarda en PostgreSQL y se aplica globalmente. El crédito **Powered by Emilio Abundis** permanece visible.
- **Actualizar** consulta tags estables oficiales en GitHub, solicita únicamente la confirmación exacta, crea un respaldo e instala el `.deb` mediante un activador aislado de `systemd`. Consulta [UPDATES.md](DashboardAPI-EC/docs/UPDATES.md).

Para activar HTTPS, selecciona el certificado y su clave, indica el DNS o IP y pulsa **Validar y activar HTTPS**. La plataforma valida SAN, vigencia y correspondencia de la clave antes de aplicar Nginx.

## Validación

El distintivo **Human Tested** indica que el flujo de conexión, autenticación OTP, detección del Orchestrator **9.7.1.42046** y selección del perfil API 9.6 fue comprobado manualmente en una instalación real. Las pruebas automatizadas validan adicionalmente backend, frontend, migraciones, creación e instalación del `.deb`, actualización y activación HTTPS en Ubuntu. No implica certificación de HPE ni garantiza permisos específicos de cada cuenta.

## Primer uso

1. Abre la dirección mostrada por el instalador.
2. En el servidor, consulta `TLS_ADMIN_TOKEN` con `sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env`.
3. Crea la primera cuenta administradora desde la pantalla de acceso.
4. Pulsa **Conectar Orchestrator**.
5. Selecciona **Orchestrator as a Service** u **On-premises**.
6. Introduce un nombre, la URL HTTPS y la credencial del Orchestrator.
7. Mantén activa la verificación TLS y pulsa **Conectar y detectar**.

La plataforma validará el acceso, detectará la versión, cargará el perfil compatible, descubrirá los appliances y construirá el dashboard.

Para OaaS se recomienda una API key dedicada con permisos de solo lectura. Las sesiones con OTP se pueden validar de forma interactiva, pero no participan en el polling automático porque el código de un solo uso nunca se almacena.

El menú **Acceso** permite crear usuarios, asignar roles, deshabilitar cuentas, cambiar la contraseña y revisar auditoría. Consulta la [guía de acceso](DashboardAPI-EC/docs/ACCESS.md).

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
| [Acceso de usuarios](DashboardAPI-EC/docs/ACCESS.md) | Administrador inicial, roles, sesiones y auditoría |
| [Actualizaciones administradas](DashboardAPI-EC/docs/UPDATES.md) | Canal oficial, respaldos, recuperación y diagnóstico |
| [Try Me y snapshots](DashboardAPI-EC/docs/TRYME.md) | Swagger completo, ejecución interactiva, cambios y exportaciones |
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
