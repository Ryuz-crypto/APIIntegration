# Hoja de ruta operativa de ec-mcp

Seguimiento: #88

## Resultado esperado

ec-mcp debe responder consultas operativas de forma rápida, predecible y segura; el panel debe mostrar información verificable y las acciones administrativas deben quedar confirmadas y auditadas. La IA puede detectar, correlacionar y proponer remediaciones, pero no aplicar políticas ni reiniciar servicios sin aprobación explícita.

## Fase 1 — consultas y SSH fiables

- Contrato común de respuesta: resultado, fuente, tiempo, truncamiento y error normalizado.
- Límites de consulta y paginación para que una respuesta grande no bloquee el servidor MCP.
- Reintentos limitados para fallos SSH transitorios, con timeout configurable y diagnóstico de ruta LAN/WAN.
- Reutilización de conexiones solo dentro de la solicitud; nunca reutilizar una sesión autenticada entre identidades.
- Métricas y auditoría de latencia, reintentos, transporte y resultado, sin secretos.

Criterio de aceptación: una consulta read-only devuelve un resultado acotado o un error accionable; no queda una conexión SSH abierta después de terminar.

## Fase 2 — panel de administración y servicios

- El panel consume estado real de API, base de datos, worker y actualización; no debe presentar `ready` si el servicio no fue comprobado.
- Las acciones de reinicio se modelan como solicitudes: prevalidación, confirmación escrita, identificador de operación y estado consultable.
- La ejecución se limita a una allowlist de servicios y se registra en auditoría.
- No se aceptan comandos de shell arbitrarios desde HTTP.

Criterio de aceptación: el panel puede mostrar la última comprobación y seguir una solicitud de servicio sin exponer credenciales ni bloquear la interfaz.

## Fase 3 — detección y remediación asistida

- Correlacionar IDS/IPS, DDoS, alarmas, firewall, túneles y reputación de tráfico.
- Emitir una propuesta de remediación con evidencia, alcance, riesgo, reversión y una política candidata.
- Toda propuesta es `dry_run` inicialmente. Para aplicar un cambio se requieren permisos de escritura, confirmación humana y una política permitida.
- Las acciones de alto impacto (aislar zona, cambiar rutas, reiniciar, modificar ACL/IDS) requieren confirmación reforzada y un plan de reversión.

Criterio de aceptación: la IA puede explicar por qué recomienda una acción y qué exacto cambio se realizaría, sin ejecutar cambios por sí misma.

## Plantillas de políticas iniciales

1. **Observación**: solo recopila y correlaciona señales.
2. **Contención propuesta**: sugiere clasificación/bloqueo temporal, nunca aplica.
3. **Cambio controlado**: permite una operación preaprobada para un alcance definido, con ventana, confirmación y reversión.
4. **Emergencia**: reservada a operadores autorizados; registra justificación, evidencia y revisión posterior.

## Prohibiciones

- No habilitar SSH expuesto a WAN automáticamente.
- No aceptar comandos arbitrarios desde el panel o una herramienta MCP.
- No desactivar ni reducir validaciones de seguridad para acelerar una acción.
- No guardar tokens, contraseñas o datos de producción en ejemplos, auditorías o respuestas.

