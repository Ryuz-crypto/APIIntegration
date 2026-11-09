# QA de seguimiento — dos Orchestrators

Esta batería complementa [QA-FULL.md](QA-FULL.md) y [QA-BATTERY.md](QA-BATTERY.md). Prioriza las pruebas fallidas, bloqueadas o sin contraste suficiente del informe del 9 de noviembre. Las pruebas previamente satisfactorias se omiten salvo T0 e inventario mínimo, necesarios para identificar correctamente cada destino. Un PASS aquí no certifica la batería completa.

## Reglas

- Solo lectura y dry-run, sin `confirm=true`, cambios de roles, forwarding, configuración ni reinicios.
- Registra fecha UTC, versión y SHA aprobado del despliegue, cliente, Orchestrator, versión, perfil, target y appliance. Compara cada llamada con el inventario de su propio destino; nunca reutilices un nePk de otro Orchestrator sin comprobarlo.
- Estados: PASS, FAIL, BLOCKED, SKIPPED_NO_ENTITY (ausencia contrastada) y SKIPPED_NOT_CONFIGURED. Permiso denegado es BLOCKED; el motivo exacto del 403 requiere confirmación. No supongas que una ruta SSH calculada verifica conectividad.
- El estado del 9 de noviembre es histórico; repite los casos en la build servida. No marques como corregido sin evidencia actual.
- Guarda solo evidencia saneada: oculta credenciales, cookies, claves, datos personales, direcciones y nombres sensibles. No pegues payloads crudos sin revisarlos.

## 0. Identidad y selección segura por destino

1. Ejecuta `list_orchestrator_targets_tool({})` y registra dos nombres configurados como A y B sin exponer URLs ni secretos.
2. Para cada uno ejecuta `orchestrator_info({"target":"<target>"})` y registra `build.package_version`, `build.git_commit`, versión detectada, perfil activo y datos de identificación no sensibles. T0 es PASS solo si versión y SHA coinciden con el despliegue aprobado. Si falla, bloquea pruebas dependientes.
3. Ejecuta `list_appliances({"target":"<target>"})` para A y B y elige un appliance verificado por cada uno. Documenta alias A/B y un identificador saneado en el reporte.

**Importante:** no todas las tools admiten `target`. Antes de cada llamada inspecciona el schema `tools/list` servido. Usa `target` explícito solo si está declarado. Si no lo admite, ejecútala para A o B únicamente en una sesión o instancia ya configurada y verificada para ese destino: confirma con `orchestrator_info({})` y `list_appliances({})` inmediatamente antes. Si no puedes identificar el destino por defecto con seguridad, marca ese caso BLOCKED. No cambies el destino global ni reinicies el servicio para forzar la prueba.

## Resultados satisfactorios documentados — ejecución anterior

Según el informe proporcionado por el agente, el 9 de noviembre de 2026 entre 22:47 y 22:53 UTC se probó ec-mcp 8.2.0 en el commit `53f4826d3cd815b326b46ebfe7e9d2a173ddb19b`. A continuación se registra **lo reportado**, no una nueva ejecución independiente. Los resultados solo aplican a esa build y alcance:

| Caso | Destino | Evidencia satisfactoria reportada | Límite |
|---|---|---|---|
| T0 | A y B | Versión y SHA coincidentes con la build aprobada. | Repetir T0 en cada nueva sesión/build. |
| H10 | A y B | Inventario de A y B distinto y coherente con `list_appliances` del mismo target. | Solo lectura de inventario; no demuestra escrituras, todos los helpers ni todos los fallbacks. |
| H1 | A y B | Ya no aparece la excepción lista/dict. | A presentó 403 parciales; hubo truncamiento. No es PASS de integridad completa. |
| H2 | A y B | Se devolvieron propuestas dry-run sin el TypeError anterior. | Falta contrastar auditoría y ausencia de escrituras. |
| H3 | A | El 403 se reportó como ERROR y no como ausencia. | La lectura sigue bloqueada; vacío en B no prueba ausencia sin contraste. |
| H5 | A | `query_used` mostró `from` y `to` para la ventana pedida. | Falta contraste independiente y ejecución real en B. |
| B11 | B | Se reportaron muestras del túnel seleccionado. | No valida A ni otras ventanas. |
| E6 | B | Ambas tools respondieron; sus resultados fueron consistentes entre sí para el alcance informado. | Sin contraste independiente; no prueba todos los tipos de túnel. |

