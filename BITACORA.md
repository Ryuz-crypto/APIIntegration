# Bitácora de bugs — control de cambios

Registro cronológico de los bugs detectados durante el desarrollo de `ec-mcp` (y componentes asociados). Cada fila usa como **Bug ID canónico el número del issue de GitHub** (regla de [AGENTS.md](AGENTS.md) y [README.md](README.md)); las claves históricas (`BUG-01`, `B.7`, `T4`, `D1`–`D5`) se conservan como referencia. Detalle completo (reproducción, evidencia, impacto) en cada issue.

Los issues se registraron de forma retroactiva a partir de la evidencia documentada en los PRs de corrección; el estado indica la situación del fallo, no la del registro.

| Bug ID | Clave histórica | Componente | Resumen | Corregido en | Estado |
|---|---|---|---|---|---|
| [#39](https://github.com/Ryuz-crypto/APIIntegration/issues/39) | — | Documentación | Conteos de pruebas desactualizados y contradictorios en READMEs y QA-SECURITY | [PR #38](https://github.com/Ryuz-crypto/APIIntegration/pull/38) | Abierto hasta integrar PR #38 |
| [#40](https://github.com/Ryuz-crypto/APIIntegration/issues/40) | — | `ec-mcp` consola | Entry point de consola ignoraba `http`/`sse` y siempre corría stdio | [PR #10](https://github.com/Ryuz-crypto/APIIntegration/pull/10) | Corregido |
| [#41](https://github.com/Ryuz-crypto/APIIntegration/issues/41) | BUG-01 (T1) | `ec-mcp` | Parser de inventario aceptaba respuesta vacía como el fleet | [PR #12](https://github.com/Ryuz-crypto/APIIntegration/pull/12) | Corregido |
| [#42](https://github.com/Ryuz-crypto/APIIntegration/issues/42) | BUG-02 (T2) | `ec-mcp` | `resolve_ne_pks` no reconocía `appliance_id:'all'`; fan-out y agregación de alarmas rotos | [PR #12](https://github.com/Ryuz-crypto/APIIntegration/pull/12) | Corregido |
| [#43](https://github.com/Ryuz-crypto/APIIntegration/issues/43) | T4 strict runner | `ec-mcp` | Runner inyectaba `nePk` y exigía `granularity` a operaciones que no los declaran | [PR #12](https://github.com/Ryuz-crypto/APIIntegration/pull/12) | Corregido |
| [#44](https://github.com/Ryuz-crypto/APIIntegration/issues/44) | B.7 (T6) + D5 | `ec-mcp` | Credenciales y secretos compuestos (`presharedkey_sha384`) sin redactar en payloads | [PR #12](https://github.com/Ryuz-crypto/APIIntegration/pull/12), [PR #15](https://github.com/Ryuz-crypto/APIIntegration/pull/15) | Corregido |
| [#45](https://github.com/Ryuz-crypto/APIIntegration/issues/45) | T3/D4 | `ec-mcp` | Payloads KPI anidados superaban el presupuesto de 12k y llegaban truncados; proyección con `fields` devolvía filas vacías | [PR #14](https://github.com/Ryuz-crypto/APIIntegration/pull/14), [PR #17](https://github.com/Ryuz-crypto/APIIntegration/pull/17) | Corregido |
| [#46](https://github.com/Ryuz-crypto/APIIntegration/issues/46) | — | `ec-mcp` | Preflight de un solo appliance bloqueaba el fan-out `all` para ops con `nePk` requerido | [PR #16](https://github.com/Ryuz-crypto/APIIntegration/pull/16) | Corregido |
| [#47](https://github.com/Ryuz-crypto/APIIntegration/issues/47) | — | `ec-mcp` SSH | Autenticación SSH keyboard-interactive fallaba en banner/prompts (ECV-Calimaya) | [PR #18](https://github.com/Ryuz-crypto/APIIntegration/pull/18), [PR #19](https://github.com/Ryuz-crypto/APIIntegration/pull/19), [PR #20](https://github.com/Ryuz-crypto/APIIntegration/pull/20) | Corregido |
| [#48](https://github.com/Ryuz-crypto/APIIntegration/issues/48) | — | `ec-mcp` | CLI de appliance se enviaba directo a `/gms/rest/cli` en lugar del proxy `/appliance/rest` | [PR #21](https://github.com/Ryuz-crypto/APIIntegration/pull/21) | Corregido |
| [#49](https://github.com/Ryuz-crypto/APIIntegration/issues/49) | — | `ec-mcp` | `run_show_api` fallaba con `Extra data` en respuestas CLI de texto plano | [PR #23](https://github.com/Ryuz-crypto/APIIntegration/pull/23) | Corregido |
| [#50](https://github.com/Ryuz-crypto/APIIntegration/issues/50) | — | `ec-mcp` admin | Throttle del login impedía entrar con contraseña correcta durante el bloqueo y no limpiaba fallos | [PR #27](https://github.com/Ryuz-crypto/APIIntegration/pull/27) | Corregido |
| [#51](https://github.com/Ryuz-crypto/APIIntegration/issues/51) | — | instalador admin | `install_admin_service.sh` sobrescribía `EC_ADMIN_PORT` del `.env` en cada reinstalación | [PR #28](https://github.com/Ryuz-crypto/APIIntegration/pull/28) | Corregido |
| [#52](https://github.com/Ryuz-crypto/APIIntegration/issues/52) | — | `ec-mcp` admin | Badge de versión del panel hardcodeado (`3.0.0b1 · BASE ZTP`) | [PR #33](https://github.com/Ryuz-crypto/APIIntegration/pull/33) | Corregido |
| [#53](https://github.com/Ryuz-crypto/APIIntegration/issues/53) | — | `ec-mcp` writes | `POST /deployment` full-REPLACE sin guard: cuerpos confirmados incompletos borraron las interfaces de EC3 (incidente en vivo) | [PR #34](https://github.com/Ryuz-crypto/APIIntegration/pull/34) | Corregido |
| [#54](https://github.com/Ryuz-crypto/APIIntegration/issues/54) | P0 (skill v22) | `ec-mcp` writes | `apply_change` rechazaba bodies array declarados por el catálogo (`postinterfacelabels288`); writes ok sin efecto y sin read-after-write | [PR #36](https://github.com/Ryuz-crypto/APIIntegration/pull/36) | Corregido |
| [#55](https://github.com/Ryuz-crypto/APIIntegration/issues/55) | P0 ZTP | `ec-mcp` ZTP | Creación de preconfig enviaba `configData` en vez de `preConfig`; `rollback_ztp_plan` denegaba por UUID en vez del id numérico | [PR #37](https://github.com/Ryuz-crypto/APIIntegration/pull/37) | Corregido |
| [#56](https://github.com/Ryuz-crypto/APIIntegration/issues/56) | — | `ec-mcp` auditoría | Auditoría de `apply_change` no manejaba cuerpos JSON tipo lista | [PR #37](https://github.com/Ryuz-crypto/APIIntegration/pull/37) (commit `63eeca8`) | Corregido |

## Pendientes fuera de un Bug ID propio

- Rate-limit 429 semántico con `retry_after` para el orquestador (documentado en el [PR #36](https://github.com/Ryuz-crypto/APIIntegration/pull/36)): requiere reproducción contra el orquestador antes de abrir issue.
- Endurecimiento SSH/updater e inconsistencias del dashboard: línea de trabajo `fix/operation-integrity-4.5` ([PR #38](https://github.com/Ryuz-crypto/APIIntegration/pull/38)).
