# Revisión del SDK SASE/SSE y puente MCP

Fecha: 2026-10-06. Implementación de laboratorio en `fix/operation-integrity-4.5` (PR #38); referencia estable 4.5.0 sin cambios. No se ha consultado ningún tenant real.

La denominación “PyConnect” no identifica de forma unívoca el SDK. El paquete oficial [pyedgeconnect](https://github.com/aruba/pyedgeconnect) cubre Orchestrator y EdgeConnect SD-WAN, que este MCP ya consulta directamente. Para el componente HPE SSE/Axis, el SDK oficial es [pyhpesse](https://github.com/aruba/pyhpesse), versión 1.0.4 inspeccionada, [fuente de AdminApi](https://github.com/aruba/pyhpesse/blob/main/pyhpesse/adminapi.py) y [transporte](https://github.com/aruba/pyhpesse/blob/main/pyhpesse/common.py). Si el nombre alude a otro repositorio, verificarlo antes de extender este puente.

`pyhpesse` usa un token bearer de Admin API y una URL base HTTPS (`https://admin-api.axissecurity.com` por defecto). Contiene operaciones de lectura y escritura para aplicaciones, conectores, categorías IP/web, exclusiones SSL, ubicaciones, túneles, usuarios y otros recursos, además de `Commit` para aplicar cambios. Algunas operaciones son de disponibilidad limitada. Asignar al token los permisos mínimos que permita el tenant; confirmar si admite un rol de solo lectura. No se han añadido escrituras ni `Commit`.

| Recurso MCP | Método `AdminApi` | GET admitido | Evidencia que entrega |
|---|---|---|---|
| `web_categories` | `get_webcategory` | `/api/v1.0/WebCategories` | Catálogo de categorías, no política aplicada. |
| `custom_ip_categories` | `get_customipcategory` | `/api/v1.0/IpCategories` | Definiciones IP. |
| `ip_feed_categories` | `get_ipfeedcategory` | `/api/v1.0/IpCategoriesFeed` | Feeds de IP. |
| `ssl_exclusions` | `get_sslexclusions` | `/api/v1.0/SslExclusions` | Exclusiones configuradas. |
| `locations` | `get_locations` | `/api/v1.0/Locations` | Ubicaciones del tenant. |
| `tunnels` | `get_tunnels` | `/api/v1.0/Tunnels` | Inventario de túneles del tenant. |
| `health` | `get_health` | `/api/v1.0/Health` | Respuesta de salud de la API. |

La implementación está en [`hpe_sse.py`](ec_mcp/hpe_sse.py). Reutiliza `httpx`, ya presente en el MCP, con métodos GET predefinidos, paginación 1..10000/1..100, TLS verificado, timeout de 15 s, redirecciones deshabilitadas y código HTTP comprobado. No importa el SDK directamente: el helper `HPESecureServiceEdgeApiLogin._send_request` desactiva avisos TLS de `urllib3` de forma global, imprime un 403 y devuelve el cuerpo sin elevar todos los fallos; esto impide distinguir una lectura válida de una autenticación fallida sin añadir controles propios. Ninguna ruta puede seleccionarse libremente desde la herramienta MCP.

Para activar el puente, configure `EC_HPE_SSE_API_TOKEN` y, solo si el tenant requiere un origen diferente, `EC_HPE_SSE_API_URL`; reinicie el servicio. Puede configurarse también desde la pestaña Variables del panel, que muestra únicamente si el token está configurado. Una respuesta de `get_hpe_sse_inventory(resource="web_categories")` conserva el JSON de la API en `response`, los metadatos de paginación y `enforcement_verified=false`. El serializador del MCP redacta campos de credenciales y trunca resultados extensos con aviso. `EC_VERIFY_TLS=false` no desactiva TLS de SSE.

Para completar el filtrado web se necesitan contratos adicionales del tenant: lectura de reglas SWG, alcance de grupos/ubicaciones, orden y acción efectiva, logs de decisión con tiempo y correlación con appliance/túnel, y un ensayo de URLs permitidas/bloqueadas. El SDK inspeccionado ofrece inventario de categorías, pero esto no prueba políticas ni enforcement. Después de validar esquemas y permisos reales, incorporar endpoints explícitos y correlacionar la evidencia sin convertir una categoría existente en “protegido”. Para cambios futuros, preparar/dry-run, comparar snapshot, requerir permisos y confirmación separados y tratar `Commit` y timeout como mutaciones de resultado incierto.

Pruebas: `pytest tests/test_hpe_sse.py` (15 simuladas), suite completa 455 y subconjunto `security` 255. Pendiente: smoke test de solo lectura con token mínimo en un tenant autorizado, respuesta de paginación real, fallos 401/403/rate limit, versiones/regiones, y límites de datos sensibles de cada recurso.