H4 no se declara satisfactorio de extremo a extremo: un mensaje de SSH deshabilitado no prueba la resolución, conexión ni autenticación, y existe discrepancia con `ssh_enabled=true` reportado. Los 403, respuestas truncadas y verificaciones sin fuente independiente permanecen pendientes.

## Siguiente nivel — batería activa

Esta fase **no repite los PASS anteriores** salvo T0, inventario mínimo y comprobaciones necesarias para validar cada caso. Registra A y B por separado. Revisa el schema efectivo de `tools/list` antes de cada llamada y usa `target` solo donde esté declarado. Si una tool no acepta `target`, úsala únicamente en una sesión cuyo destino predeterminado esté verificado; de lo contrario BLOCKED.

### N0 — Identidad y alcance obligatorio

Ejecuta `list_orchestrator_targets_tool({})`, `orchestrator_info({"target":"<target>"})` y `list_appliances({"target":"<target>"})` para A y B. Registra versión, SHA completo servido, versión y perfil de cada Orchestrator, sesión predeterminada, y appliance/túnel específico verificado para cada uno. Compara contra el SHA **aprobado para esta sesión**, no contra el SHA histórico. Sin coincidencia T0 es BLOCKED y se detienen sus dependencias.

### N1 — Aislamiento de targets en lectura

Para A y B ejecuta `call_read_api({"operation_id":"orchestrator.inventory.summary","target":"<target>"})` y contrasta con `list_appliances` del mismo destino. Comprueba target inexistente y, cuando sea aplicable, fan-out `all`; verifica que no se consulte el predeterminado como fallback. Si hay identificadores iguales en ambos targets, contrasta además una señal que los distinga. PASS requiere datos correctos y ausencia de mezcla; si no puedes verificar la solicitud upstream o target desconocido, documenta el límite. **No infieras seguridad de escritura por esta prueba de lectura.**

### N2 — Escrituras: aislamiento con clientes simulados

Esta prueba es **solo automatizada en laboratorio/mocks**, no invocar escrituras confirmadas en un Orchestrator real. Prueba `apply_change` para A, B, target inexistente y target omitido con múltiples targets. Verifica que dry-run, confirmación simulada y lectura de verificación usan el mismo cliente; que un destino desconocido no cae al predeterminado y que el dry-run identifica el target. Registra si target omitido usa predeterminado: es comportamiento observado, no prueba de bloqueo seguro. Confirma candados, auditoría, no-duplicación y cero tráfico de escritura real. Si no hay entorno de pruebas, BLOCKED; no usar producción como sustituto.

### N3 — Infraestructura y respuesta completa

En A y B ejecuta `get_orchestrator_infrastructure({"target":"<target>"})`. Registra cada sección accesible, 403 y truncamiento. Si falta una sección requerida o la respuesta está truncada, el resultado global es parcial/BLOCKED; la desaparición de la excepción H1 sí puede registrarse como PASS por separado. No atribuir causa del 403 sin evidencia.

### N4 — Auditoría de propuesta dry-run

Para cada target usa `propose_remediation` con `appliance_id` y `target` si el schema lo permite. Confirma `applied=false` y ausencia de ejecución automática. Con acceso autorizado, contrasta el registro JSONL saneado de esa llamada, incluyendo destino, resultado y `dry_run`; no publiques registros crudos. Si no tienes acceso a auditoría, PASS solo para la respuesta y BLOCKED para la auditoría. No uses `confirm=true`.

### N5 — Brownout: dato vacío frente a error

Repite en A y B con `get_brownout_state`. Comprueba que un error upstream no se etiqueta como ausencia, y contrasta una respuesta vacía con fuente autorizada del mismo destino y ventana. Si no hay contraste, ausencia indeterminada/BLOCKED, no `SKIPPED_NO_ENTITY`. Para combinación de resultados éxito/error usa fixtures o mocks, sin provocar fallas en producción.

### N6 — SSH: configuración y etapas

