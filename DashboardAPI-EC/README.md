# DashboardAPI-EC

Primera fase en código para una plataforma NOC/SOC de Aruba EdgeConnect.

Esta fase deja una base instalable y modular:

- Backend FastAPI con modelos para Orchestrators, Appliances, perfiles API y auditoría.
- Compatibility Layer obligatorio para resolver operaciones por versión.
- Perfiles iniciales para EdgeConnect 9.3, 9.4, 9.5 y 9.6.
- Swagger Loader base para generar perfiles sin cambiar código.
- Workers Celery preparados para polling.
- PostgreSQL con TimescaleDB y Redis.
- Frontend React, TypeScript y Material UI en dark theme.
- Nginx como punto de entrada.
- Documentos MTDS y ADR para guiar las siguientes fases.
- Fase 2: cliente HTTP real para EdgeConnect, credenciales cifradas, discovery real y muestras API persistidas.

---

## 📥 Instalación desde 0 (Linux Workstation)

### Requisitos previos
- **Sistema operativo**: Ubuntu 22.04 LTS (o cualquier distribución Linux moderna).
- **Permisos**: Usuario con `sudo` o root.
- **Conexión a Internet**: Para descargar dependencias.

---

### 1️⃣ Instalar Docker y Docker Compose

Abre una terminal y ejecuta:

```bash
# Actualizar paquetes del sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias necesarias
sudo apt install -y ca-certificates curl gnupg

# Añadir la clave GPG de Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Añadir el repositorio de Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verificar instalación
docker --version
docker compose version
```

> ⚠️ **Nota**: Si usas otra distribución (ej. Debian, Fedora), consulta la [documentación oficial de Docker](https://docs.docker.com/engine/install/).

---

### 2️⃣ Clonar el repositorio y cambiar a la rama con los fixes

```bash
# Clonar el proyecto
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC

# Cambiar a la rama con los fixes para Docker y pip
git checkout vibe/fix-docker-pip-errors-e158a5
```

---

### 3️⃣ Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar el archivo .env (opcional)
# Puedes modificar contraseñas o puertos si es necesario:
nano .env
```

> 🔹 **Variables importantes en `.env`**:
> - `POSTGRES_USER`: Usuario de PostgreSQL (default: `edgeconnect`).
> - `POSTGRES_PASSWORD`: Contraseña de PostgreSQL (default: `edgeconnect`).
> - `POSTGRES_DB`: Base de datos (default: `edgeconnect`).

---

### 4️⃣ Construir y levantar la plataforma

```bash
# Construir imágenes (IMPORTANTE: Usar --no-cache para aplicar los fixes)
docker compose build --no-cache

# Levantar todos los servicios
docker compose up -d
```

> ⏳ **Tiempo estimado**: 
> - Primera construcción: ~10-15 minutos (depende de tu conexión a Internet).
> - Inicios posteriores: ~1-2 minutos (gracias a la caché).

> ⚠️ **Nota**: Si ves errores de timeout al instalar dependencias de Python (ej. `ReadTimeoutError`), **ejecuta el comando de construcción con `--no-cache`** para forzar la descarga de todos los paquetes desde cero. Esta rama usa un espejo de PyPI (Tsinghua) y un timeout de 120 segundos para evitar estos errores.

---

### 5️⃣ Verificar que todo funciona

```bash
# Ver estado de los contenedores
docker compose ps
```

Deberías ver algo como:
```
NAME                COMMAND                  SERVICE     STATUS              PORTS
backend-1           "uvicorn app.main:app…"   backend    running             0.0.0.0:8000->8000/tcp
frontend-1          "docker-entrypoint.s…"   frontend   running             0.0.0.0:8080->80/tcp
nginx-1             "nginx -g 'daemon of…"   nginx      running             0.0.0.0:8080->80/tcp
postgres-1          "docker-entrypoint.s…"   postgres   running (healthy)   0.0.0.0:5432->5432/tcp
redis-1             "docker-entrypoint.s…"   redis      running (healthy)   0.0.0.0:6379->6379/tcp
worker-1            "celery -A app.worker…"   worker     running
```

---

### 6️⃣ Acceder a la plataforma

Abre tu navegador y ve a:

- **🌐 UI (Interfaz de usuario)**: [http://localhost:8080](http://localhost:8080)
- **📡 API (Backend)**: [http://localhost:8080/api/v1](http://localhost:8080/api/v1)
- **📖 Documentación API (Swagger)**: [http://localhost:8080/api/v1/docs](http://localhost:8080/api/v1/docs)

---

## 🛑 Detener la plataforma

```bash
# Detener todos los contenedores
docker compose down

# Detener y eliminar volúmenes (⚠️ Borra los datos de PostgreSQL)
docker compose down -v
```

---

## 🔄 Actualizar la plataforma

Si hay cambios en el código:

```bash
# Descargar los últimos cambios
git pull

# Reconstruir imágenes (sin caché para asegurar actualizaciones)
docker compose build --no-cache

# Reiniciar servicios
docker compose up -d
```

---

## 🐛 Solución de problemas

### Error: "ReadTimeoutError" o "Connection reset by peer" al instalar dependencias
Si ves errores como:
```
WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=60.0)")'
```
**Soluciones**:

#### 1️⃣ Usar un espejo de PyPI más rápido
Esta rama ya usa el espejo de **Tsinghua** (`https://pypi.tuna.tsinghua.edu.cn/simple`), pero si prefieres otro espejo (ej. Aliyun), modifica el `Dockerfile`:
```dockerfile
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

#### 2️⃣ Aumentar el timeout manualmente
Si el espejo de Tsinghua sigue siendo lento, puedes aumentar el timeout en el `Dockerfile`:
```dockerfile
ENV PIP_DEFAULT_TIMEOUT=300  # 5 minutos
```

#### 3️⃣ Reconstruir con `--no-cache`
```bash
docker compose build --no-cache
```

#### 4️⃣ Verificar la conexión a Internet
```bash
# Probar conexión a PyPI
curl -v https://pypi.tuna.tsinghua.edu.cn/simple/

