# EdgeConnect Advanced Troubleshooting Catalog (GENÉRICO)

Enumeración de dominios de troubleshooting avanzado para HPE Aruba EdgeConnect SD-WAN, anclada a las operation IDs estables del catálogo del MCP (perfiles 9.3–9.6) y a las herramientas MCP compuestas. **Aplicable a cualquier despliegue EdgeConnect**; sin datos de laboratorio. Ambiente específico: `EDGECONNECT_LAB_ENV.md` / skill `edgeconnect-lab-env`.

Convenciones:
- `TOOL:` = herramienta MCP compuesta (un llamado, orquesta varias APIs)
- `OP:` = operation ID del catálogo, ejecutable vía `call_read_api` (read) o `apply_change` (write, dry-run por defecto)
- Toda ventana de tiempo: verificar por endpoint (alarmas usan epoch ms; IDS/IPS epoch secs; stats aggregate epoch ms)
- Siempre iniciar con `list_appliances` + `orchestrator_info` para resolver nePks y perfil activo

---

## Dominio 1 — Triage inicial (¿qué está mal y dónde?)

**Síntomas típicos**: "el sitio X no reporta", "usuarios reportan lentitud", "no sé por dónde empezar".

| Check | Cómo | Interpretación |
|---|---|---|
| Inventario y estado global | `TOOL: list_appliances` | `state` ≠ aprobado/activo = problema de adopción, no de red |
| Versión/perfil del orquestador | `TOOL: orchestrator_info` | Perfil activo determina qué ops existen; ECOS vs Orchestrator version mismatch causa desync de config |
| Conteo de alarmas | `TOOL: get_active_alarms(appliance_id="all")` | Empezar por el appliance con mayor severidad crítica/mayor |
| Detalle de alarmas | `OP: orchestrator.alarmappliancegetpost9` (POST query-with-body: from/to epoch ms, severity, view) | El `/alarm/gms` de detalle NO acepta view/severity — contrato conocido |
| Salud integral por appliance | `TOOL: get_security_posture(appliance_id)` | IDS/IPS + DDoS + zone matrix + tunnel health + findings priorizados en una llamada |
| Availability de túneles | `OP: orchestrator.stats_aggregate_availability600` (date, granularity, nePk, overlayId) | % disponibilidad por túnel/overlay |

**Regla**: no bajar a dominios específicos hasta tener alarmas + posture. El 80% de los casos se resuelve con dominio 1 + un dominio puntual.

---

## Dominio 2 — Flujos (Flow Monitoring)

**Síntomas**: "la app X va lenta", "no sé qué tráfico consume el enlace", "algo está bloqueado".

| Check | Cómo | Interpretación |
|---|---|---|
| Top talkers agregados | `TOOL: get_top_talkers(start_time, end_time, limit)` — detrás: `OP: orchestrator.stats_aggregate_toptalkers654` | Epoch **ms**; vacío ≠ error (lab sin tráfico) |
| Flujos con filtro | `OP: orchestrator.flows242` (nePk, application, ip1/ip2, zone1/zone2, vrf1/vrf2, port1/port2, protocol, overlays, maxFlows) | El filtro combina AND; usar maxFlows para acotar |
| Detalle de un flujo | `OP: orchestrator.flowdetails238` (id, nePk, seq) | `id` = Flow-ID, el mismo que aparece en el security log |
| Ancho de banda por flujo | `OP: orchestrator.flowbandwidthstats237` (id, nePk, seq) | RX/TX octetos del flujo |
| Logs de firewall con Action/Flow-ID | `TOOL: get_security_log(appliance_id, log_type="Firewall", date, lines)` — detrás: `OP: appliance.getlogfile458377` (`/logViewer/{logType}/{date}/{lines}`) | `Action:drop` + `Reason:Policy drop` = política de zona (→ dominio 4); drop con "interface is down" = conectividad (→ dominio 6) |
| Flujos lentos | `OP: orchestrator.flows242` con `anytimeSlowFlows=true` | Filtra flujos que degradaron el path selection |

**Correlación clave**: Flow-ID aparece en `flowdetails`, `get_security_log` y `flowbandwidthstats` — es la llave universal para unir "la app X" con "permitido/bloqueado" y "cuánto consumió".

