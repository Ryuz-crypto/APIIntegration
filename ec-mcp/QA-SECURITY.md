# Revisión y batería del path de seguridad

Fecha: 2026-10-06. Alcance: `APIIntegration/ec-mcp`, herramientas MCP, cliente HTTP y perfiles API 9.3, 9.4, 9.5 y 9.6.

La referencia estable sigue siendo **4.5.0**, rama `release/4.5.0`, commit `949b60ffefd6480b7913d911b2128ef425527753`. Estas correcciones y pruebas están en `fix/operation-integrity-4.5`, PR #38. No se ha actualizado ningún servidor ni aplicado ninguna remediación sobre dispositivos reales durante esta revisión.

## Resultado y límites

La base de la rama tenía 217 pruebas. Se añadieron **238 pruebas**, para un total de **455**. El marcador `security` selecciona **255 casos**, incluyendo las 15 pruebas del puente HPE SSE. La batería usa herramientas MCP reales y `httpx.MockTransport`: inspecciona método, ruta, proxy, nePk, cabecera de autenticación, cuerpo y estado posterior. Los fixtures representan los contratos presentes en el catálogo y en el SDK SSE; todavía falta contrastarlos con respuestas reales del fabricante.

| Campo | Interpretación |
|---|---|
| `evidence_status=observed` | El payload contiene campos reconocidos para esa observación. |
| `unknown`, `conflicting`, `error` | No permite inferir protección activa. |
| `assessed_controls_complete` | IDS/IPS, DDoS, matriz de zonas y túneles pudieron evaluarse con los campos esperados. |
| `coverage_complete` | Cobertura de todos los dominios solicitados. Permanece falsa mientras la política de filtrado web no sea observable. |
| `verified=true` en una remediación | El snapshot completo leído coincide con la configuración deseada o con el original tras rollback. |
| `enforcement_verified=false` | No se ha probado el bloqueo efectivo de tráfico. Se conserva aun cuando la configuración coincide. |
| `applied=null` / `rolled_back=null` | El transporte falló y el resultado de la escritura es incierto. Leer/verificar antes de preparar otro cambio. |

## Hallazgos y correcciones

Las severidades expresan impacto potencial del código, no una explotación o incidente comprobado en producción.

