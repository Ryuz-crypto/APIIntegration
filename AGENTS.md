# Registro de fallos en GitHub

Esta regla aplica a cualquier asistente de IA que revise o modifique este repositorio. Es provisional hasta que se publique el criterio definitivo del proyecto.

1. Ante un bug reproducido o un hallazgo técnico accionable, busca primero un issue existente en `Ryuz-crypto/APIIntegration`. Si existe, añade la evidencia nueva allí. Si no existe, crea un issue con la [plantilla de bug](.github/ISSUE_TEMPLATE/bug_report.md). Una sospecha sin reproducción debe identificarse como tal y explicar qué falta validar.
2. El **Bug ID canónico es el número del issue de GitHub** (`#123`). No inventes identificadores locales ni presentes una fila de QA, un comentario o un PR como sustituto del issue. Las claves históricas `SEC-01`, etc., pueden conservarse como referencia adicional.
3. Registra componente, versiones y commit afectados, comportamiento esperado y observado, pasos de reproducción, evidencia saneada, impacto y estado de validación. No publiques tokens, contraseñas, IP internas, datos personales ni payloads sensibles en un issue público. Usa el mecanismo privado de GitHub para vulnerabilidades cuando esté disponible y sea apropiado.
4. En cada PR o commit que corrija un bug, enlaza el issue (`Fixes #123` si el PR cierra el problema; `Refs #123` si solo avanza la investigación). Actualiza el issue con la prueba de corrección y los límites pendientes antes de cerrarlo. Los hallazgos sin resolver permanecen abiertos.
5. Si la IA no tiene permisos o acceso para crear/actualizar el issue, prepara el texto con la plantilla, informa que el registro en GitHub **sigue pendiente** y entrega el enlace solo cuando realmente exista. No afirmes que se reportó ni inventes un Bug ID.

Documentar y corregir un fallo urgente puede hacerse en el mismo trabajo, pero el issue debe quedar vinculado al PR antes de considerarlo cerrado. Esta regla incluye bugs de `ec-mcp`, `DashboardAPI-EC`, instaladores, documentación y pruebas.