---

## Dominio 3 — Túneles y overlay

**Síntomas**: "túnel caído", "voz degradada", "brownouts", "MOS bajo".

| Check | Cómo | Interpretación |
|---|---|---|
| Estado de túneles | `TOOL: get_tunnel_state(appliance_id)` — detrás: `OP: appliance.tunnelsconfigandstate741932` (state param) | `status` operacional; distinguir admin-down de down real |
| Túneles site-to-site + VGW | `TOOL: get_site_to_site_tunnels(appliance_id)` | Incluye bonded y third-party/SSE |
| Latencia/jitter/loss/MOS por túnel | `TOOL: get_wan_health(appliance_id, fields=...)` | **Pasar `fields`** o se trunca; MOS ×100 (440 = 4.40). MOS < 350 = voz degradada |
| Brownout/blackout | `TOOL: get_brownout_state(appliance_id)` | Devuelve el reason del brownout — causa raíz directa |
| Excepciones de túnel | `OP: orchestrator.tunnelexceptionget230` | Túneles con comportamiento anómalo persistente |
| Traceroute bajo túnel | `OP: orchestrator.initiatetraceroute883` (id) → `OP: orchestrator.traceroutestate884` (id) para poll | El `id` es del túnel físico; el resultado muestra el hop que falla |
| NAT-D | `get_tunnel_state` — campo Discovered | `NONE:NONE` = nunca llegó paquete NAT-D del remoto → validar transporte/firewall entre ambos EC (no es problema de config EC) |
| Health period summaries | `OP: orchestrator.jitterperiodsummary410` / `latencyperiodsummary411` / `lossperiodsummary412` / `mosperiodsummary413` | Tendencia histórica del período — distingue incidente puntual de degradación crónica |

**Regla**: túnel down → primero brownout reason y tunnel_state admin/oper, después traceroute bajo el túnel caído.

---

## Dominio 4 — Seguridad e incidentes

**Síntomas**: "¿nos están atacando?", "tráfico bloqueado que debería pasar", "revisión SOC".

| Check | Cómo | Interpretación |
|---|---|---|
| Postura integral | `TOOL: get_security_posture(appliance_id)` | Snapshot único: IDS/IPS + DDoS + zone matrix + tunnels + findings priorizados |
| Log de seguridad (allow/drop/inspect) | `TOOL: get_security_log(appliance_id, log_type="Firewall", date, lines, summarize=true)` | Summary con actions, drop_reasons, zone_pairs, top_applications. `Policy drop` → revisar el par de zonas en el zone matrix |
| Otros logs del Log Viewer | `OP: appliance.getlogfile458377` con logType Alarm\|Audit\|Event | Alarm = eventos de alarma crudos; Audit = cambios de config (quién/cuándo); Event = sistema |
| Eventos IDS/IPS | `TOOL: get_ids_ips_events(appliance_id, start_time, end_time)` — detrás: `OP: appliance.getidsipsevents189513` | Epoch-secs; vacío = sin detecciones (no error) |
| Estado IDS/IPS | `TOOL: get_ids_ips_state` — detrás: `OP: appliance.getidsipsstate405371` | "Enabled, EC Not Licensed" = falta feature license, no es config |
| Zone matrix | `TOOL: get_zone_matrix(appliance_id)` — detrás: `OP: appliance.getallzones257534` + `appliance.securitymapsget832281` | Pares zona→zona **sin política explícita** = hallazgo a revisar |
| DDoS | `OP: appliance.thresholdstatusget574729` + `OP: appliance.protectionprofilesget574729` (o `TOOL: get_ddos_status`) | Threshold status = si está bajo ataque activo |
| Reputación web/IP en el firewall log | Campos `WebCategory`/`WebReputation`/`SrcIPReputation`/`DstIPReputation` de `get_security_log` | Poblados = NSS/SWS activo; categoría bloqueada = filtrado de contenido trabajando |

**Flujo de incidente**: `get_security_posture` (detectar) → `get_security_log` (evidencia con Flow-ID) → `get_zone_matrix` (¿qué política causó el drop?) → fix vía `apply_change` sobre security maps → re-verificar con `get_security_log`.

---

## Dominio 5 — Routing (BGP/OSPF/rutas)

