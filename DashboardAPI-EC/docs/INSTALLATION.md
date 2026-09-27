# Instalación y primer uso

DashboardAPI-EC 1.5.0 stable se instala en Ubuntu. El método recomendado construye un paquete `.deb`, lo instala y configura PostgreSQL, Redis, Nginx, la API, el recolector y el motor de actualización.

## Requisitos

- Ubuntu `amd64` o `arm64`, con Python 3.12 o superior. Ubuntu 20.04 incluye Python 3.8 y Ubuntu 22.04 Python 3.10; no son compatibles con DashboardAPI-EC 1.0 usando su Python predeterminado. Ubuntu 24.04 y versiones posteriores están admitidas.
- 4 GB de RAM como mínimo y 8 GB recomendados.
- 10 GB libres.
- Acceso HTTPS desde el servidor hacia cada EdgeConnect Orchestrator.
- Usuario con privilegios `sudo`.

## Instalación sencilla desde GitHub

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/DashboardAPI-EC
sudo ./scripts/install-ubuntu.sh
```

El instalador comprueba Ubuntu y Python 3.12 o superior antes de instalar paquetes
o construir el `.deb`. Las versiones posteriores de Ubuntu están permitidas. Si
tu Python es anterior a 3.12, actualízalo junto con la distribución o utiliza un
host Ubuntu con Python 3.12 o posterior.

El instalador muestra la URL al terminar. Normalmente será:

```text
http://IP-DEL-SERVIDOR/
```

Comprueba el estado con:

```bash
curl http://127.0.0.1/api/v1/health
sudo systemctl status dashboardapi-ec dashboardapi-ec-worker nginx
```

## Instalación de un paquete ya construido

Si recibiste `dashboardapi-ec_1.5.0_amd64.deb` o la variante `arm64`:

```bash
sudo apt install ./dashboardapi-ec_1.5.0_amd64.deb
```

Las actualizaciones usan el mismo comando con el paquete nuevo. Las migraciones se ejecutan automáticamente y conservan conexiones, credenciales y muestras.

La primera actualización desde 1.0 o 1.1 se hace manualmente con ese comando o con `sudo ./scripts/install-ubuntu.sh`. Una vez instalada la versión 1.2, usa **Actualizar** en el dashboard. Consulta [UPDATES.md](UPDATES.md) para conocer la validación de versiones, respaldos y recuperación.

## Primer acceso y primera conexión

1. Abre la URL del servidor.
2. Consulta `TLS_ADMIN_TOKEN` localmente:

   ```bash
   sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env
   ```

3. Crea el administrador inicial con una contraseña de al menos 12 caracteres.
4. Pulsa **Conectar Orchestrator**.
5. Selecciona **Orchestrator as a Service** u **On-premises**.
6. Asigna un nombre claro e introduce la URL HTTPS del Orchestrator.
7. Escribe una etiqueta, selecciona el método de autenticación e introduce el secreto.
8. Mantén la verificación TLS activada y pulsa **Conectar y detectar**.

La plataforma valida la autenticación, detecta la versión, selecciona el contrato API, descubre los equipos y construye el dashboard adecuado.

La [guía de acceso](ACCESS.md) explica los roles, la administración de cuentas, el cambio de contraseña y el uso de tokens Bearer para automatización.

## Actualizar desde el dashboard

La versión 1.5.0 incluye el motor de actualización. Entra con una cuenta administradora, abre **Actualizar**, pulsa **Buscar versiones en GitHub**, selecciona un tag estable posterior y escribe la confirmación exacta mostrada por la interfaz. El sistema crea un respaldo, instala el nuevo `.deb`, ejecuta migraciones y comprueba la salud del servicio. Si falla, intenta reinstalar el paquete anterior.

No necesitas Vagrant, Docker ni una máquina virtual para instalar o actualizar. El flujo soportado usa Ubuntu, el paquete `.deb` y servicios `systemd`. Consulta [UPDATES.md](UPDATES.md) para diagnóstico y recuperación.

Después de actualizar desde 1.0, ejecuta nuevamente **Descubrir** en cada Orchestrator. Esto llena el campo `nePk`, obligatorio para consultar rendimiento, interfaces y túneles. El recolector ya no utiliza MAC, serial ni hostname como sustitutos.

## HTTPS y apariencia

Usa **Certificado HTTPS** en la cabecera para cargar PEM, DER o PFX/P12. Selecciona los archivos, indica el DNS o IP y pulsa **Validar y activar HTTPS**. El panel valida el certificado antes de entregarlo al activador de Nginx.

Usa **Apariencia** para elegir nombre, mensaje, seis colores, icono y tipografía. El cambio se guarda en PostgreSQL y se conserva al actualizar el paquete. **Powered by Emilio Abundis** permanece visible como atribución del proyecto.

## Try Me y Swagger completo

Después de validar el primer Orchestrator abre **Try Me**. La plataforma intentará utilizar el Swagger almacenado para su versión. Pulsa **Traer del Orchestrator** para sincronizar el documento publicado por el entorno o **Importar Swagger** para cargar JSON/YAML manualmente. La guía [TRYME.md](TRYME.md) explica operaciones de lectura y cambio, exportaciones JSON/CSV y snapshots persistentes.

## Varios Orchestrators y credenciales

Puedes repetir **Conectar Orchestrator** para todos los entornos necesarios. Cada conexión conserva independientemente:

- URL, tenant y tipo de despliegue;
- método de autenticación;
- usuario, contraseña o API key cifrada;
- etiqueta descriptiva de la credencial;
- versión, capacidades y plan de recolección.

Los secretos se cifran antes de almacenarse y nunca se devuelven por la API ni se muestran en el inspector. La clave maestra reside en:

```text
/etc/dashboardapi-ec/dashboardapi-ec.env
```

Para rotar una credencial, abre **Orchestrators → Credenciales**, introduce el nuevo secreto, guarda y ejecuta **Validar**. Dejar el secreto vacío conserva el actual. Un cambio queda registrado en la auditoría sin guardar el valor del secreto.

Las API keys permiten recolección desatendida. Una sesión con OTP requiere un código nuevo y no se agenda automáticamente, porque el OTP nunca se almacena.

## Recolección automática

El servicio `dashboardapi-ec-worker` revisa cada minuto qué conexiones deben actualizarse. Los appliances recién descubiertos quedan habilitados para monitoreo. El interruptor **Auto** permite activar o detener un equipo concreto.

Ver actividad:

```bash
sudo journalctl -u dashboardapi-ec-worker -f
```

## Copia de seguridad

Debes respaldar la base y el archivo de entorno juntos. Sin `SECRET_KEY` no es posible descifrar las credenciales guardadas.

```bash
sudo -u postgres pg_dump dashboardapi_ec | gzip > dashboardapi_ec.sql.gz
sudo install -m 600 /etc/dashboardapi-ec/dashboardapi-ec.env ./dashboardapi-ec.env.backup
```

Restauración:

```bash
gunzip -c dashboardapi_ec.sql.gz | sudo -u postgres psql dashboardapi_ec
sudo install -o root -g dashboardapi -m 640 dashboardapi-ec.env.backup \
  /etc/dashboardapi-ec/dashboardapi-ec.env
