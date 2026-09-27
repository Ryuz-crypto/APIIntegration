# Try Me · Swagger Explorer

La pestaña **Try Me** permite ejecutar las APIs disponibles en el Swagger de cada Orchestrator. El explorador no se limita a las operaciones que construyen el dashboard: muestra todos los paths y métodos del documento importado.

## Preparar el catálogo completo

El perfil integrado permite comenzar con las operaciones verificadas por DashboardAPI-EC. Pulsa **Traer del Orchestrator** para buscar la definición en las rutas publicadas conocidas. Si el entorno no expone directamente el archivo, descarga la definición correspondiente y pulsa **Importar Swagger** dentro de Try Me.

HPE documenta el archivo del Orchestrator como `gmsApiInfo.json` y lo ubica en la interfaz **Support → REST APIs**. La definición debe corresponder a la versión del entorno. Orchestrator 9.7 usa el contrato 9.6 en esta plataforma mientras no exista un perfil específico importado.

La importación acepta OpenAPI 3 o Swagger 2 en JSON o YAML. El documento queda almacenado como borrador: alimenta Try Me, pero no reemplaza automáticamente el perfil activo del dashboard.

## Explorar y ejecutar

1. Abre **Try Me** en el menú lateral.
2. Selecciona uno de los Orchestrators guardados.
3. Filtra por tag o busca por método, path, resumen u `operationId`.
4. Selecciona la operación.
5. Completa los parámetros de path, query o headers.
6. Revisa el cuerpo JSON sugerido a partir del schema.
7. Pulsa **Ejecutar**.

La petición utiliza la URL, validación TLS, timeout y credencial cifrada del Orchestrator seleccionado. Los headers de autenticación, cookies, `Host`, longitud y transporte no se pueden reemplazar desde el editor. Una conexión OTP utiliza únicamente la sesión temporal vigente; cuando expire, vuelve a validarla desde el panel de Orchestrators.

## Operaciones que modifican configuración

Los métodos `POST`, `PUT`, `PATCH` y `DELETE` pueden cambiar el comportamiento del Orchestrator. Para ejecutarlos se requieren estas tres condiciones:

- acceso al dashboard mediante HTTPS o túnel SSH local;
- `TLS_ADMIN_TOKEN` de `/etc/dashboardapi-ec/dashboardapi-ec.env`;
- confirmación exacta `EJECUTAR MÉTODO /path/del/swagger`.

El backend comprueba que el método y el path pertenezcan al Swagger seleccionado. No acepta URLs arbitrarias. Cada ejecución queda en las muestras API y cada operación de cambio genera además un evento de auditoría con método, path, status y sample ID; no registra credenciales.

## Salidas y exportación

El panel de salida separa:

- respuesta del Orchestrator;
- request sanitizado;
- headers de respuesta permitidos;
- status HTTP, latencia y error, cuando corresponda.

**JSON** descarga el resultado completo. **CSV** aplana la respuesta en pares `path,value`, útil para revisarla en Excel o cargarla en herramientas de análisis.

Antes de mostrar, registrar o exportar, la plataforma sustituye valores cuyos nombres indiquen contraseña, token, secreto, API key, cookie, autorización o CSRF por `[REDACTED]`.

## Snapshots

Después de ejecutar una operación asigna un nombre y pulsa **Guardar snapshot**. El snapshot conserva de forma inmutable:

- Orchestrator y sample original;
- operación, método y path resuelto;
- parámetros y cuerpo enviados, sin autenticación;
- status y payload recibido;
- fecha de creación.

Los snapshots se muestran al final de Try Me. Puedes abrirlos, exportarlos o eliminarlos. Permanecen en PostgreSQL después de reiniciar o actualizar la plataforma.

## Diagnóstico

- **Sólo aparecen algunas APIs:** importa el Swagger completo; el perfil integrado contiene las operaciones comprobadas por el dashboard.
- **HTTP 401/403:** revisa permisos de la API key o renueva la sesión OTP.
- **HTTP 404:** confirma que el documento corresponde a la versión del Orchestrator.
- **No permite un cambio:** utiliza HTTPS, comprueba `TLS_ADMIN_TOKEN` y copia literalmente la confirmación mostrada.
- **El schema no incluye ejemplo:** Try Me genera una estructura inicial según tipos y valores predeterminados; ajústala antes de ejecutar.

Referencia: [HPE Aruba Networking — Orchestrator and EdgeConnect API endpoints](https://developer.arubanetworks.com/edgeconnect/docs/aruba-orchestrator-and-edgeconnect-api-endpoints).