| ID | Prioridad | Hallazgo reproducido | Corrección en esta rama |
|---|---|---|---|
| SEC-01 | Alta | `GET /ids/updateSignatureFromPortal` figuraba como lectura y podía ejecutarse desde `call_read_api` con escrituras desactivadas. | Riesgo `write` en los cuatro perfiles; bloqueo en herramientas y transportes de lectura y en verificadores. Solo se permite desde escritura confirmada; sin fallback ni caché. |
| SEC-02 | Alta | Un selector `all` podía convertirse en el primer appliance para una escritura; nombres duplicados también elegían el primero. La lectura API de appliances con `all` podía salir por la ruta global. | Las escrituras requieren un target único y no ambiguo. Las lecturas múltiples usan el proxy por cada nePk. Los helpers de lectura individual rechazan `all`. |
| SEC-03 | Alta | Los cuerpos parciales de `/ids/state` podían reemplazar asignaciones globales; DDoS podía enviarse sin preservar perfiles y mapas. | Snapshots completos, modificación de un target, conservación de las demás asignaciones, lectura previa y comparación antes de escribir. La vía genérica confirmada exige el workflow para estos endpoints. |
| SEC-04 | Alta | El ejemplo de `/securityMaps` solo contiene opciones, entre ellas `merge=false`; no contiene las políticas completas. Otros payloads de firmas, perfiles IDS y settings de firewall no tienen un workflow de preservación validado. | Se bloquean las escrituras confirmadas de esos contratos. El dry-run permite revisarlas. Falta capturar y validar el contrato NGFW completo; no se declara segura una escritura por aceptar cualquier JSON. |
| SEC-05 | Alta | `get_security_posture` no consultaba DDoS y los errores podían terminar con cero hallazgos. | Consulta thresholds y perfiles; errores y falta de evidencia generan hallazgos y cobertura incompleta. Inventario vacío no equivale a un entorno sano. |
| SEC-06 | Alta | Un modo IDS desconocido podía aparecer activo. `IDS Only` no distinguía detección de prevención. | Solo modos reconocidos; campos separados para detección y prevención; estados contradictorios quedan sin verificar. Bajar protección requiere el segundo candado. |
| SEC-07 | Media | El resumen DDoS perdía `zone_id=0`, `false`, nombres `profile` y la estructura `profiles[]` + `profileMaps[]`. | Se preservan valores y relaciones; perfiles o zonas duplicados, referencias ausentes y enables desconocidos no declaran protección. Validación de tipos y rangos definidos en el catálogo. |
| SEC-08 | Media | Una política LAN→WAN se trataba como cobertura WAN→LAN. El total de pares podía perderse al truncar a 40. | Matriz direccional, total y truncación explícitos, lectura de acción por defecto, prioridades ambiguas y reglas inválidas. Un par sin regla explícita requiere revisión; no prueba tráfico permitido. |
| SEC-09 | Alta | Los parámetros de ruta admitían delimitadores; aliases Postman `:zoneId` podían quedar sin resolver. El proxy podía recibir parámetros de routing sobreescritos. | Render de `{param}` y `:param`, codificación de valores y rechazo de traversal, controles y delimitadores. `nePk` y `url` del proxy no pueden sobreescribirse. |
| SEC-10 | Alta | Un timeout posterior a una mutación podía conservar lecturas en caché. Dos planes globales IDS podían interferir. | Invalidación antes del intento de mutación, estado incierto sin repetición automática, locks por alcance y cuota sincronizada. Los conflictos no consumen cuota. |
| SEC-11 | Media | Un fallo de auditoría posterior a escribir podía ocultar una aplicación correcta. Los mensajes HTTP podían exponer credenciales. | Auditoría previa al intento; si falla después se conserva el resultado y se informa `audit_error`. Mensajes HTTP saneados y snapshots completos fuera de respuestas públicas/auditoría. |
| SEC-12 | Media | Las ventanas de eventos IDS se anunciaban aunque el perfil no declara sus parámetros; fechas de log y límites no estaban validados. | Ventanas no soportadas se rechazan explícitamente, fechas reales `YYYY-MM-DD`, límites 1..1000 y metadatos de truncación. Logs admiten wrappers, registros estructurados, IPv6 y comas entre comillas. |
| SEC-13 | Media | La conexión SSE podía confundirse con filtrado web efectivo. Estados de túnel desconocidos se contaban como caídos. | `get_web_filter_status` distingue asociación del target, conectividad y política no observada; asociaciones desconocidas conservan `null`. Túneles separan up/down/unknown. |

## Ejecutar la batería

Desde `ec-mcp`, en un entorno Python 3.12 o superior con las dependencias fijadas:

```bash
python -m pip install -r requirements-stable.txt -e .
python -m pytest tests -m security -q --junitxml=reports/security.xml
python -m pytest tests -q --junitxml=reports/pytest.xml
ruff check ec_mcp tests scripts/apply-web-update.py
bandit -r ec_mcp scripts/apply-web-update.py -q
pip-audit --skip-editable
```

Para CI basta ejecutar una vez la suite completa: ya incluye la batería. GitHub Actions publica `reports/pytest.xml` como artifact `ec-mcp-tests`. El comando con `-m security` sirve para iterar sobre ese dominio de forma independiente.

| Archivo | Qué comprueba |
|---|---|
| `tests/test_security_path.py` | Tools MCP y HTTP real simulado, permisos, proxy, scope, errores, SSE, logs, remediación, conflictos, timeout, concurrencia, auditoría y rollback. |
| `tests/test_security_contracts.py` | Contratos de los cuatro perfiles, reemplazos IDS, tipos/rangos DDoS, asociaciones, direccionalidad, prioridades y evidencia desconocida de NGFW. |
| `tests/test_security_workflow.py` | Regresiones de helpers existentes y sus herramientas. |
| `tests/test_security.py`, `test_operation_integrity.py`, `test_orchestrator_integrity.py` | Controles complementarios incluidos en la suite completa: transporte, CLI, cuota, redacción, no repetición de escrituras y cachés. |

