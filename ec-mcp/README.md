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
| `run_show_command` | lectura | Comando `show` ECOS whitelisteado vía SSH |
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

## Ampliar perfiles con colecciones Postman

El workspace público de Postman de HPE Aruba (oficial) contiene las APIs de
EdgeConnect SD-WAN. Exporta la colección (JSON v2.0/v2.1) e impórtala:

```bash
# Perfil nuevo
python -m ec_mcp.import_postman EdgeConnect-Orchestrator.postman_collection.json --version 9.7
# O fusionar con un perfil existente
python -m ec_mcp.import_postman EdgeConnect-Orchestrator.postman_collection.json --version 9.7 --merge-into 9.6
```

El importador detecta method, path, path/query params, ejemplos de body y
clasifica riesgo `read`/`write` automáticamente.

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
