# Certificado HTTPS del dashboard

La instalación `.deb` en Ubuntu permite cargar un certificado desde **Certificado
HTTPS** en la cabecera. La rutina toma como referencia las validaciones de
`WAN_SIM/installer/security.sh`: PEM, DER y PFX/P12, vigencia y correspondencia
de la clave. Aquí se añade carga web, validación SAN y activación de Nginx.
No cambia los certificados ni la autenticación de los Orchestrators.

## Preparar el servidor

Instala o actualiza con `sudo ./scripts/install-ubuntu.sh` desde `DashboardAPI-EC`.
Apunta el DNS del dashboard a la IP del servidor y permite TCP 443 desde la red
administrativa. El puerto 80 redirigirá después de activar HTTPS. Si utilizas UFW,
autoriza 443 con una regla apropiada para tu red antes de continuar.

Solicita a tu CA un certificado de servidor con el DNS o IP en **Subject Alternative
Name (SAN)**. Debe estar vigente y conservar más de 24 horas de validez.

| Formato | Archivo de certificado | Archivo de clave |
| --- | --- | --- |
| PEM | Certificado del servidor primero, seguido de intermedios | Clave PEM, cifrada o sin cifrar |
| DER | Certificado binario del servidor | Clave privada DER |
| PFX/P12 | Paquete con certificado, clave e intermedios | Dejar vacío |

Máximo 256 KiB por archivo. Introduce la contraseña si el archivo está cifrado.
Para cadenas con intermedios, prefiere PEM completo o PFX. La comprobación local
no garantiza que tu navegador confíe en la CA: instala la CA corporativa en los
clientes si corresponde. No se emiten ni renuevan certificados automáticamente.

## Primera carga segura

En el servidor, consulta exclusivamente la clave de administración HTTPS:

```bash
sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env
```

Es una credencial administrativa: no la compartas ni la publiques. Es distinta
de `SECRET_KEY` y no se almacena en el navegador de manera persistente.

Desde tu computadora abre este túnel y deja la terminal abierta:

```bash
ssh -L 8080:127.0.0.1:8081 usuario@IP_DEL_SERVIDOR
```

Abre **http://localhost:8080**, pulsa **Certificado HTTPS** y completa:

1. Clave de administración HTTPS.
2. DNS o IP real del dashboard cubierto por el certificado, sin protocolo ni ruta.
3. Certificado y clave, o solo el paquete PFX/P12.
4. Contraseña del archivo, cuando corresponda.

Pulsa **Cargar y activar HTTPS**. El panel muestra primero la validación y luego
el resultado de Nginx, normalmente en unos 15 segundos. Cuando indique **HTTPS
activo**, abre `https://TU_DNS` y comprueba que el navegador confía en el certificado.
Puedes cerrar el túnel. El panel y la API bloquean la carga por HTTP remoto.
El puerto de preparación 8081 escucha únicamente en `127.0.0.1` y permanece
disponible por SSH para recuperación.

## Renovar o cambiar el certificado

Entra mediante el HTTPS vigente, abre el mismo panel y carga el certificado nuevo.
Para cambiar de PEM a PFX, cierra y vuelve a abrir el diálogo para vaciar los archivos.
Si el certificado ya venció o no puedes acceder mediante su DNS, utiliza el túnel
SSH. **Consultar estado** funciona después de volver a introducir la clave.
Las actualizaciones del paquete conservan la configuración y los certificados activos.

## Funcionamiento y almacenamiento

- FastAPI valida y normaliza los archivos, sin ejecutar comandos privilegiados.
- `dashboardapi-ec-tls.timer` comprueba cada 15 segundos si hay una solicitud.
- `dashboardapi-ec-tls.service` vuelve a validar el material, instala los archivos,
  ejecuta `nginx -t` y recarga Nginx. Antes de marcarlo activo, comprueba en el
  servidor el certificado servido y la redirección HTTP. Si falla, restaura la configuración anterior.
- HTTP redirige con 308 al DNS/IP configurado. HTTPS admite TLS 1.2 y 1.3.
- El certificado está en `/etc/dashboardapi-ec/tls/fullchain.pem` y la clave
  normalizada sin contraseña en `/etc/dashboardapi-ec/tls/privkey.pem`, accesibles
  solo por root (archivos 0600; directorio 0700). Nginx necesita esa clave para iniciar.
- La solicitud temporal está en `/var/lib/dashboardapi-ec-tls/request.json`, con
  permisos 0600, y se elimina después del intento. El estado no contiene la clave.
- La contraseña del archivo no se persiste ni aparece en las respuestas de la API.

API: `POST /api/v1/system/tls` (multipart: `hostname`, `certificate`, `key` opcional,
`password` opcional) y `GET /api/v1/system/tls`. Ambas requieren `X-TLS-Admin-Token`.
Respuestas: 202 pendiente, 400 material/canal inválido, 403 clave administrativa
incorrecta, 409 solicitud pendiente, 503 instalación no habilitada. Estas rutas
no se incluyen en el inspector de llamadas de Orchestrators.

La activación automática depende de systemd/Nginx del paquete Ubuntu. En desarrollo
y Docker permanece deshabilitada (`TLS_ENABLED=false`); configura allí tu propio proxy.
La clave de administración protege estas operaciones; no sustituye controles de
acceso al resto del dashboard. Mantén el servicio en una red administrativa.

## Diagnóstico y recuperación

```bash
sudo systemctl status dashboardapi-ec-tls.timer dashboardapi-ec-tls.service
sudo nginx -t
sudo journalctl -u dashboardapi-ec-tls.service -n 50 --no-pager
sudo cat /var/lib/dashboardapi-ec-tls/status.json
```

Si sigue pendiente, comprueba el timer y ejecuta
`sudo systemctl start dashboardapi-ec-tls.service`. Si hay error, revisa que los
puertos 443 y 8081 estén libres y que no existan otros sitios `default_server`.
La activación gestiona el sitio `dashboardapi-ec` completo; respalda personalizaciones
de Nginx antes de utilizarla. Los errores del formulario no alteran el certificado
activo. Ante un error de activación, corrige el problema y vuelve a cargar.

Para respaldar HTTPS, guarda con acceso restringido `/etc/dashboardapi-ec/tls`,
`/etc/nginx/sites-available/dashboardapi-ec` y el archivo de entorno, además de
PostgreSQL. Al restaurar, conserva propiedad root, permisos 0700/0600 para TLS,
ejecuta `sudo nginx -t` y solo entonces `sudo systemctl reload nginx`.

Para rotar la clave de administración, cambia `TLS_ADMIN_TOKEN` en el archivo de
entorno por un valor aleatorio de al menos 32 bytes y reinicia `dashboardapi-ec`.
No cambies `SECRET_KEY`, que cifra las credenciales de los Orchestrators.
