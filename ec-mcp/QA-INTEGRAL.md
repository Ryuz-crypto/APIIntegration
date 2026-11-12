# Batería integral de aceptación — SD-WAN, SSE y Aruba Central

Estado: **plantilla; ninguna prueba se considera ejecutada por existir este documento**.

## Preparación

Registrar fecha UTC, responsable, entorno, versión, SHA completo esperado y servido, transporte, perfil y alcance. Identificar cada Orchestrator, tenant SSE y cuenta/región Central mediante alias saneados. Registrar límites de API, permisos y ventanas. No incluir tokens, contraseñas, IP internas ni datos personales.

Por defecto todas las pruebas son de lectura. Las pruebas de escritura se ejecutan únicamente con mocks; una prueba real de escritura requiere autorización separada y un plan de reversión. No desactivar servicios ni borrar auditoría durante la batería.

## Registro por prueba y destino

| Campo | Valor |
| --- | --- |
| ID y objetivo | |
| Alias del destino y plataforma | |
| Versión/SHA y fecha UTC | |
| Tool y parámetros saneados | |
| Resultado esperado y criterio | |
| Resultado observado y evidencia saneada | |
| PASS / FAIL / BLOCKED / NOT RUN | |
| Limitaciones, error y seguimiento | |

PASS exige evidencia del resultado y comparación con una fuente independiente autorizada; una llamada sin error por sí sola no prueba que los datos sean correctos. Conservar errores y respuestas parciales saneadas. Marcar BLOCKED cuando falten permisos o conectividad, sin inferir éxito.

## T0 — Identidad y salud

T0.1 Verificar versión y SHA servido contra los aprobados.  
T0.2 Verificar salud y autenticación MCP, acceso denegado sin credenciales y expiración.  
T0.3 Obtener catálogo servido; confirmar disponibilidad y estado de tools para cada plataforma.

## T1 — SD-WAN, repetir por Orchestrator

T1.1 Descubrir destinos y seleccionar explícitamente el alias; comprobar que no se cruza información entre destinos.  
T1.2 Consultar identidad y versión; comparar con el Orchestrator.  
T1.3 Listar appliances y contrastar una muestra autorizada de identificadores y estado.  
T1.4 Consultar alarmas, WAN y túneles disponibles; contrastar una muestra y su marca de tiempo.  
T1.5 Simular respuesta vacía, 401/403, timeout y destino desconocido; verificar clasificación y ausencia de secretos.

## T2 — SSE, repetir por tenant

T2.1 Listar destinos y verificar selección explícita y aislamiento.  
T2.2 Consultar salud y datos de inventario de solo lectura disponibles; contrastar con la consola correspondiente.  
T2.3 Verificar token inválido o sin permiso mediante mock, sin mostrarlo en errores o auditoría.  
T2.4 Comprobar paginación y respuestas vacías cuando el endpoint las admita.

## T3 — Aruba Central, repetir por cuenta y región

T3.1 Listar destinos y validar selección explícita, región y aislamiento.  
T3.2 Verificar autenticación y renovación con mocks; contrastar inventario y estado de solo lectura con la consola autorizada.  
T3.3 Simular token vencido, 401/403, límite 429 y timeout; verificar errores y manejo de reintentos documentado.  
T3.4 Validar paginación, datos incompletos y respuestas vacías con fixtures.

## T4 — Seguridad y auditoría

T4.1 Verificar roles, límite de intentos y caducidad de sesión; registrar configuración de workers y sus límites.  
T4.2 Comprobar que secretos no aparecen en respuestas, errores, logs ni exportaciones con valores sintéticos.  
T4.3 Verificar IDs, actor cuando esté realmente autenticado, acción, destino, resultado y UTC. Marcar desconocidos explícitamente.  
T4.4 Exportar evidencia saneada y verificar su alcance. Una huella sin firma ni anclaje independiente no demuestra no repudio.  
T4.5 En entorno aislado, probar fallos de auditoría, restauración de backups y conservación de archivos rotados.

## T5 — Cambios solo con mocks

T5.1 Verificar configuración de escritura deshabilitada y rechazo sin autorización.  
T5.2 Para cada plataforma compatible, ejecutar preview/dry-run con mocks y comprobar que no hay tráfico de escritura real.  
T5.3 Simular confirmación, fallo parcial y reversión con mocks; verificar auditoría y estado final.  
T5.4 Simular destino deshabilitado, último destino, fallback global y reinicio; verificar que ningún destino no autorizado se selecciona silenciosamente.

## T6 — Operación y entrega

T6.1 Comprobar reinicio y recuperación en laboratorio; verificar versión, configuración, identidad y conectividad después.  
T6.2 Comprobar roles, filtros, estados y legibilidad del panel en escritorio y móvil.  
T6.3 Registrar límites de cobertura por destino, incidentes, bloques y pruebas no ejecutadas.  
T6.4 Emitir decisión de aceptación con responsables; CI verde no sustituye las pruebas reales ni constituye por sí solo aprobación de producción.
