# ec-mcp: MCP server for EdgeConnect SD-WAN

Servidor MCP (Model Context Protocol) que expone un entorno HPE Aruba Networking
EdgeConnect SD-WAN a asistentes de IA (Claude Desktop, Cursor, Le Chat,
ChatGPT, Vibe, etc.).

- **Orchestrator + Appliance (REST)**: ~1550 operaciones por versión (9.3–9.6)
  generadas desde los **OpenAPI oficiales** de HPE Aruba (Orchestrator REST
  APIs, 695 paths; Silver Peak Unity ECOS REST APIs, 388 paths).
- **Appliances (SSH)**: **1367 comandos ECOS** del CLI Reference oficial,
  clasificados por riesgo (monitoreo, troubleshooting, alarmas,
  administración, configuración, negación).
- **Seguridad**: dry-run por defecto en toda operación de escritura, whitelist
  de comandos, kill switch global, salida truncada, y audit log JSONL de cada
  operación (evidencia ISO 27001 / CIS).
- **Transportes**: stdio (Claude Desktop/Cursor) y HTTP streamable / SSE con
  **bearer token obligatorio** y `/health` público, pensado para publicarse
  detrás de TLS o una plataforma ZTNA.

## Herramientas MCP

| Tool | Riesgo | Descripción |
|---|---|---|
| `orchestrator_info` | lectura | Detecta versión del Orchestrator y perfil activo |
| `list_api_operations` | lectura | Lista las ~1550 operaciones API con method, path, params y riesgo |
| `call_read_api` | lectura | Ejecuta una operación GET del perfil (topología, túneles, eventos, stats...) |
| `list_cli_commands` | lectura | Catálogo de los 1367 comandos ECOS oficiales, con filtro por categoría |
| `run_show_command` | lectura | Comando `show` whitelisteado vía SSH |
| `run_cli_command` | según riesgo | Cualquier comando del catálogo ECOS: monitoreo/troubleshooting directo; configuración en dry-run |
| `apply_change` | escritura | Operación API de cambio; dry-run por defecto, requiere `confirm=true` + `EC_ALLOW_WRITE_TOOLS=true` |

Los permisos efectivos son siempre los del usuario autenticado contra el
Orchestrator/appliance; el MCP añade sus capas de control (dry-run, whitelist,
auditoría) pero no los sustituye.

## Requisitos

- Python 3.12+
- Acceso al Orchestrator (API key o usuario/contraseña)
- Para SSH: credenciales de appliance habilitadas

## Instalación

### Linux recién instalado: de cero a funcionar en 4 pasos

**Paso 0 — Prerrequisitos (una sola vez):**

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
```

**Paso 1 — Descargar el proyecto:**

```bash
git clone https://github.com/Ryuz-crypto/APIIntegration.git
cd APIIntegration/ec-mcp
```

**Paso 2 — Instalar el servidor:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Paso 3 — Credenciales reales (los `export` viven solo en esta sesión):**

```bash
export EC_ORCHESTRATOR_URL="https://TU-ORCHESTRATOR-REAL"
export EC_ORCHESTRATOR_API_KEY="TU-API-KEY-REAL"
```

`EC_MCP_AUTH_TOKEN` solo se necesita en el modo HTTP remoto (ver "Uso por HTTP/SSE"); para stdio sáltalo.

**Paso 4 — Conectar tu asistente de IA:** no ejecutas `ec-mcp` a mano; el cliente IA lo lanza por ti. Solo dile dónde vive el servidor. En **Claude Desktop** (Settings → Developer → Edit Config, `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ec-mcp": {
      "command": "/home/TU-USUARIO/APIIntegration/ec-mcp/.venv/bin/ec-mcp",
      "env": {
        "EC_ORCHESTRATOR_URL": "https://TU-ORCHESTRATOR-REAL",
        "EC_ORCHESTRATOR_API_KEY": "TU-API-KEY-REAL"
      }
    }
  }
}
```

Reinicia Claude Desktop y aparecerá "ec-mcp" con sus 7 herramientas. Prueba preguntando: *"¿qué appliances tengo?"*, *"muéstrame los túneles"*, *"ejecuta show system"*.

| Quieres... | Haces... |
| --- | --- |
| Probar que el servidor arranca | `ec-mcp` en la terminal (Ctrl+C para salir) |
| Usarlo desde Claude/Cursor/Le Chat | El JSON del Paso 4 — nada más |
| Exponerlo remoto por ZTNA | `ec-mcp http` + nginx + token (producción) |

### Instalación alternativa con `.env`

```bash
cp .env.example .env       # revisa EC_ORCHESTRATOR_URL y credenciales
set -a; source .env; set +a
```

### Verificación rápida

```bash
python -m pytest tests -q        # 19 tests
ec-mcp                           # arranca en stdio; Ctrl+C para salir
```

## Uso por stdio (Claude Desktop, Cursor)

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "/ruta/a/ec-mcp/.venv/bin/ec-mcp",
      "env": {
        "EC_ORCHESTRATOR_URL": "https://orchestrator.example.com",
        "EC_ORCHESTRATOR_API_KEY": "..."
      }
    }
  }
}
```

