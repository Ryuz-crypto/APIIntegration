# Actualizaciones administradas

DashboardAPI-EC incorpora un motor para instalar versiones oficiales desde la interfaz. El botón **Actualizar** está disponible para los administradores.

## Activación inicial

Una instalación 1.0 o 1.1 todavía no contiene el motor. Actualízala una sola vez desde el repositorio:

```bash
cd ~/APIIntegration
git pull --ff-only
cd DashboardAPI-EC
sudo ./scripts/install-ubuntu.sh
```

El instalador conserva la base de datos, las credenciales cifradas, la configuración, los certificados y la apariencia. También habilita `dashboardapi-ec-update.timer`.

## Actualizar desde el dashboard

1. Inicia sesión con una cuenta administradora.
2. Abre **Actualizar**.
3. Pulsa **Buscar versiones en GitHub** y elige una versión posterior.
4. Escribe la confirmación exacta, por ejemplo `ACTUALIZAR v1.5.0-stable`.
5. Pulsa **Aplicar actualización**. La interfaz mostrará `pending`, `running`, `success` o `error` y se recargará cuando la API vuelva a estar disponible.

El canal admite únicamente tags estables oficiales con este formato:

```text
v1.2.0-stable
```

No se permiten ramas, commits arbitrarios, versiones iguales ni retrocesos desde la interfaz.

## Qué hace el motor

La API consulta los tags del repositorio `Ryuz-crypto/APIIntegration`, valida la selección y escribe una solicitud sin privilegios. Un timer de `systemd` la recoge cada 30 segundos. El activador que corre como `root` vuelve a verificar el tag exacto, descarga sólo esa revisión, construye el `.deb` e instala el paquete con `apt`.

Antes de modificar el sistema guarda:

- volcado PostgreSQL en formato personalizado;
- `/etc/dashboardapi-ec`, incluida la clave maestra;
- configuración activa de Nginx y material TLS;
- paquete `.deb` de la versión instalada.

Los respaldos se guardan en `/var/backups/dashboardapi-ec/before-<tag>-<fecha>`. Los paquetes quedan en `/var/lib/dashboardapi-ec-update/packages`. Tras instalar, el motor verifica `/api/v1/health`. Si la instalación o esa verificación falla, intenta reinstalar automáticamente el paquete anterior y conserva el respaldo para una restauración de datos.

## Diagnóstico

```bash
sudo systemctl status dashboardapi-ec-update.timer
sudo systemctl status dashboardapi-ec-update.service
sudo journalctl -u dashboardapi-ec-update.service -n 200 --no-pager
sudo cat /var/lib/dashboardapi-ec-update/status.json
curl http://127.0.0.1:8010/api/v1/health
```

Si GitHub no es accesible, la consulta de versiones falla sin cambiar el servidor. La construcción también requiere salida HTTPS hacia GitHub, PyPI y el registro de npm. Comprueba DNS, las reglas de salida y el proxy corporativo.

## Recuperación manual

Si la recuperación automática no deja el servicio saludable, identifica el paquete anterior y reinstálalo:

```bash
sudo ls -lh /var/lib/dashboardapi-ec-update/packages/
sudo apt install --reinstall --allow-downgrades \
  /var/lib/dashboardapi-ec-update/packages/dashboardapi-ec_VERSION_ARQUITECTURA.deb
sudo systemctl restart dashboardapi-ec dashboardapi-ec-worker nginx
curl http://127.0.0.1:8010/api/v1/health
```

La restauración del volcado PostgreSQL puede descartar datos recientes. Hazla sólo después de guardar el estado actual y revisa el `metadata.json` del respaldo elegido.

## Controles de seguridad

- Sólo una sesión con rol administrador puede programar la actualización.
- La confirmación incluye el tag exacto que se instalará.
- La solicitud contiene únicamente el tag validado y se publica de forma atómica.
- El proceso web no ejecuta `apt`, comandos de shell ni tareas como `root`.
- El activador acepta una lista fija de formatos, repositorio, ejecutables y rutas.
