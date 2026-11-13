# Versiones de mantenimiento / Maintenance versions

Cada entrega de correcciones recibe un parche nuevo: 9.6.1, 9.6.2, 9.6.3. No se cambia la versión al guardar configuración en el panel.

Desde ec-mcp:
```bash
python scripts/bump_patch.py
python scripts/bump_patch.py --write
```

El primer comando muestra los archivos que cambiarían; el segundo los escribe. Revisa el diff, ejecuta CI y la batería aplicable, y documenta el SHA aprobado antes de crear una etiqueta o release. El script no publica ni instala el release. Las sustituciones en README y plantillas deben revisarse para no alterar referencias históricas o versiones de firmware.

Each maintenance delivery gets a new patch version. Configuration saves do not change the package version. Run the commands above from ec-mcp: the first previews changes, the second writes them. Review the diff, run CI and applicable acceptance tests, and record the approved SHA before tagging a release. The script does not publish or install a release. Review documentation replacements to preserve historical and firmware references.

## Traducciones / Localization

9.6.1 completa las claves de los nueve catálogos y comprueba los parámetros de formato. Los identificadores de API, nombres propios y textos de confirmación exigidos por el servidor pueden permanecer literales. La paridad de claves no garantiza por sí sola calidad lingüística ni cubre mensajes de backend y texto codificado directamente en vistas. El seguimiento completo permanece en #169.

9.6.1 completes keys in all nine catalogs and validates formatting placeholders. API identifiers, proper names and server-required confirmation strings may remain literal. Key parity alone does not establish linguistic quality or cover backend messages and hard-coded view text. Full localization remains tracked in #169.