## Remediaciones implementadas

Las herramientas siguientes solo están en la rama de mejoras. El nePk se comprueba en inventario actualizado. Los planes viven en el proceso, expiran a los **10 minutos** y no sobreviven a un reinicio. Mantener un backup externo de la configuración completa antes de una prueba real; el plan público contiene cambios y hashes, no los snapshots completos.

### IDS/IPS: cambiar un modo conservando los demás equipos

```text
prepare_security_remediation(
    appliance_id="<nePk verificado>",
    control="ids_ips",
    mode="IPS-Inline"
)
apply_security_remediation(plan_id="<plan_id>")
apply_security_remediation(
    plan_id="<plan_id>",
    confirmation="APPLY <plan_id>",
    confirm=true
)
verify_security_remediation(plan_id="<plan_id>")
```

El GET `/ids/state` debe contener las cuatro listas `ips_inline`, `ips_lookaside`, `ids` y `disabled`, con cada nePk en una sola lista. El PUT conserva todos los demás equipos. Un target desconocido, un modo inválido, una configuración parcial o un cambio sin efecto no produce una escritura. Los cambios a un modo de menor protección exigen también `EC_ALLOW_DANGEROUS_WRITES=true`.

### DDoS: habilitar un perfil existente asignado

```text
prepare_security_remediation(
    appliance_id="<nePk verificado>",
    control="ddos",
    profile_name="<perfil existente y asignado>"
)
apply_security_remediation(
    plan_id="<plan_id>",
    confirmation="APPLY <plan_id>",
    confirm=true
)
verify_security_remediation(plan_id="<plan_id>")
```

Solo cambia `enable` a `true` en ese perfil. Conserva sus demás campos, todos los otros perfiles y `profileMaps`, incluido zone 0. El plan muestra todas las zonas del appliance que usan ese perfil. No crea perfiles, reasigna zonas ni inventa thresholds; esos cambios requieren otro contrato y validación.

### Conflictos, errores y rollback

Aplicar requiere `EC_ALLOW_WRITE_TOOLS=true`, permisos efectivos en el Orchestrator y la frase exacta vinculada al plan. Un GET justo antes de escribir debe coincidir con el snapshot de preparación. Un conflicto exige preparar otro plan. Solo un intento confirmado consume cuota; dry-run, confirmación incorrecta, conflicto o fallo de auditoría previo no la consumen.

Una respuesta de escritura 2xx no basta para `verified=true`: el GET posterior debe coincidir con el estado completo esperado. Si el GET falla, se conserva `applied=true` y `verified=false`. Si se pierde la respuesta de escritura, `applied=null`: usar `verify_security_remediation`, sin repetir el mismo plan. El plan aplicado no vuelve a ejecutarse.

```text
rollback_security_remediation(plan_id="<plan_id>")
rollback_security_remediation(
    plan_id="<plan_id>",
    confirmation="ROLLBACK <plan_id>",
    confirm=true
)
```

Rollback requiere ambos candados de escritura, incluso si el cambio original elevaba protección. Solo restaura el original si el estado actual completo sigue coincidiendo con el candidato del plan: no sobrescribe cambios ajenos ni una aplicación parcial. Un resultado incierto de rollback se comprueba con `verify_security_remediation`, que compara entonces con el original.

Los locks evitan carreras dentro de un proceso MCP. El Orchestrator no ofrece aquí una transacción atómica GET+PUT ni se ha implementado compare-and-swap: otro operador o instancia puede escribir entre ambas solicitudes. La aplicación real necesita una ventana con exclusión de cambios o un mecanismo de locking del fabricante validado.

