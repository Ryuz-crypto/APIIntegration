# Seguridad y respuesta ante exposición de secretos

Este repositorio no debe contener secretos reales, datos de clientes, direcciones internas, claves privadas ni tokens de acceso, incluidos ejemplos de OpenAPI, colecciones, pruebas, documentación y archivos de CI.

## Antes de confirmar cambios

- Usa valores sintéticos y claramente no utilizables: `<redacted>`, `example.invalid` o identificadores ficticios.
- No copies encabezados `Authorization`, cookies, API keys, certificados, claves privadas ni respuestas obtenidas de equipos reales.
- Revisa los cambios antes de subirlos y ejecuta Gitleaks localmente con la configuración del repositorio.
- No se permite añadir excepciones, allowlists o reducir el alcance del escaneo para ocultar una detección sin una revisión de seguridad documentada.

## Si se detecta una posible exposición

1. **Revoca o rota inmediatamente** la credencial, incluso si el repositorio es privado.
2. Abre o actualiza un issue con evidencia saneada. Nunca pegues el valor expuesto, su hash, una captura sin redacción ni un payload completo.
3. Sustituye el valor en el árbol actual por un ejemplo sintético.
4. Reescribe todas las referencias editables afectadas con `git-filter-repo` o una herramienta equivalente. Incluye ramas, etiquetas y forks bajo control del equipo.
5. Comprueba el historial reescrito con Gitleaks y registra los SHA iniciales/cambiados sin repetir valores sensibles.
6. Si GitHub conserva referencias internas de pull requests históricos (`refs/pull/*`) u objetos inaccesibles para administradores, solicita a GitHub Support la purga de datos sensibles. Indica repositorio, PR afectados, los primeros commits cambiados y cualquier objeto LFS huérfano.
7. Informa a colaboradores que deben volver a clonar o seguir el procedimiento de limpieza indicado por `git-filter-repo`.

## Regla de CI

Gitleaks debe mantenerse como control preventivo de historial y contenido. Una ejecución fallida por referencias internas históricas se documenta y se eleva a GitHub Support; no se soluciona reduciendo silenciosamente el alcance del análisis.

### Excepción documentada (refs #85, aprobada por el propietario, 2026-10-25)

El commit histórico `ad8e66b` contiene ejemplos sintéticos con formato de credencial y es ancestro de `main`; las referencias internas `refs/pull/*` de GitHub no son editables mediante force-push. Con autorización explícita del propietario y la decisión de no recurrir a GitHub Support, el escaneo de CI se define así:

1. **Contenido actual**: `gitleaks dir .` analiza el snapshot completo del repositorio en cada ejecución. Debe pasar siempre: un hallazgo aquí es un secreto en el árbol vigente.
2. **Historial incremental**: `gitleaks git --log-opts="<rango>"` analiza únicamente los commits nuevos que introduce cada push o pull request respecto a su base. Un secreto introducido por un cambio nuevo sigue bloqueando ese cambio.
3. Los 159 hallazgos históricos de #85 no se ocultaron con allowlist: permanecen clasificados en el issue como ejemplos sintéticos sin credenciales reales, y el snapshot vigente (`apiDocs.json`, `edgeconnect-10.0.json`) sustituye los valores por variables (`$EC_API_TOKEN`) o marcadores (`<CLIENT_KEY>`).

Esta excepción no habilita secretos reales: toda detección en contenido nuevo o en commits nuevos se trata según la sección «Si se detecta una posible exposición». Si el proyecto decide después purgar el historial vía GitHub Support, se retira esta excepción y se restaura el escaneo de historial completo.

## Divulgación responsable

Para una vulnerabilidad activa o una exposición de alto impacto, usa el canal privado de seguridad de GitHub cuando esté habilitado. Si no lo está, limita el issue a metadatos saneados y coordina la información sensible mediante un canal privado autorizado.