**Cursor** — `.cursor/mcp.json`: mismo JSON.

Arranca **read-only** por defecto. Para habilitar operaciones de escritura:
`EC_ALLOW_WRITE_TOOLS=true` (y aun así, cada cambio requiere `confirm=true`).

## Uso por HTTP/SSE (clientes remotos: ChatGPT, Le Chat, agentes)

```bash
# 1. Genera el token (obligatorio; sin él el servidor se niega a arrancar)
export EC_MCP_AUTH_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# 2. Arranca en streamable-HTTP (bind local; se publica vía proxy/ZTNA)
ec-mcp http --host 127.0.0.1 --port 8000

# 3. Verifica
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"ec-mcp"}

curl -X POST http://127.0.0.1:8000/mcp \
  -H "Authorization: Bearer $EC_MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
# → 200 con serverInfo: edgeconnect-sdwan
```

También disponible: `ec-mcp sse` (SSE legacy) y `ec-mcp` (stdio).

### Autenticación

- Cada petición a `/mcp` exige `Authorization: Bearer <EC_MCP_AUTH_TOKEN>`;
  sin token o inválido responde `401` antes de crear cualquier sesión MCP
  (comparación en tiempo constante).
- `/health` es público: para probes de balanceadores y plataformas ZTNA.
- El servidor **se niega a arrancar** en modo `http`/`sse` sin token.

### Publicación detrás de TLS / plataforma ZTNA

El MCP nunca debe exponerse directamente a internet. Publica el bind local a
través de tu reverse proxy con TLS o de tu plataforma ZTNA:

```
ec-mcp (127.0.0.1:8000, bearer) ⇄ Nginx/ZTNA (TLS) ⇄ https://mcp.tu-dominio/mcp
```

Ejemplo de Nginx en [`packaging/nginx/ec-mcp.conf`](packaging/nginx/ec-mcp.conf)
(streaming habilitado, timeouts largos, `/health` público). Requisitos del proxy:

- `proxy_buffering off` — las respuestas SSE/chunked no deben buferizarse.
- Timeouts generosos (las sesiones MCP viven minutos).
- **Mantén el bearer token** aunque el ZTNA autentique al usuario: doble capa.

Configuración del cliente remoto (ChatGPT connectors, Le Chat, otro agente):

```
URL:     https://mcp.tu-dominio/mcp
Headers: Authorization: Bearer <EC_MCP_AUTH_TOKEN>
```

## Instalación como servicio (Ubuntu + systemd)

```bash
# 1. Usuario y código
sudo useradd --system --home /opt/ec-mcp --shell /usr/sbin/nologin ecmcp
sudo mkdir -p /opt/ec-mcp && sudo chown -R ecmcp:ecmcp /opt/ec-mcp
sudo -u ecmcp git clone https://github.com/Ryuz-crypto/APIIntegration.git /tmp/repo
sudo -u ecmcp cp -r /tmp/repo/ec-mcp/* /opt/ec-mcp/
cd /opt/ec-mcp && sudo -u ecmcp python3 -m venv .venv
sudo -u ecmcp .venv/bin/pip install -e .

# 2. Configuración (root-only)
sudo mkdir -p /etc/ec-mcp /var/lib/ec-mcp && sudo chown ecmcp:ecmcp /var/lib/ec-mcp
sudo cp .env.example /etc/ec-mcp/env
sudo $EDITOR /etc/ec-mcp/env        # EC_ORCHESTRATOR_*, EC_MCP_AUTH_TOKEN, EC_MCP_AUDIT_LOG=/var/lib/ec-mcp/mcp-audit.jsonl
sudo chmod 600 /etc/ec-mcp/env && sudo chown root:ecmcp /etc/ec-mcp/env

# 3. Servicio
sudo cp packaging/systemd/ec-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ec-mcp
systemctl status ec-mcp && curl http://127.0.0.1:8000/health
```

El servicio corre con endurecimiento systemd (`NoNewPrivileges`,
`ProtectSystem=strict`, `ProtectHome`) y solo escucha en `127.0.0.1`.

## Configuración (variables de entorno)

Ver [`.env.example`](.env.example) con la referencia completa. Resumen:

| Variable | Default | Descripción |
|---|---|---|
| `EC_ORCHESTRATOR_URL` | — | URL del Orchestrator (obligatoria) |
| `EC_ORCHESTRATOR_API_KEY` | — | API key (o `EC_ORCHESTRATOR_USER`/`PASSWORD`) |
| `EC_VERIFY_TLS` | `true` | Verificar certificados TLS |
| `EC_SSH_ENABLED` | `false` | Habilitar tools SSH |
| `EC_SSH_HOST/USER/PASSWORD/PORT` | — | Credenciales del appliance |
| `EC_ALLOW_WRITE_TOOLS` | `false` | Kill switch global de escritura |
| `EC_MAX_OUTPUT_CHARS` | `12000` | Truncado de respuestas al LLM |
| `EC_MCP_AUDIT_LOG` | `logs/mcp-audit.jsonl` | Audit log JSONL |
| `EC_MCP_AUTH_TOKEN` | — | Bearer token (obligatorio en http/sse) |
| `EC_MCP_HOST/PORT` | `127.0.0.1:8000` | Bind del transporte HTTP |

