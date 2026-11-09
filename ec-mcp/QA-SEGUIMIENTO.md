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

## 1. Casos a repetir en cada Orchestrator

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

## 2. Controles transversales pendientes

- **D2:** registra por separado el estado efectivo de los candados EdgeConnect y SSE. Si alguno está habilitado o no se puede leer, no declares PASS del bloqueo con ambos apagados; marca BLOCKED. No cambies valores para esta sesión.
- **D4 / E3:** desde un cliente autorizado con acceso al servidor, comprueba protección HTTP y carga/login del panel. Si no hay acceso, BLOCKED; ausencia de acceso del evaluador no significa servicio no configurado.
- **E2:** repite render solo si el HTML completo puede obtenerse; una respuesta truncada no prueba integridad. Verifica snapshot por destino solo cuando su schema o sesión permita identificarlo.
- **E4:** concilia el total de conectores y categorías con páginas completas; la plataforma SSE no se asocia automáticamente a ambos Orchestrators. No incluyas datos personales.
- **E5:** si el perfil no ofrece Copilot, registra el motivo y disponibilidad contrastada. No aumentes privilegios para forzar una prueba.

## 3. Informe por target y cierre

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