En cada target registra el estado SSH global y el efectivo por destino sin mostrar secretos. Resuelve el appliance mediante `get_ssh_network_path`, compara con inventario y registra salida saneada. Solo si SSH está habilitado y autorizado, ejecuta `run_show_command({"command":"show version","host":"<identificador>","target":"<target>"})` usando el schema servido. Registra separadamente resolución, conexión, host key, autenticación y salida del equipo. Un error de SSH deshabilitado no demuestra que se haya completado la resolución ni la conexión. Si está deshabilitado, BLOCKED; no activar SSH ni crear reglas para esta prueba.

### N7 — Ventana de alarmas en A y B

Inspecciona `list_api_operations` para `orchestrator.alarmgms25`, sus parámetros y unidades por perfil. En cada target usa una ventana UTC explícita, con una fuente autorizada para contrastar. Registra valores enviados y `request_echo.query_used`; verifica que los eventos estén dentro de la ventana y que una respuesta vacía tenga contraste. Un PASS en A no certifica B. Si no existe contraste independiente, marca parcialmente validado/BLOCKED.

### N8 — Performance y permisos

En B repite `get_appliance_infrastructure({"appliance_id":"<nePk>","target":"<target>"})`; registra si el endpoint exige `trafficType`, `granularity`, errores por campo y truncamiento. No supongas que el fix está desplegado. En A repite las lecturas bloqueadas A3/A7/B10/B11/T5/C2/E6 solo con permisos ya concedidos; un 403 es BLOCKED, no ausencia y no prueba por sí solo la causa. No elevar permisos.

### N9 — HTTP, panel y dashboard

Desde un cliente autorizado comprueba `/health`, rechazo de `/mcp` sin credenciales y carga/login/Servicios del panel. No compartir tokens ni cookies. Para dashboard registra destino efectivo, errores parciales y completitud; HTML truncado no acredita integridad. Sin acceso directo al servidor/panel, BLOCKED. No reiniciar ni cambiar configuración.

### N10 — Integridad de informes y criterios de cierre

Por cada caso y target anota hora UTC, build, argumentos saneados, esperado, observado, fuente independiente, estado y enlace de issue/evidencia. Usa PASS, FAIL, BLOCKED, SKIPPED_NO_ENTITY solo con ausencia contrastada, y SKIPPED_NOT_CONFIGURED solo con configuración comprobada. Diferencia **casos planificados**, **ejecutados**, **bloqueados antes de ejecutar** y **bloqueados después de ejecutar**; los estados deben sumar el total planificado sin contar subcasos dos veces. Registra por separado PASS parcial y alcance no certificado.

No publiques credenciales, cookies, PSK, direcciones internas ni datos personales. Ninguna operación confirmada o modificación de red está autorizada por esta guía. El cierre de esta fase exige N0 PASS, sin FAIL/BLOCKED en el alcance obligatorio acordado; omisiones justificadas no certifican la función ni el despliegue completo.

---

## Anexo histórico — casos de la primera fase

Los siguientes casos se conservan como referencia histórica; para la ejecución actual usa la sección **Siguiente nivel**. Repite un caso histórico solo si cambió la build, el entorno o hay una regresión justificada.

### Casos de la primera fase