sudo systemctl restart dashboardapi-ec dashboardapi-ec-worker
```

## Activar HTTPS con tu certificado

Abre **Certificado HTTPS** en la cabecera del dashboard. La [guía HTTPS](HTTPS.md)
explica cómo subir PEM/DER o PFX/P12, proteger la primera carga mediante SSH,
renovar el certificado y respaldar la configuración. Al activarlo, Nginx sirve
el dashboard en el puerto 443 y redirige las peticiones HTTP a HTTPS.

## Diagnóstico rápido

Si APT muestra `La descarga se realiza sin aislamiento como root ... _apt ...
Permission denied` al instalar un `.deb` ubicado dentro de tu directorio personal,
es un aviso de acceso al archivo local, no un fallo de conexión al Orchestrator.
El instalador actualizado copia temporalmente el paquete a `/var/tmp` con permisos
de lectura para `_apt` y elimina esa copia al terminar, sin cambiar permisos de tu home.
Si el instalador imprimió `quedó instalado` después de verificar servicios, ese aviso
no impidió la instalación.

Para OTP y errores 404 durante el descubrimiento consulta la [guía de autenticación](AUTHENTICATION.md).

```bash
sudo nginx -t
sudo systemctl status postgresql redis-server nginx
sudo systemctl status dashboardapi-ec dashboardapi-ec-worker
sudo journalctl -u dashboardapi-ec -n 100 --no-pager
sudo journalctl -u dashboardapi-ec-worker -n 100 --no-pager
```

Si una conexión falla, comprueba desde el servidor:

```bash
curl -v https://ORCHESTRATOR/
```

Cuando el certificado pertenezca a una CA interna, instala esa CA en Ubuntu. No desactives TLS en producción.