**Síntomas**: "rutas faltantes", "asimetría", "subred no alcanza el otro sitio".

| Check | Cómo | Interpretación |
|---|---|---|
| BGP state | `OP: orchestrator.bgpstate145` (nePk) / `OP: orchestrator.allvrfsbgpstate144` (allVrfs) | Neighbor down + uptime reiniciándose = flapping |
| BGP neighbors + BFD | `TOOL: get_bgp_neighbors(appliance_id)` — detrás: `OP: orchestrator.getneighbor142` | BFD down detecta antes que BGP timers |
| OSPF | `OP: orchestrator.ospfstateobj490` (system) / `orchestrator.ospfneighborsstateobj489` (neighbors) / `orchestrator.getinterfaceconfigdta483` (interfaces) | Full state esperado en neighbors; 2-Way/DOWN = problema |
| Rutas del appliance | `OP: appliance.networkroutesget73060` (`/networkRoutes`) | Tabla completa; comparar contra lo esperado por segment/VRF |
| Ruta preferida | `OP: appliance.findpreferredroute141733` | Qué path elegiría el EC para un destino |
| Route map dependencies | `OP: appliance.routemapdependency692870` (name) | Antes de tocar un route map, saber qué depende de él |
| Multicast | `OP: orchestrator.multicastroutestateget467` (routes) / `orchestrator.multicastinterfacestateget465` (interfaces) | PIM state por interfaz |

---

## Dominio 6 — LAN/WAN, interfaces y servicios

**Síntomas**: "interface down", "DHCP no asigna", "duplex mismatch", "NAT raro".

| Check | Cómo | Interpretación |
|---|---|---|
| Config de despliegue LAN/WAN | `TOOL: get_deployment_config(appliance_id)` — detrás: `OP: appliance.deployment729344` | Addressing, labels, zonas, firewallMode por interface. **Nunca POSTear deployment completo sin modoIfs/sysConfig** (peligro full-REPLACE documentado) |
| Estado de interfaces | `OP: orchestrator.interfacestate423` / `OP: appliance.interfaces` | Errores, duplex, oper status real |
| ARP/ND | Proxy: `OP: orchestrator.appliancegetapi70` con `url=/neighbors` | `/arpTable`, `/macTable`, `/fdb` NO existen (404) — contrato conocido |
| DHCP leases | `OP: appliance.dhcpdleases559133` (`/dhcpd/leases` nativo) | El orchestrator `/dhcpConfig/leases` da 400 — usar el nativo |
| DHCP config | `OP: appliance.dhcpdconfig735985` | server vs relay; serverConfig.startIp/endIp |
| Port profiles | `OP: orchestrator.portprofilesget500` | Speed/duplex forzados vs auto |

---

## Dominio 7 — Diagnóstico profundo (capturas y evidencia)

**Síntomas**: "necesito ver paquetes", "dame evidencia para HPE TAC", "prueba de integridad del enlace".

| Check | Cómo | Interpretación |
|---|---|---|
| TCPDump | `OP: orchestrator.tcpdump_run737` (run) → `orchestrator.tcpdump_status738` (poll) → appliance stop/download (`appliance.tcpdump_stop927032`, `appliance.tcpdump_download581121`) | Flujo run → poll status → download; la captura queda en el appliance |
| Link integrity test | `OP: appliance.link_integrity_test_run790835` → `appliance.link_integrity_test_status188430` (poll) → `appliance.link_integrity_test_stop226191` | Prueba de inyección de pérdida en un enlace (ventana de mantenimiento) |
| Sysdump / debug files | `OP: appliance.generatesysdump69159` (generate) → `appliance.statusgeneratingsysdump847152` (poll) → `OP: orchestrator.debugfiles215` (list) → download | Evidencia completa para TAC; pesado — solo cuando el triage no basta |
| Log Viewer nativo | `OP: appliance.getlogfile458377` (logType Firewall/Alarm/Audit/Event) | Evidencia en texto plano sin generar dump |
| Rango de fechas disponible | `OP: appliance.getdaterange457535` (logType) | `aN/aN/NaN` = sin rango indexado; el logViewer con fecha explícita igual funciona |

---

## Dominio 8 — Alarms y correlación