| ID | Prueba | Criterio y evidencia |
|---|---|---|
| H1 / B9 | `get_orchestrator_infrastructure({"target":"<target>"})` | PASS si devuelve resultado interpretable sin excepción lista/dict; documenta errores parciales por campo. |
| H2 / D3 | `propose_remediation({"appliance_id":"<nePk>"})` | Solo donde se haya verificado el destino por defecto. PASS si devuelve propuesta dry-run o ausencia válida sin error de auditoría; nunca aplicar. |
| H3 / A8 | `get_brownout_state({"appliance_id":"<nePk>","target":"<target>"})` | Error 403 u otro fallo upstream no puede presentarse como ausencia confirmada. Registra estado global y errores por equipo. |
| H4 / C3 | `get_ssh_network_path({"appliance_id":"<nePk>"})`; luego `run_show_command({"command":"show version","host":"<identificador autorizado>"})` | Ambas solo si se confirmó destino por defecto y SSH está autorizado. Compara resolución por nePk/nombre/IP con inventario de ese mismo target; registra etapa de fallo. No añadas reglas de red. |
| H5 / B4 | Con `list_api_operations`, inspecciona el schema de `orchestrator.alarmgms25`, luego `call_read_api` para una ventana UTC explícita y conocida | Solo destino por defecto verificado. Registra argumentos admitidos, unidades, `query_used` y fechas observadas; contrasta con lectura autorizada o UI del mismo Orchestrator. Si los argumentos se ignoran, regístralo; no inventes mapeos. |
| A3 / T3 | `get_wan_health({"appliance_id":"<nePk>","target":"<target>"})` | Revisa latencia/jitter/pérdida y errores parciales; 403 es BLOCKED. Compara origen y ventana cuando exista acceso. |
| A7 | `get_tunnel_state({"appliance_id":"<nePk>","target":"<target>"})` | Compara con fuente viva; 403 es BLOCKED. |
| B10 | `get_appliance_infrastructure({"appliance_id":"<nePk>","target":"<target>"})` | Registra estado por campo y errores; sin PASS global si falta una sección requerida. |
| B11 | `get_realtime_stats({"appliance_id":"<nePk>","target_type":"tunnel","name":"<túnel-real>","count":5})` | Solo destino por defecto verificado; registra identidad del túnel y muestras, o 403 como BLOCKED. |
| T5 / C2 | `run_show_api({"command":"show version","appliance_id":"<nePk>"})` y `run_show_api({"command":"show arp","appliance_id":"<nePk>"})` | Solo destino por defecto verificado. Debe responder el equipo correcto; tabla ARP vacía necesita contraste. |
| A9–A11 | Revisar availability, top talkers y HA en el target, si los schemas lo permiten | Vacío sin contraste es indeterminado; no afirmar ausencia o standalone sin evidencia. Documenta origen y ventana. |
| E6 | `get_site_to_site_tunnels({"appliance_id":"<nePk>"})` frente a `get_tunnel_state` | Solo destino por defecto verificado. Compara tipo y alcance de túneles; 403 es BLOCKED. |

Para H6, contrasta diferencias de alarmas con UI y hora de cada fuente; cambios de estado y semántica pueden explicar diferencias. H5 requiere una ventana que contenga o excluya datos de forma inequívoca, sin publicar datos sensibles.

### Controles transversales de la primera fase

- **D2:** registra por separado el estado efectivo de los candados EdgeConnect y SSE. Si alguno está habilitado o no se puede leer, no declares PASS del bloqueo con ambos apagados; marca BLOCKED. No cambies valores para esta sesión.
- **D4 / E3:** desde un cliente autorizado con acceso al servidor, comprueba protección HTTP y carga/login del panel. Si no hay acceso, BLOCKED; ausencia de acceso del evaluador no significa servicio no configurado.
- **E2:** repite render solo si el HTML completo puede obtenerse; una respuesta truncada no prueba integridad. Verifica snapshot por destino solo cuando su schema o sesión permita identificarlo.
- **E4:** concilia el total de conectores y categorías con páginas completas; la plataforma SSE no se asocia automáticamente a ambos Orchestrators. No incluyas datos personales.
- **E5:** si el perfil no ofrece Copilot, registra el motivo y disponibilidad contrastada. No aumentes privilegios para forzar una prueba.

### Formato de informe de la primera fase

```text
Fecha UTC / responsable / entorno:
Build aprobada: versión=<...> SHA completo=<...>
Target A: alias=<...> versión Orchestrator=<...> perfil=<...>
Target B: alias=<...> versión Orchestrator=<...> perfil=<...>
Destino por defecto de cada sesión y evidencia: <...>

Caso | Target | Tool y argumentos saneados | Hora/ventana | Esperado
     | Observado y errores parciales | Fuente de contraste | Estado | Issue
H1/B9 | A | ... 
H1/B9 | B | ...
[una fila por caso y target; indicar explícitamente cuando no se ejecutó]

Resumen: casos planificados=<...>, ejecutados=<...>, PASS=<...>,
FAIL=<...>, BLOCKED=<...>, SKIPPED_NO_ENTITY=<...>,
SKIPPED_NOT_CONFIGURED=<...>; comprobar que los totales concuerden.
Hallazgos abiertos, alcance no probado y siguiente acción: <...>
```

Una función solo se considera validada para el destino y alcance probados. Los casos BLOCKED y los que dependen del destino por defecto permanecen pendientes hasta contar con acceso verificable; esta batería no autoriza producción ni escrituras por sí sola.
