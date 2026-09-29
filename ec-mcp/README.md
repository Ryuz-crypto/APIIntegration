# ec-mcp: MCP server for EdgeConnect SD-WAN

Servidor MCP (Model Context Protocol) que expone un entorno HPE Aruba Networking
EdgeConnect SD-WAN a asistentes de IA (Claude Desktop, Cursor, Le Chat, etc.).

## Componentes

- **Orchestrator (REST)**: operaciones estables (`orchestrator.topology`,
  `orchestrator.inventory.summary`, `appliance.tunnels`, ...) resueltas por
  perfil de compatibilidad 9.3–9.6 (heredado de `DashboardAPI-EC`).
- **Appliances (SSH)**: comandos `show` de ECOS con whitelist de solo lectura.
- **Seguridad**: cambios con dry-run por defecto, whitelist de comandos,
  salida truncada y redactada, audit log JSONL de cada operación.

## Herramientas MCP

| Tool | Riesgo | Descripción |
|---|---|---|
| `orchestrator_info` | lectura | Detecta versión del Orchestrator y perfil activo |
| `list_api_operations` | lectura | Lista operation IDs por versión |
| `call_read_api` | lectura | Ejecuta una operación GET del perfil |
| `list_cli_commands` | lectura | Catálogo de **579 comandos ECOS** del CLI Reference oficial (monitoreo, troubleshooting, alarmas, administración, configuración, negación) |
| `run_show_command` | lectura | Comando `show` whitelisteado vía SSH |
| `run_cli_command` | según riesgo | Cualquier comando del catálogo ECOS: monitoreo/troubleshooting ejecuta directo; configuración/administración en dry-run con `confirm=true` + `EC_ALLOW_WRITE_TOOLS` |
| `apply_change` | escritura | Dry-run por defecto; requiere `confirm=true` y `EC_ALLOW_WRITE_TOOLS`. Soporta path params (`appliance_id`, `group_id`, `interface_name`) y body JSON. Los permisos efectivos son los del usuario autenticado en el Orchestrator |

## Configuración (`.env`)

```
EC_ORCHESTRATOR_URL=https://orchestrator.example.com
EC_ORCHESTRATOR_API_KEY=...           # o EC_ORCHESTRATOR_USER + EC_ORCHESTRATOR_PASSWORD
EC_VERIFY_TLS=true
EC_SSH_ENABLED=false
EC_SSH_HOST=192.0.2.10
EC_SSH_USER=admin
EC_SSH_PASSWORD=...
EC_ALLOW_WRITE_TOOLS=false             # arranca read-only
EC_MCP_AUDIT_LOG=logs/mcp-audit.jsonl
```

## Instalación

```bash
cd ec-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
ec-mcp                                 # stdio (Claude Desktop, Cursor)
ec-mcp serve --transport sse --port 8808  # HTTP/SSE
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "/ruta/a/ec-mcp/.venv/bin/ec-mcp"
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "/ruta/a/ec-mcp/.venv/bin/ec-mcp"
    }
  }
}
```

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
derivado del schema y clasificación de riesgo `read`/`write`. Las versiones
9.3–9.5 usan el mismo OAS oficial (la API documentada del hub cubre ese
rango); al publicar HPE un OAS nuevo, basta reimportar con `--merge-into`.

## Ampliar perfiles con colecciones Postman

El workspace público de Postman de HPE Aruba (oficial) contiene las mismas
APIs en formato colección. Exporta la colección (JSON v2.0/v2.1) e impórtala
como alternativa o complemento:

```bash
python -m ec_mcp.import_postman EdgeConnect-Orchestrator.postman_collection.json --version 9.7 --merge-into 9.6
```

## Operaciones de escritura incluidas

Los perfiles incluyen operaciones de cambio reales (`appliance.interface.set_admin_state`,
`appliance.suspend_traffic`, `policy_group.update`, `appliance.tag.assign`,
`appliance.send_command`, `appliance.reboot`, entre otras). Todas pasan por
`apply_change` con dry-run, whitelist global (`EC_ALLOW_WRITE_TOOLS`) y auditoría;
la autorización final es la del usuario autenticado contra el Orchestrator.

```bash
pip install -e "ec-mcp[mcp]"
python -m ec_mcp.import_postman EdgeConnect-API.postman_collection.json --version 9.7 --merge-into 9.6
```

## Estado

Esqueleto funcional: REST read-only completo, SSH whitelisteado, dry-run de
escritura y auditoría. `apply_change` envía el body JSON cuando `confirm=true`
y `EC_ALLOW_WRITE_TOOLS=true`; probar primero en lab.
