# Conexión al Orchestrator y espera del OTP

En **Conectar Orchestrator**, introduce la URL de tu instancia (host o URL que
termine en `/gms/rest`). Para usuario, contraseña y código de tu aplicación,
selecciona **Sesión interactiva con OTP**. No introduzcas el OTP anticipadamente.

1. Completa usuario, contraseña, proveedor y verificación TLS.
2. Pulsa **Autenticar usuario y contraseña**. El backend envía las credenciales a
   `POST /gms/rest/authentication/loginToken` con `TempCode: false`.
3. El asistente queda en **Esperando tu código OTP**, durante un máximo de cinco
   minutos. En este punto todavía no consulta versión ni inventario.
4. Introduce el código vigente de tu aplicación y pulsa **Validar OTP y detectar**.
   El backend completa `POST /gms/rest/authentication/login` y conserva las cookies
   y el encabezado CSRF para las consultas siguientes.
5. Consulta la versión mediante `GET /gms/rest/gmsserver/briefInfo` y el inventario
   mediante `GET /gms/rest/appliance`, sin volver a iniciar sesión ni reutilizar el OTP.

Si el código es rechazado, la espera caduca o se cambian las credenciales, inicia
la autenticación de nuevo. El sistema no reintenta códigos automáticamente.
**Cancelar** elimina la espera pendiente. Los reintentos dentro del mismo asistente
reutilizan la conexión creada; cambiar la URL configura un destino nuevo.

El OTP se borra del formulario después de enviarlo y no se guarda en base de datos,
Redis, auditoría ni muestras de API. Solo se conservan cookies cifradas en Redis:
cinco minutos para la espera y treinta minutos para la sesión autenticada. El estado
es compartido por los procesos de la API y queda vinculado al Orchestrator y sus
credenciales. La sesión remota puede vencer antes; en ese caso hay que autenticar
de nuevo. No se hace polling automático de conexiones que requieren OTP. Para una
operación continua, utiliza una API key con los permisos necesarios de solo lectura.

El flujo implementa los endpoints REST de Orchestrator, no un inicio de sesión
SAML/OAuth en un proveedor externo. Que la instancia sea aaS no garantiza que su
proveedor de identidad permita usuario/contraseña por esos endpoints; si requiere
SSO externo, usa una API key creada en esa instancia.

## Entender un 404

Un 404 significa que un servidor HTTP respondió, pero no encontró la ruta solicitada.
No confirma que las credenciales o el OTP hayan sido aceptados. Ahora el error
muestra el método y la ruta exacta para distinguir autenticación, versión e inventario.

- `POST /gms/rest/authentication/loginToken`: verifica que la URL sea la instancia
  del Orchestrator, no el portal general de acceso, y que exponga este método REST.
- `POST /gms/rest/authentication/login`: revisa la misma URL y el método de acceso.
- `GET /gms/rest/gmsserver/briefInfo`: revisa versión instalada y perfil Swagger.
- `GET /gms/rest/appliance`: revisa permisos de inventario/API del usuario.

Los perfiles integrados 9.3–9.6 se corrigieron: consultaban `/gms/rest/version`, una
ruta que no corresponde a la consulta de versión documentada. Al reinstalar se
actualizan los perfiles integrados; los Swagger importados por el usuario se conservan.

## API del asistente

| Operación del dashboard | Función |
| --- | --- |
| `POST /api/v1/orchestrators/{id}/auth/start` | Envía credenciales y devuelve `challenge_id` y `expires_in` |
| `POST /api/v1/orchestrators/{id}/auth/complete` | Recibe `challenge_id` y `otp`; valida sesión y versión |
| `POST /api/v1/orchestrators/{id}/auth/cancel` | Recibe `challenge_id` y elimina la espera |

El identificador de espera solo puede consumirse una vez. Un OTP requiere una
espera válida; `/validate` no sustituye este intercambio.

Referencias oficiales utilizadas para los endpoints y campos:

- [HPE: login y loginToken](https://github.com/aruba/pyedgeconnect/blob/main/pyedgeconnect/orch/_login.py).
- [HPE: gmsserver/briefInfo e info](https://github.com/aruba/pyedgeconnect/blob/main/pyedgeconnect/orch/_gms_server.py).
- [Autenticación y CSRF](https://developer.arubanetworks.com/edgeconnect/docs/authentication).
