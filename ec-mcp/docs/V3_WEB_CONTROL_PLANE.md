# ec-mcp 3.0: control plane web y ruta ZTP

La versión `3.0.0b1` establece la base operativa para administrar ec-mcp sin
entrar por SSH al servidor.

## Alcance de esta base

Disponible:

- edición web de las variables admitidas de Orchestrator, SSH opcional,
  seguridad, transporte, panel y updater;
- secretos enmascarados: la API sólo indica si están configurados;
- escritura atómica de `.env` con permisos `600`;
- reinicio solicitado desde la web y ejecutado por un worker separado;
- detección del commit de GitHub en repositorios públicos o privados;
- actualización por commit exacto, únicamente fast-forward;
- respaldo de `.env`, reinstalación, suite de pruebas, reinicio y rollback;
- estados `idle`, `pending`, `running`, `success` y `error`.

Aún no disponible:

- adopción de appliances;
- creación o edición de templates ZTP;
- aplicación de configuración a equipos.

Estas acciones permanecen bloqueadas hasta incorporar preview/diff,
confirmación, auditoría y rollback específicos de EdgeConnect.

## Instalación

Desde el checkout de `APIIntegration/ec-mcp`:

```bash
./scripts/install.sh
./scripts/install_service.sh
./scripts/install_admin_service.sh
```

El último comando instala:

- `ec-mcp-admin.service`: panel ejecutado con el propietario del checkout;
- `ec-mcp-update.timer`: revisa solicitudes cada 20 segundos;
- `ec-mcp-update.service`: worker privilegiado de una sola ejecución.

La UI queda en `http://<IP>:8080` salvo que cambies `EC_ADMIN_HOST` o
`EC_ADMIN_PORT`.

## Primera configuración web

1. Inicia sesión con `EC_ADMIN_PASSWORD`.
2. Abre **Variables**.
3. Configura la URL y autenticación del Orchestrator.
4. Revisa los candados de escritura; deben quedar en `false` salvo una
   ventana de cambio autorizada.
5. Configura transporte, hosts permitidos y bearer token.
6. Pulsa **Guardar y reiniciar servicios**.
7. Comprueba `orchestrator_info` y `run_show_api`.

Un campo secreto vacío conserva el valor existente. Para borrarlo usa
**Eliminar secreto guardado**.

## GitHub privado

En **Variables → Actualizaciones** define:

```dotenv
EC_UPDATE_REPOSITORY=Ryuz-crypto/APIIntegration
EC_UPDATE_BRANCH=main
EC_UPDATE_GITHUB_USER=TU_USUARIO
EC_UPDATE_GITHUB_TOKEN=TU_TOKEN_FINE_GRAINED
```

El token sólo necesita lectura de Contents para el repositorio. No se devuelve
al navegador, no se incluye en `request.json`, no se incrusta en la URL Git y
se elimina del entorno de trabajo al terminar el fetch.

Luego abre **Actualizaciones**, pulsa **Detectar GitHub**, revisa ambos commits,
escribe `ACTUALIZAR <sha-corto>` y confirma.

## Modelo de seguridad del updater

```text
navegador autenticado
        │
        ▼
API admin sin privilegios ── valida lista blanca, repo, rama, SHA y confirmación
        │
        ▼
request.json atómico (sin token)
        │
        ▼
worker systemd ── revalida ── backup ── fast-forward ── pip ── pytest
        │                                                   │
        └──────────────── rollback si falla ◄───────────────┘
```

El worker rechaza:

- repositorios o ramas fuera del formato permitido;
- un repositorio o rama distintos de la configuración activa;
- commits que cambiaron después de la confirmación;
- retrocesos o historial reescrito;
- un checkout con cambios rastreados;
- solicitudes simultáneas.

## Ruta funcional ZTP

El objetivo de la línea 3.0 es:

1. **Discover:** obtener candidatos e identidad desde el Orchestrator.
2. **Template:** elegir una plantilla compatible y completar parámetros
   tipados.
3. **Adoptar:** vincular el appliance con autorización explícita.
4. **Preview/diff:** renderizar la configuración y el impacto antes de escribir.
5. **Confirmar:** exigir una confirmación ligada al appliance, template y hash.
6. **Aplicar:** ejecutar mediante la API del Orchestrator, no mediante SSH.
7. **Verificar/rollback:** health check, auditoría y recuperación.

La base `3.0.0b1` implementa el control plane y el patrón de trabajo seguro
que esas etapas reutilizarán.