## Validación de laboratorio pendiente

Todos los casos siguientes están **pendientes de ejecución real**. Registrar commit MCP, API/ECOS, serial/nePk, VRF/zona, perfil, firma y hora UTC, snapshot previo/posterior, logs y evidencia de tráfico. Usar dispositivos y destinos de laboratorio identificados y un techo acordado de tráfico y duración.

| Caso | Comprobación real | Evidencia para aceptar |
|---|---|---|
| LAB-IDS-01 | GET de modos, perfil y firmas en las versiones realmente instaladas. | Capturas del contrato real; modo/perfil consistente por target; fecha/versión de firma. |
| LAB-IDS-02 | Caso benigno aprobado por el fabricante en IDS Only y en IPS. | En IDS, evento sin atribuir prevención; en IPS, decisión de bloqueo y log correlacionado. |
| LAB-IDS-03 | Cambiar un equipo mediante el plan y verificar el resto. | Snapshot global sin pérdida de asignaciones; recuperación del original con rollback. |
| LAB-DDOS-01 | Perfiles, mapas de zona y thresholds, incluidos 0 y false. | Esquema real, asignación explícita y estado enable coherente; no interpretar valores de threshold sin contrato. |
| LAB-DDOS-02 | Habilitar un perfil y probar tráfico acotado dentro del techo aprobado. | Contadores/eventos del control y conservación de tráfico permitido, latencia y recursos; detener ante el umbral de impacto acordado. |
| LAB-WEB-01 | Conexión SSE y asociación del appliance elegido. | El target, no otro appliance, figura asociado. Una conexión por sí sola no acepta filtrado. |
| LAB-WEB-02 | Leer política URL/categoría y probar destinos de laboratorio permitidos/bloqueados. | Política/versión en el proveedor, decisión y log para cada URL; alcance/usuario y bypass conocidos. |
| LAB-NGFW-01 | Capturar securityMaps/settings completos y validar con documentación de la versión. | Shape, semántica de merge/reemplazo, prioridad, dirección y acción por defecto documentados. Desbloqueo de escritura en un cambio separado con pruebas. |
| LAB-NGFW-02 | LAN→WAN, WAN→LAN, tráfico permitido/denegado y default action. | Resultado por dirección y Flow-ID correlacionado; ausencia de regla explícita no equivale a permiso. |
| LAB-NGFW-03 | VRF/segmentos, IPv4/IPv6, NAT y camino SSE/HA según configuración real. | Política y decisión coinciden con el camino observado; esquema y comportamiento no reconocidos quedan pendientes. |
| LAB-FAIL-01 | Pérdida de lectura, permiso 403, timeout y cambio externo en laboratorio. | Ninguna repetición automática; estado incierto visible; conflicto y recuperación documentados. |
| LAB-ROLLBACK-01 | Backup, rollback dentro del TTL y recuperación manual tras reinicio/expiración. | Sin sobrescribir cambios de otro operador; comprobación completa y tráfico esperado restaurado. |

## Trabajo restante

1. Capturar contratos y evidencia de enforcement en laboratorio para IDS/IPS, DDoS y NGFW; contrastar los cuatro perfiles con versiones instaladas.
2. Integrar lectura de políticas y decisiones del proveedor SSE. `get_hpe_sse_inventory` incorpora el inventario de categorías web/IP y exclusiones SSL del Admin API (contratos de `pyhpesse`), pero no observa qué política se aplica a un appliance ni los logs de decisión; el filtrado real sigue pendiente de laboratorio.
3. Añadir workflows completos para políticas/settings NGFW, asignación de perfiles/firmas IDS y cambios DDoS distintos de habilitar un perfil existente. Se bloquea su escritura automática mientras falta esa validación.
4. Resolver coordinación entre instancias/operadores y persistencia protegida de planes si se requieren remediaciones prolongadas.
5. Continuar los hallazgos previos de host keys SSH, aislamiento del updater privilegiado e inconsistencias del dashboard. No se dan por cerrados por esta batería.
