#!/usr/bin/env bash
# Autodetecta los appliances registrados en el Orchestrator y prueba si el
# puerto SSH (22) es alcanzable desde este servidor. No modifica nada.
# Requiere .env con EC_ORCHESTRATOR_URL y EC_ORCHESTRATOR_API_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "    detect: no existe .env" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

python - <<'EOF'
import os
import socket
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:
    os.system("pip install -q python-dotenv >/dev/null 2>&1")
    from dotenv import dotenv_values

env = dotenv_values(Path(".env"))
for key in ("EC_ORCHESTRATOR_URL", "EC_ORCHESTRATOR_API_KEY", "EC_ORCHESTRATOR_USER"):
    os.environ.setdefault(key, env.get(key) or "")

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.config import Settings
from ec_mcp.orchestrator_client import OrchestratorClient

try:
    settings = Settings.from_env()
    engine = CompatibilityEngine(load_profiles(settings.profiles_dir))
    client = OrchestratorClient(settings, engine)
    appliances = client.list_appliances()
except Exception as error:
    print(f"    detect: error consultando el Orchestrator: {error}")
    raise SystemExit(1)

if not appliances:
    print("    detect: el Orchestrator no reporta appliances")
    raise SystemExit(1)

print(f"    Encontrados {len(appliances)} appliances:")
for index, appliance in enumerate(appliances, 1):
    ne_pk = appliance.get("nePk") or "?"
    name = appliance.get("name") or "?"
    ips = [appliance.get("ip")] + [appliance.get("lan_ip")] + (appliance.get("wan_ips") or [])
    ips = [ip for ip in ips if ip]
    reachable = ""
    for ip in ips[:3]:
        try:
            with socket.create_connection((str(ip), 22), timeout=2):
                reachable = f"SSH OK ({ip})"
                break
        except OSError:
            continue
    if not reachable:
        reachable = "SSH inalcanzable desde este servidor"
    print(f"      {index}. {name}  [{ne_pk}]  {' / '.join(map(str, ips[:3])) or 'sin IP'}  -> {reachable}")
print("    Los hosts se resuelven automaticamente en cada consulta SSH;")
print("    no necesitas configurar IP fija por appliance.")
EOF
