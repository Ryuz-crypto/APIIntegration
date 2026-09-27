# Acceso de usuarios

DashboardAPI-EC 1.4.0 protege el dashboard y la API con cuentas locales. Las contraseñas se derivan con `scrypt`; los tokens de sesión se guardan únicamente como hashes SHA-256 y vencen después de 12 horas. Cerrar sesión o deshabilitar una cuenta revoca su acceso.

## Crear el primer administrador

Después de instalar, consulta el token generado en el propio servidor:

```bash
sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env
```

Abre el dashboard. La primera pantalla solicita usuario, nombre visible, una contraseña de al menos 12 caracteres y ese token. El alta inicial sólo está disponible mientras no exista ninguna cuenta.

Para no transmitir el token por una red HTTP, configura primero HTTPS o abre un túnel desde tu estación:

```bash
ssh -L 8080:127.0.0.1:80 usuario@IP-DEL-SERVIDOR
```

Después abre `http://127.0.0.1:8080/`. El navegador guarda la sesión sólo en `sessionStorage`; se elimina al cerrar sesión y no se comparte entre pestañas nuevas.

## Roles

| Rol | Permisos |
| --- | --- |
| Consulta | Ver dashboards, inventario, muestras, perfiles y configuración publicada. |
| Operador | Todo lo anterior, además de validar conexiones, completar OTP, descubrir equipos, recolectar datos y guardar snapshots. |
| Administrador | Control total: usuarios, Orchestrators, credenciales, Swagger, Try Me, apariencia, HTTPS y actualizaciones. |

Las reglas se aplican en el backend. Ocultar un botón en el navegador no sustituye la autorización de la API.

## Administrar cuentas

Abre **Acceso** en el menú lateral. Un administrador puede:

- crear cuentas y asignar su rol;
- cambiar roles;
- habilitar o deshabilitar cuentas;
- eliminar cuentas;
- revisar los últimos 200 eventos de auditoría.

La plataforma impide eliminar la propia cuenta activa y deshabilitar, degradar o eliminar al último administrador habilitado.

Cada usuario puede cambiar su contraseña en **Acceso**. Al hacerlo se revocan sus demás sesiones y se conserva la sesión actual.

## Acceso a la API

Inicia sesión y usa el token devuelto como Bearer:

```bash
TOKEN="$(curl -fsS -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"TU-CONTRASEÑA"}' \
  https://dashboard.example/api/v1/auth/login \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"

curl -fsS -H "Authorization: Bearer $TOKEN" \
  https://dashboard.example/api/v1/orchestrators
```

Los endpoints `/api/v1/health`, `/api/v1/auth/status`, `/api/v1/auth/login` y el alta inicial permanecen públicos. La documentación OpenAPI puede consultarse sin sesión, pero las operaciones protegidas requieren el encabezado Bearer.

## Respaldo

Las cuentas y sesiones viven en PostgreSQL. Inclúyelas en el respaldo normal de `dashboardapi_ec`. Conserva también `/etc/dashboardapi-ec/dashboardapi-ec.env`, ya que contiene las claves administrativas y de cifrado.