# Probar descarga de un paquete
curl -v https://pypi.tuna.tsinghua.edu.cn/packages/5d/95/6b5cb3461ea5673ba0995989746db58eb18b91b54dbf331e72f569540946/pip-26.1.2-py3-none-any.whl
```

#### 5️⃣ Usar una VPN o proxy
Si tu red tiene restricciones, prueba con una VPN o configura un proxy:
```bash
# Exportar variables de proxy (ejemplo)
export HTTP_PROXY=http://tu-proxy:8080
export HTTPS_PROXY=http://tu-proxy:8080

# Reconstruir con proxy
docker compose build --no-cache
```

### Error: "Port already in use"
Si el puerto `8080` o `5432` ya está en uso:
```bash
# Ver qué proceso usa el puerto (ejemplo para 8080)
sudo lsof -i :8080

# Matar el proceso (reemplaza PID con el número del proceso)
kill -9 PID
```

### Error: "Permission denied" al ejecutar Docker
Si ves errores de permiso:
```bash
# Añadir tu usuario al grupo docker
sudo usermod -aG docker $USER

# Reiniciar la sesión (cierra y vuelve a abrir la terminal)
newgrp docker
```

### Error: "Max retries exceeded" en el worker
Si el `worker` falla al instalar dependencias:
1. **Elimina los contenedores y volúmenes**:
   ```bash
   docker compose down -v
   ```
2. **Reconstruye todo desde cero**:
   ```bash
   docker compose build --no-cache
   docker compose up -d
   ```

---

## 🌍 Espejos de PyPI alternativos
Si el espejo de Tsinghua no funciona bien en tu región, prueba con uno de estos:

| **Espejo** | **URL** | **Región** |
|------------|---------|------------|
| Tsinghua | `https://pypi.tuna.tsinghua.edu.cn/simple` | China |
| Aliyun | `https://mirrors.aliyun.com/pypi/simple/` | China |
| Douban | `https://pypi.doubanio.com/simple/` | China |
| Huawei | `https://repo.huaweicloud.com/repository/pypi/simple/` | China |
| Azure (China) | `https://mirror.azure.cn/pypi/simple/` | China |

Para cambiar el espejo, modifica el `Dockerfile`:
```dockerfile
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

---

## 📂 Flujo con datos reales

1. Entrar a la UI en [http://localhost:8080](http://localhost:8080).
2. Agregar un **Orchestrator** con:
   - URL real de tu instancia de EdgeConnect.
   - Tipo de autenticación.
   - Credenciales.
3. Usar **`Validate`** para ejecutar una llamada real a `orchestrator.version`.
4. Usar **`Discover`** para leer inventario real desde `orchestrator.inventory.summary`.
5. Usar **`Metrics`** en un Appliance para recolectar `appliance.performance`.
6. Revisar **`Real API Samples`** para ver:
   - HTTP status.
   - Latencia.
   - Operación.
   - Payload almacenado.

> 🔹 **Nota**: Si un endpoint de Aruba cambia, **no se modifica el servicio**. Solo actualiza el perfil de compatibilidad o genera uno nuevo con Swagger/OpenAPI.

---

## 🏗️ Principios de fase 1

- Ningún servicio llamará endpoints de EdgeConnect directamente.
- Toda operación se resuelve por `backend/app/compatibility`.
- La configuración operativa se modela para ser administrada desde la UI.
- El backend separa **Orchestrator** y **Appliance**.
- Secretos se reciben por API, se enmascaran en respuestas y quedan preparados para cifrado.
- La fase 2 guarda secretos cifrados con `SECRET_KEY`. **Cambiar ese valor invalida secretos ya cifrados**.

---

## 📁 Estructura del proyecto

```text
DashboardAPI-EC/
├── backend/          # Backend en FastAPI
├── frontend/         # Frontend en React + TypeScript
├── infrastructure/   # Configuraciones de infraestructura (Nginx)
├── docs/             # Documentación técnica
├── scripts/          # Scripts de apoyo
└── docker-compose.yml # Configuración de Docker
```
