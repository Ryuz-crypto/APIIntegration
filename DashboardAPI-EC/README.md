# DashboardAPI-EC

Plataforma NOC/SOC para Aruba EdgeConnect con lectura real desde Orchestrator.

Incluye:

- Backend FastAPI con Orchestrators, Appliances, perfiles API, auditoria y muestras API.
- Compatibility Layer obligatorio para resolver operaciones por version.
- Perfiles importados para EdgeConnect 9.3, 9.4, 9.5, 9.6 y 9.7.
- Cliente HTTP real para EdgeConnect.
- Credenciales cifradas con `SECRET_KEY`.
- Validacion real de Orchestrator, discovery real y metricas por Appliance.
- PostgreSQL/TimescaleDB, Redis, worker Celery, frontend React y Nginx.
- Instalador Linux interactivo para operar como aplicativo con Docker Compose.

Los perfiles 9.3-9.6 se generan desde las colecciones Postman de EdgeConnect SD-WAN y el perfil 9.7 desde los modulos Swagger/OpenAPI independientes. El dashboard consume aliases canonicos estables como `orchestrator.version`, `orchestrator.inventory.summary` y `appliance.performance`, aunque la ruta real cambie entre contratos.

## Instalacion rapida como aplicativo

Repositorio:

```bash
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
git branch --show-current
```

La validacion debe responder:

```bash
codex/fase-2-real-data
```

Instalador recomendado:

```bash
bash scripts/install-linux.sh
```

El instalador:

- Instala `git`, `curl`, `openssl`, Docker Engine y Docker Compose plugin desde el repositorio oficial de Docker.
- Valida que existan `git`, `curl`, `openssl`, `docker` y `docker compose`.
- Genera `.env` preguntando puerto HTTP, usuario/password de PostgreSQL, `SECRET_KEY`, CORS y ambiente.
- Ejecuta `docker compose up -d --build`.
- Valida `http://localhost:<puerto>/api/v1/health`.

Al terminar abre:

- UI: `http://localhost:8080` o el puerto que elegiste.
- API: `http://localhost:8080/api/v1`.
- Docs API: `http://localhost:8080/api/v1/docs`.

## Instalacion desde cero por plataforma

### Ubuntu Server

```bash
sudo apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc || true
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
bash scripts/install-linux.sh
```

### Ubuntu Workstation

```bash
sudo apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc || true
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
bash scripts/install-linux.sh
xdg-open http://localhost:8080
```

Si ves `E: No se ha podido localizar el paquete docker-compose-plugin`, significa que aun no agregaste el repositorio oficial de Docker. Repite el bloque completo de Ubuntu desde `sudo apt-get remove -y docker.io ...` hasta `sudo docker compose version`.

### Rocky Linux

```bash
sudo dnf install -y git curl openssl yum-utils
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
bash scripts/install-linux.sh
```

### CentOS Stream

```bash
sudo dnf install -y git curl openssl yum-utils
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
bash scripts/install-linux.sh
```

### CentOS 7/8 legado

```bash
sudo yum install -y git curl openssl yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
git clone -b codex/fase-2-real-data https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
bash scripts/install-linux.sh
```

## Parametros que pide la plataforma

Al agregar un Orchestrator desde la UI se solicitan y validan estos campos:

- `Name`: nombre operativo del Orchestrator.
- `Base URL`: URL real, por ejemplo `https://orchestrator.empresa.local`.
- `API profile`: auto detect o version 9.3, 9.4, 9.5, 9.6, 9.7.
- `Auth`: `None`, `Basic`, `Bearer` o `API Key`.
- `Username` y `Password`: requeridos para `Basic`.
- `Bearer token`: requerido para `Bearer`.
- `API key` y `Header`: requeridos para `API Key`.
- `Verify TLS`: activa/desactiva validacion de certificado.
- `Timeout seconds`: entre 3 y 120 segundos.

El backend rechaza configuraciones incompletas antes de guardarlas.

## Flujo con datos reales

1. Entrar a la UI.
2. Agregar el Orchestrator con los parametros reales.
3. Usar `Validate`; ejecuta `orchestrator.version` y guarda HTTP status, latencia, version detectada y error si aplica.
4. Usar `Discover`; lee inventario real desde `orchestrator.inventory.summary`.
5. Usar `Metrics` en un Appliance; recolecta `appliance.performance`.
6. Revisar `Appliances` para ver el ultimo resumen de metricas.
7. Revisar `Real API Samples` para ver operacion, HTTP status, latencia, endpoint y payload almacenado.

Si un endpoint de Aruba cambia, no se modifica el servicio: se actualiza el perfil de compatibilidad o se genera uno nuevo con Swagger/OpenAPI.

## Checklist de validacion

- `docker compose ps` muestra `postgres`, `redis`, `backend`, `worker`, `frontend` y `nginx`.
- `docker compose version` muestra la version del plugin Compose v2.
- `curl http://localhost:8080/api/v1/health` responde OK.
- `http://localhost:8080` abre la UI.
- `http://localhost:8080/api/v1/docs` abre Swagger.
- En la UI, el checklist del Orchestrator queda en verde antes de guardar.
- `Validate` deja `HTTP 200` o muestra un error real de conexion/autenticacion.
- `Discover` crea Appliances reales.
- `Metrics` muestra valores en la columna `Last metrics`.
- `Real API Samples` registra cada lectura exitosa o fallida.

## Troubleshooting de instalacion

### Timeout descargando paquetes Python

Si durante `docker compose up -d --build` aparece un error como:

```text
HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out
```

vuelve a traer la ultima rama y reconstruye sin cache:

```bash
cd ~/APIIntegration
git pull
cd DashboardAPI-EC
docker compose build --no-cache backend worker
docker compose up -d
```

El Dockerfile no actualiza `pip` durante el build porque eso agrega una descarga innecesaria y puede fallar en redes lentas. La instalacion de dependencias usa timeout de 120 segundos y 10 reintentos.

## Operacion diaria

```bash
cd APIIntegration/DashboardAPI-EC
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
docker compose restart
docker compose down
docker compose up -d --build
```

Para reiniciar desde cero en laboratorio:

```bash
docker compose down -v
bash scripts/install-linux.sh
```

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