## Perfiles generados desde los OAS oficiales

Los perfiles incluidos (`9.3`–`9.6`, ~1550 operaciones cada uno) se generaron
a partir de las definiciones OpenAPI **oficiales** publicadas por HPE Aruba en
su developer hub (ReadMe):

- **Orchestrator REST APIs** (695 paths)
- **Silver Peak Unity ECOS REST APIs** (388 paths, appliance level)

Descarga de los OAS (registries de ReadMe):

```bash
python - <<'EOF'
import urllib.request
for name, uuid in [("orchestrator", "s7ggtll0fec04"), ("ecos-appliance", "aspw2wm6k1xidx")]:
    urllib.request.urlretrieve(f"https://dash.readme.com/api/v1/api-registry/{uuid}", f"{name}.json")
EOF

# Regenerar / ampliar perfiles
python -m ec_mcp.import_oas orchestrator.json --version 9.6 --prefix orchestrator --merge-into 9.6
python -m ec_mcp.import_oas ecos-appliance.json --version 9.6 --prefix appliance --merge-into 9.6
```

Cada operación incluye method, path, path/query params, ejemplo de body
derivado del schema y clasificación de riesgo `read`/`write`. Al publicar HPE
un OAS nuevo, basta reimportar con `--merge-into`.

### Colecciones Postman oficiales

Las colecciones oficiales del workspace de HPE Aruba ya están incluidas en
[`api-collections/`](api-collections/) (9.3–9.6) y fusionadas en los perfiles:
cada versión expone ~2000–2250 operaciones únicas (OAS + Postman deduplicadas
por método y ruta). Para reimportar o importar otra colección:

```bash
python -m ec_mcp.import_postman EdgeConnect-Orchestrator.postman_collection.json --version 9.7 --merge-into 9.6
```

## Catálogo CLI ECOS (1367 comandos)

Extraído del **CLI Reference oficial** de HPE Aruba EdgeConnect SD-WAN:

| Categoría | Comandos | Ejecución |
|---|---|---|
| Monitoring (`show ...`) | 85 | Directa (read) |
| Troubleshooting (`ping`, `tcpdump`, `mtr`...) | 8 | Directa (diagnostic) |
| Alarm (`logging ...`) | 5 | Dry-run + confirm |
| Administration (`aaa ...`, `image ...`, `configuration ...`) | 106 | Dry-run + confirm |
| Configuration (`interface ...`, `bgp ...`, `ospf ...`, `nat-map ...`...) | ~240 | Dry-run + confirm |
| Negation (`no ...`) | 135 | Dry-run + confirm |

```
run_cli_command("show interfaces tunnel 1/2")          → ejecuta directo
run_cli_command("ping 10.0.0.1")                       → ejecuta directo
run_cli_command("interface shutdown 1")                → dry-run
run_cli_command("interface shutdown 1", confirm=true)  → ejecuta (requiere EC_ALLOW_WRITE_TOOLS)
```

Comandos fuera del catálogo se rechazan; metacaracteres de shell (`;`, `` ` ``,
`&&`, `$()`) bloqueados; todo queda en el audit log.

## Auditoría

Cada invocación de tool registra en el JSONL: timestamp UTC, tool, acción,
target, resultado, dry-run/real y detalles. Ejemplo de línea:

```json
{"timestamp":"2026-09-29T05:10:01+00:00","tool":"apply_change","action":"appliance.suspend_traffic","target":"/appliance/suspend/3.NE","result":"dry-run","dry_run":true,"details":{"confirmed":false}}
```

## Flujo de trabajo típico

```
1. orchestrator_info          → detecta versión y perfil
2. list_api_operations        → el asistente descubre las operaciones y params
3. call_read_api("orchestrator.topology")
4. run_cli_command("show interfaces tunnel 1/2")
5. apply_change(..., confirm=false)   → dry-run: muestra el cambio exacto
6. apply_change(..., confirm=true)    → lo ejecuta (si el usuario tiene permiso)
```

## Estado y validación

- Tests: 19 (perfiles, whitelist, catálogo, importadores OAS/Postman, auth HTTP en vivo).
- CI: pytest + smoke test stdio en cada push/PR que toque `ec-mcp/`.
- Pendiente: validar paths de escritura contra un Orchestrator real en lab
  antes de habilitar `EC_ALLOW_WRITE_TOOLS` en producción.

## Licencia

Igual que el repositorio contenedor ([LICENSE](../LICENSE)).
