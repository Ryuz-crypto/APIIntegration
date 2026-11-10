# 9.2.0 — Preparación de auditoría y no repudio

## Alcance y estado

Esta versión prepara evidencia; **no implementa ni certifica no repudio** ni cumplimiento de ningún marco. El panel de Debug permite descargar una huella SHA-256 del archivo de auditoría activo (hasta 64 MiB) y no incluye archivos rotados, journal ni registros de otros equipos. La huella no está firmada, no tiene sello temporal confiable ni anclaje externo: si se modifica el archivo y la huella, esta captura por sí sola no detecta el reemplazo. Guárdese en un repositorio independiente con retención y controles de acceso propios. Un archivo que cambia durante la lectura se rechaza; una captura posterior cambia al agregarse eventos.

Los eventos nuevos incluyen identificador UUID, esquema y fecha UTC. El ID no prueba identidad ni vincula automáticamente tool, petición upstream y resultado. Los eventos anteriores pueden no tener ID. Los reportes CSV y Excel siguen limitados a los últimos eventos disponibles y no sustituyen el registro íntegro. La limpieza de Debug vacía solo memoria: no trunca ni elimina auditoría persistente o rotaciones.

## Referencias y brechas

| Referencia | Objetivo de diseño | Estado |
| --- | --- | --- |
| NIST SP 800-92 | Recolección, protección y gestión de registros | Parcial: fuente local y exportación limitada; falta recolección integral, retención y almacenamiento independiente. |
| NIST SP 800-53 Rev. 5 AU-2/AU-3 | Eventos y contenido de auditoría | Parcial: falta catálogo integral y correlación de usuario, sesión, tool, API, destino y resultado; no se infiere identidad ausente. |
| AU-9/AU-11 | Protección y retención | Parcial: el borrado desde Debug se limita al buffer; faltan segregación administrativa, retención inmutable y control de borrado fuera de la aplicación. |
| AU-10 | No repudio | No implementado: falta vinculación de identidad, firma verificable con claves protegidas, sellado temporal confiable, cadena de custodia y evaluación independiente. |
| FIPS 186-5 | Firmas digitales | Referencia para diseño futuro; una huella SHA-256 sin firma no cumple ese objetivo. |

Fuentes: [NIST SP 800-92](https://www.nist.gov/publications/guide-computer-security-log-management), [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final), [FIPS 186-5](https://csrc.nist.gov/pubs/fips/186-5/final).

## Siguientes componentes necesarios

1. Inventariar fuentes y retención: autenticación, acceso denegado, administración, tools MCP, llamadas upstream, aprobaciones y ejecución de cambios, SSH, servicio y sistema. Registrar omisiones y fallos de captura sin registrar secretos.
2. Propagar un ID de correlación por solicitud y metadatos mínimos: actor autenticado o desconocido, rol, origen, destino, hora UTC, acción, resultado y duración real. Evitar asociar un usuario de panel a un cliente MCP sin evidencia.
3. Definir identidad individual y autenticación fuerte; documentar sesiones compartidas y acciones automáticas como tales. Asegurar sincronización de reloj y evidencias de su estado.
4. Diseñar canal independiente e inmutable con control de acceso separado, retención configurada, verificación periódica y alertas. Firmar manifiestos mediante claves protegidas y gestionadas fuera del proceso; evaluar sellado temporal confiable y rotación/revocación.
5. Probar pérdida de eventos, concurrencia, truncamiento, rotación, cambios, reordenamiento, caída, recuperación, exportación y verificación independiente. Obtener revisión de seguridad y de requisitos aplicables antes de declarar cumplimiento.

## Revisión: desactivar un Orchestrator o SSE

En este documento “desactivar” significa impedir que **el MCP use el destino**, no detener el appliance o el servicio remoto. Aún no hay botón operativo ni una garantía de bloqueo.

- El registro y sus blobs de entorno se gestionan en `multi_target.py` y `admin.py`. El runtime en `server.py` carga los destinos al iniciar y mantiene clientes compartidos; un cambio requiere aplicar y reiniciar o rediseñar la recarga.
- Si la lista queda vacía, existen rutas de respaldo a variables globales. Al desactivar el último destino, ese respaldo podría reactivar una conexión que el usuario creía deshabilitada.
- La selección predeterminada puede resolver otro nombre automáticamente; hay que evitar cambios silenciosos de destino, especialmente para escrituras.
- `api_apply`, la selección por nombre, sondas del panel, SSH y todas las rutas SSE deben respetar el mismo estado. El indicador visual actual de activo no demuestra un bloqueo de runtime.
- La sincronización del blob captura algunos errores de E/S sin propagarlos: no debe indicarse éxito si el archivo no se guardó. La acción necesita autorización, auditoría, confirmación explícita, preservar secretos y estado pendiente de reinicio.
- Antes de habilitar la función, probar en mocks: destino explícito desactivado, predeterminado desactivado, último destino, variables globales presentes, SSE, clientes cacheados, fallos de persistencia, reinicio y reactivación. Después validar de forma controlada con ambos Orchestrators reales.

Seguimiento: [#171](https://github.com/Ryuz-crypto/APIIntegration/issues/171). No se modificaron los destinos ni los Orchestrators reales.
