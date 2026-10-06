# pyedgeconnect: utilidad para el MCP de EdgeConnect

Revisión: 2026-10-06. Fuente: [SDK oficial `aruba/pyedgeconnect`](https://github.com/aruba/pyedgeconnect), [referencia de módulos](https://pyedgeconnect.readthedocs.io/en/latest/pyedgeconnect.html), [ejemplo EdgeConnect↔SSE](https://pyedgeconnect.readthedocs.io/en/latest/examples/ec_sse_orchestration.html), [ejemplo de políticas](https://pyedgeconnect.readthedocs.io/en/latest/examples/upload_security_policy.html) y [guía actual de HPE sobre Service Orchestration](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/cloud/service-orch/). El usuario no incluyó un enlace a una librería llamada literalmente «PyConnect»; confirmar la URL si se refiere a otra. Esta revisión no hizo cambios en dispositivos.

## Qué aporta el SDK

`pyedgeconnect` es una capa Python sobre REST con clases `Orchestrator` y `EdgeConnect`. Incluye API key o sesión para Orchestrator, login con MFA para modalidades soportadas, requests con timeout y verificación TLS configurables, métodos de inventario, estadísticas, políticas y escritura. El repositorio advierte que el soporte para cambios API en Orchestrator 9.3+ es preliminar y que no cubre todas las operaciones. Sus funciones son una referencia útil de parámetros y respuestas, no sustituyen la validación de los Swagger y la versión instalada del cliente. En el MCP ya hay perfiles REST para 9.3, 9.4, 9.5 y 9.6 y transporte propio `httpx`; instalar el SDK duplicaría sesiones, autenticación, logging y tratamiento de errores.

| Uso útil | Referencia del SDK | Estado en el MCP / decisión |
|---|---|---|
| EdgeConnect↔SSE | `get_service_orchestration_all_services`, `get_service_orchestration_remote_endpoints`, `get_service_orchestration_appliance_association`, labels, tunnel settings e IP SLA | Los GET ya existen en los cuatro perfiles; `get_sse_status` consulta integraciones específicas, pero falta un resumen **genérico** por servicio/`nePk` que cruce endpoint, label, asociación, túnel e IP SLA. Prioridad alta de lectura. |
| Flujos NGFW | `EdgeConnect.get_appliance_flows`, `get_appliance_flow_details_verbose`, `get_appliance_security_policies` | `get_security_log` y la matriz de zonas no muestran todavía una correlación completa de Flow ID con detalle `/flow/flowDetails2` o `/flowDetails2`. Añadir lectura acotada por `nePk`, ID y secuencia, distinguiendo política configurada de decisión del flujo. |
| Estadística por segundo | `Orchestrator.get_realtime_stats` consulta `POST /realtimeStats` | El perfil declara `orchestrator.realtime_stats519` como POST de consulta; el guard genérico del MCP lo trata como escritura. Si se necesita, crear un helper de solo lectura con cuerpo y tipo estrictamente permitidos, frecuencia y costo acotados; nunca abrir todos los POST declarados `risk=read`. El SDK señala retención de solo tres segundos en ECOS. |
| Seguridad NGFW | `EdgeConnect.get_appliance_security_policy_map` y ejemplo CSV | El ejemplo muestra merge y que una regla con igual prioridad en el mismo par de zonas se sobrescribe. Utilizar para diseñar dry-run, snapshot completo, conflicto, verificación y rollback; no desbloquear escritura hasta comprobar contratos 9.3–9.6 y comportamiento real. |
| ZTP/BIO/túneles | APIs de preconfig, overlays, deployment y túneles | El MCP ya tiene workflows controlados de overlay y ZTP e inventario de túneles. Tomar campos documentados como casos de QA; evitar reimplementar otro cliente REST. |

El ejemplo SSE del SDK fue concebido como solución provisional de aprovisionamiento inicial. Permite filtrar por appliance o región, preparar servicio/etiquetas/endpoints y crear locations/túneles en SSE. Deja el `Commit` de SSE para revisión separada porque puede incluir cambios pendientes de otros operadores. La guía actual de HPE indica que Service Orchestration gestiona el ciclo de vida de los túneles IPsec e IP SLA; el MCP debe **inspeccionar primero la orquestación nativa** y automatizar solo las brechas verificadas. En HA, validar cómo se nombran locations y se asignan ambos appliances antes de cualquier escritura.

## Corrección inmediata identificada

Los cuatro perfiles etiquetaban los POST `/flow/flowReset` y `/flow/flowReClassification` como `risk=read` e incluían una nota que los presentaba como consultas seguras. El SDK describe explícitamente `reset_flows` y `reclassify_flows` como acciones; reclasificar con lista vacía puede afectar a todos los flujos. Se corrigió el riesgo a `write` y se quitó aquella nota. El guard anterior ya exigía flujo de escritura por tratarse de POST, pero el catálogo ahora muestra el riesgo correcto. `tests/test_edgeconnect_sdk_alignment.py` protege el cambio en 9.3–9.6.

## Validación pendiente antes de ampliar el MCP

1. En un laboratorio autorizado, obtener respuestas reales de `/thirdPartyServices/serviceOrchestration/*`, estados de túnel e IP SLA para 9.3–9.6, incluida una pareja HA y fallos parciales. Inspeccionar si las cadenas JSON escapadas de labels y tunnel settings varían por versión.
2. Probar el detalle de flujo (`nePk`, ID y `seq`) y su relación con `securityMaps`, zonas y logs; acotar volumen y datos sensibles.
3. Verificar semántica y carga real de `POST /realtimeStats`, límites de polling, autenticación y fallos. Solo entonces exponer consulta dedicada.
4. Mantener separadas las escrituras en Orchestrator y el `Commit` del tenant SSE; preparar plan, permisos, confirmación y reconciliación para ambos sistemas antes de automatizar aprovisionamiento.

La incorporación previa de `pyhpesse` en [HPE-SSE-INTEGRATION.md](HPE-SSE-INTEGRATION.md) cubre **inventario del Admin API SSE**, no el plano de control SD-WAN de EdgeConnect. Ambas superficies se pueden correlacionar después de validar los contratos, sin inferir enforcement de una asociación o de un catálogo.