| Check | Cómo | Interpretación |
|---|---|---|
| Conteos | `OP: orchestrator.allappliancealarmsummary12` / `TOOL: get_active_alarms` | Por severidad |
| Detalle filtrado | `OP: orchestrator.alarmappliancegetpost9` (from/to epoch ms, severity, view, orderBySeverity, maxAlarms) | Query-with-body: POST read |
| Acknowledge/clear/notes | `apply_change` sobre `orchestrator.alarmacknowledgement5` / `alarmclearance10` / alarm notes ops | No borrar alarmas sin entender la causa — son la línea de tiempo del incidente |
| Severidades personalizadas | `OP: orchestrator.customseverityget15` / `customseveritypost16` | Ajuste fino de qué se reporta como crítico |

**Correlación**: mismo túnel/sitio con decenas de alarmas simultáneas = una causa raíz (p.ej. circuito caído); identificar el evento padre antes de tratar alarmas individuales.

---

## Dominio 9 — HA (EdgeHA / Orchestrator-HA)

| Check | Cómo | Interpretación |
|---|---|---|
| HA de appliances | `TOOL: get_ha_status` | Pares, interfaces de sync; missing HA se reporta explícito |
| Orch-HA reachability | `OP: orchestrator.haclusterreachabilityconfigget` (`/orch-ha/reachability`) | Config de reachability del cluster de orquestadores |
| Orch-HA notificaciones | `OP: orchestrator.hanotificationconfigget` (`/orch-ha/notificationConfig`) | A quién avisa si el orch primario falla |
| Estado de failover | Alarms del dominio 8 filtradas por HA | Failover reciente aparece como secuencia de alarmas |

---

## Dominio 10 — Telemetría y stats collectors

| Check | Cómo | Interpretación |
|---|---|---|
| Estado de collectors | `OP: orchestrator.gethealthstatusofallstatscollectors726` (`/statsCollector/status`) | Collector caído = huecos en TODA la telemetría histórica |
| Thresholds de salud | `OP: orchestrator.healththresholdconfigget408` / `healththresholdconfigpost409` | Qué cuenta como "unhealthy" |
| Health resumido | `OP: orchestrator.healthsummary406` (POST) | Resumen multi-appliance |
| Métricas del orquestador | `TOOL: orchestrator_metrics({})` | Latencia por operación del propio pipeline MCP |

---

## Apéndice A — Contratos problemáticos conocidos (no perder tiempo)

| Endpoint | Comportamiento | Alternativa correcta |
|---|---|---|
| REST appliance `/securityLog`, `/firewallLog`, `/events`, `/idpEvents` | Cuerpo vacío; proxy devuelve `{"ok": true}` | `/logViewer/{logType}/{date}/{lines}` |
| `GET /availability/appliance` | 404 en v9.7 | `/stats/aggregate/availability/tunnel` |
| Orchestrator `/dhcpConfig/leases` | 400 "supply correct input" | `/dhcpd/leases` nativo del appliance |
| REST appliance `/arpTable`, `/macTable`, `/fdb`, `/ndp` | 404 | `/neighbors` |
| `appliance.send_command` (`/appliance/restInvoke/{id}`) | 404 en ECOS 9.7 | Proxy `orchestrator.appliancegetapi70` con `url=<endpoint>` |
| `get_mos` con query params | 400 "null does not exist in GMS" | MOS de `get_wan_health` |

## Apéndice B — Señal `{"ok": true}` del proxy

El proxy `orchestrator.appliancegetapi70` devuelve `{"ok": true}` cuando el appliance responde **cuerpo vacío** — casi siempre ruta inexistente. Antes de concluir que un endpoint existe y "está vacío", validar con un endpoint conocido (`/neighbors`). Contrasta: 404 real = el orquestador no conoce la ruta; `{"ok": true}` = el appliance ignoró la ruta.

## Apéndice C — Ventanas de tiempo por familia de endpoints

| Familia | Formato |
|---|---|
| Alarmas (`/alarm/appliance`, from/to) | epoch **ms** |
| IDS/IPS events (startTime/endTime) | epoch **secs** |
| Stats aggregate (startTime/endTime) | epoch **ms** |
| Log Viewer (date path param) | `YYYY-MM-DD` |
