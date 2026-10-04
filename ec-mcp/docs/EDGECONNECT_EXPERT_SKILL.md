# EdgeConnect Expert Skill (GENÉRICO)

Reglas y métodos aplicables a cualquier HPE Aruba EdgeConnect/Orchestrator. Los datos específicos del laboratorio viven en `EDGECONNECT_LAB_ENV.md`.

# EdgeConnect Expert Skill — Hallazgos, reglas y runbooks

Living knowledge base capturado de despliegues reales. Actualizar con cada hallazgo nuevo.

## 1. ZTP / Onboarding vía Orchestrator

- Flujo UI Discover: al presionar **Approve** aparece primero la opción de **actualizar software** (se puede dar *skip*), después se puede elegir **Wizard** o **aplicar YAML**. Si el serial coincide con un template conocido, el sistema ofrece aplicar el YAML y autoconfigura.
- El appliance **solo se reinicia si se actualiza software**; aplicar preconfig YAML no reinicia.
- Un appliance puede quedar en **Discover** sin aprobar, o en la **lista de denegados** (denied). Revisar ambas antes de asumir que el ZTP falló.
- Los appliances por defecto traen el **mismo hostname** → las rutinas de adopción deben **basarse en número de serie**, no en hostname. Para volumen masivo usar bulk adoption por seriales.
- Template de preconfig: si una sección no aplica, **removerla** (los campos vacíos a veces se validan). Post-approval behavior: replace/merge según sección (documentado en el header del template).

## 2. Licenciamiento (AAS / Portal)

- **Regla de ancho de banda**: la suscripción se calcula con la **suma del ancho de banda de los enlaces WAN** del YAML; se toma el **tier inmediato superior** disponible en la cuenta (tiers típicos: 50M, 200M, 500M, 1G, 2G, Unlimited).
- **Boost** solo si el cliente lo pide explícitamente (ráfagas). No asignar por defecto.
- Si el YAML de ZTP incluye `ecLicensing` con `bandwidthLevel` (p.ej. `base`), **ese valor se impone** durante el aprovisionamiento y el appliance queda con licencia **Base** — quitar esa sección si el licenciamiento se maneja por portal.
- **"Enabled, EC Not Licensed" en IDS/IPS** = falta la feature license `adv_sec` (EC-AS / EC-AS-UL) en el appliance; no es problema de configuración.
- APIs clave: `GET /license/portal/appliance` (estado por appliance), `GET /license/portal/summary` (inventario de cuenta), `POST /license/portal/appliance/ec/account/license` con `action: grant` + `license.license.tier/boost/feature` para asignar, `POST /license/portal/appliance/revoke` para quitar.
- Grant exitoso puede tardar (>60s timeout del cliente) — **siempre re-verificar con GET** antes de reintentar; reintentar un grant puede duplicar consumo.

## 3. IDS/IPS

- Modos: `Off`, `IDS Only`, `IPS-Performant`, `IPS-Inline` (`idsIpsConfig` en preconfig: `mode` + `profile`).
- Requiere feature license `adv_sec` en el appliance (ver §2).
- `mode: none` o `disabled` en el API = inactivo.
- Events: leer por appliance con ventana de tiempo (epoch-secs) para incidentes.

## 4. Seguridad / Troubleshooting

- Revisar siempre: posture (IDS/IPS + DDoS + zone matrix + tunnels en una llamada), alarmas activas por appliance, zone matrix (pares de zonas sin política explícita = hallazgo).
- DDoS: threshold status + perfiles por zona.
- NO tocar nunca `ECV-CALIMAYA` (0.NE): es la salida a internet del laboratorio.

## 5. Filtrado de contenido (Secure Web Services / NSS)

- `secureWebServicesConfig` en preconfig: `urlClassificationConfig` (`hasURLClassification`, `incrementalUpdate`, `queryOnMiss`, `urlReputation` 1=High Risk..5=Trustworthy) e `ipReputationConfig`.
- Para filtrar por categorías web (p.ej. pornografía) se requiere **Network Security Services (NSS)** activo y URL Classification habilitado en el appliance; el bloqueo por categoría se aplica vía policy/overlay (BIO) o reglas de seguridad con la categoría como match.

## 6. Ambiente conocido (lab)

| nePk | Hostname | Modelo | Notas |
|------|----------|--------|-------|
| 0.NE | ECV-EMX-CALIMAYA | EC-V | **NO TOCAR** — salida internet |
| 14.NE | EC-10104-MATAMOROS | EC-10104 | pruebas físicas, Unlimited + AAS |
| 16.NE | EC3 | EC-V | ZTP de pruebas, 500 Mbps tier, serial 001BBC462C04 |
| 1-4.NE | EC1-4-CLOUD | EC-V | cloud |

Cuenta portal: Silver Peak SE - Lab Account 20.

## 7. Regiones y regional routing (túneles)

- Alarma `APPLIANCE_NOT_IN_REGION` (WARNING, source /orchestration): regional routing habilitado pero el appliance sin región asociada → **no se construye ningún túnel** (0 túneles aunque el despliegue LAN/WAN esté correcto).
- Regiones: `GET /regions` lista (regionId + nombre). Asociación por appliance: `GET /regions/appliances?nePk=` y `PUT /regions/appliances?nePk=` con body `{"regionId": <integer>}`.
- `POST /regions/appliances` rechaza ese body (400 "supply correct input") — **usar PUT** para reasociar un appliance existente.
- Un appliance re-adoptado (delete + re-add) **pierde la asociación de región** (vuelve a Default/0) y también puede perder la licencia portal asignada → re-verificar ambos tras re-adopción.

## 8. Alarmas y eventos (contract findings)

- `GET /alarm/gms` usa `from`/`to` en **epoch milisegundos** (no segundos). Con segundos devuelve lista vacía o 400 según filtros.
- `POST /alarm/appliance` (detalle) no acepta los filtros combinados de la spec (`view`/`severity` rechazados upstream) — contrato conocido; para detalle usar `/alarm/gms` con from/to ms.
- Cada alarma trae `name`, `description`, `recommendedAction`, `occurrenceCount`, `closed`, `serviceAffect` — suficiente para triage automático.
- Alarmas típicas de lab: `APPLIANCE_NOT_IN_REGION`, `OVERLAY_REGION_MISSING` (overlay sin hub en una región), `FAILED_TO_CONNECT_TO_AZURE/AWS` (sin suscripción cloud en el Orchestrator).

## 9. Stats SWS / WebCC (filtrado de contenido)

- Endpoints timeseries bajo `POST /stats/timeseries/secureWebServices/*`: `configStats` (totalFlows/deniedFlows/highRiskUrls/highRiskips), `allowedDeniedCategory`, `allowedDeniedCategoryUrl`, `allowedDeniedUrl`, `allowedDeniedUrlSrcIp`.
- Body usa **`nePks` (lista)**, no `nePk` singular; startTime/endTime en epoch ms, `allowed: true|false`, `top: N`.
- Datos vacíos = aún no hay tráfico clasificado (o appliance recién adoptado); el collector necesita tráfico real para poblar.
- `GET /secureWebServicesConfig?nePk=` valida que URL Classification/IP Reputation están activos y `isWebccSupported` del modelo.

## 10. DDoS Protection (ADDoS) — perfiles y umbrales

- Endpoints appliance-scoped (vía Orchestrator proxied):
  - **Listar perfiles**: `GET /security/ddos/protectionProfile` (todos) o `GET /security/ddos/protectionProfile/{zoneId}` (por zona).
  - **Crear/actualizar perfiles**: `POST /security/ddos/protectionProfile` con body `{"profiles": [ {profile} ]}`.
  - **Quitar perfil de una zona**: `DELETE /security/ddos/protectionProfile/{zoneId}` (elimina el perfil asignado a esa zona).
  - **Estado de umbrales**: `GET /security/ddos/thresholdStatus` (todas) o `/{zoneId}`.
  - Vista orchestrator: `GET /security/ddos/protectionProfiles/appliance?nePk=&cached=`.
- Schema del perfil (POST):
  ```json
  {"profiles":[{
    "profile_name":"...","enable":true,"comment":"...",
    "preset_threshold_type":"...",
    "spoof_check":true,"icmp_verify":true,"dpi_app_verify":true,
    "ftp_bounce_attack":true,"rst_verify":false,"udp_verify":false,
    "discard_non_syn_tcp":false,"strict_3way_tcp":false,"is_asymmetric":false,
    "aggr_age_time":5,"blacklist_time":60,"embryonic_time":10,"embryonic_non_tcp_time":10,
    "whitelist":"...","blacklist":"...",
    "tid":{"<thresholdId>":{"classification":"...","protocol":"...","metric":"...",
      "enable":true,"min_action":"...","min_value":10,"max_action":"...","max_value":1000,
      "min_value_percent":1,"max_value_percent":100,"is_custom_type":true}}
  }]}
  ```
- **Validado en vivo (EC3/16.NE, 9.6)** — contrato real del POST `{"profiles":[...],"profileMaps":[...]}`:
  - `profileMaps` usa **`zone_id`** (snake_case), NO `zoneId`. Con `zoneId` el appliance devuelve 400/timeout silencioso.
  - El body debe llevar **ambas claves** `profiles` y `profileMaps` (aunque sea `[]`); sin `profileMaps` → 400 "Object does not have profiles / profileMaps key".
  - Rangos validados por el appliance: `aggr_age_time` **15-45** ("Rapid aging"), `embryonic_time` y `embryonic_non_tcp_time` **20-45** ("Embryonic timeout"). Valores default seguros: 30/30/30.
  - Para mapear perfil→zona: `{"profile_name":"<name>","zone_id":<id>}` en `profileMaps`; el appliance responde "Protection profiles updated successfully".
  - **Quitar**: `DELETE /security/ddos/protectionProfile/{zoneId}` → "Protection profile deleted". Para borrar perfiles: POST con `{"profiles":[],"profileMaps":[]}` los limpia.
  - Umbrales `tid`: usar valores **numéricos** (classification: 1=zone/2=source; protocol numérico p. ej. 6=TCP); strings como "dos"/"tcp" → 400 "Value not valid".
  - Respuestas del appliance vía Orchestrator WS a veces dan "read operation timed out" aunque el apply haya fallado — siempre re-verificar con GET.
- Stats para incidentes: `POST /stats/timeseries/ddosTotalStats`, `ddosPeakAndPeakDropRate`, `ddosSrcIpSample10`, `ddosTopTalkers` (query: startTime/endTime epoch ms, granularity, zoneId, metric, protocol, statIds, limit); baseline ADDoS: `POST /stats/timeseries/addos/*` (maxTimestamp, segmentZoneView, trends/baselineZone...). Body `{"nePk": "..."}`.
- IP Reputation DDoS: `GET /security/ddos/ipReputation?filter=trusted|...` y `POST /security/ddos/ipReputationStatus` con `{"segment": <id>, "ipAddress": "x.x.x.x"}`.

## 12. DHCP (Orchestrator `/dhcpConfig`) — contrato validado en vivo
- `POST /dhcpConfig` (dhcpconfigpost220): body con 3 claves top: `mode` ("server"|"relay"), `serverConfig` (para mode=server) y `relayConfig` (para mode=relay), más `dhcpFoSetting` (failover, p.ej. `{"my_ip","peer_ip","role","mclt","split",...}`; vacío si no hay EdgeHA). **Requiere `nePk` como query param** (los GET hermanos también lo declaran).
- `serverConfig` claves: `startIp`, `endIp`, `defaultSubnetMask`, `defaultLease` (s 1-2147483647, default 86400), `maxLease` (default 172800), `defaultGateway`, `defaultGatewayEnabled`, `dnsServers[]`, `ntpServers[]`, `netBiosServers[]`, `netBiosNodeType` ("B"|"P"|"M"|"H"), `blockStartIp`, `blockMask`, `startOffset`, `endOffset`, `options{}`, `staticIps[]`, `reservations[]`, `localReservations[]`, `applianceReservations[]`, `failover` (bool).
- `relayConfig` claves: `destDhcpServer`, `opt82` (bool; si true, al menos un subOpt debe ser true), `opt82Policy` ("append"|"replace"|"forward"|"discard"), `opt82SubOpt{1,5,10,11,150,151,152}` (bools), `serverPerSegment` (bool).
- `POST /dhcpConfig/reservations?nePk=` (dhcpreservationspost223): body `{"ifName":"lan0","mask":24,"serialNum":"<serial>","startIp":"<subnet>"}` — reserva subred del pool.
- `POST /dhcpConfig/reservations/gms` (dhcpreservationsgmspost224): body lista `[{"ifName":"lan0","ip":"172.16.200.5","mask":24,"neId":"16.NE","source":"local"}]` — actualiza/limpia reservaciones locales aún no aplicadas al appliance.
- `POST /dhcpConfig/reset` (dhcpconfigreset225): **POST sin body**, limpia todas las reservaciones del pool.
- `GET /dhcpConfig/leases` (dhcpdleases221): query `nePk` (requerido), `cached` (true=cache, false=appliance), `maxLease` (límite, default/máx 10000). **Validado en vivo (9.6)**: devuelve 400 "supply correct input" incluso pasando nePk/cached/maxLease explícitos — contrato roto upstream. **Usar el endpoint nativo del appliance `GET /dhcpd/leases` (appliance.dhcpdleases559133)**, que funciona (vacío = sin clientes aún); igual `GET /dhcpd/config` para config.
- **POST /dhcpConfig validado en vivo (9.6)**: body completo server-mode devuelve `{"ok": true}` y `GET /dhcpConfig` refleja el estado exacto (el orchestrator normaliza `blockMask` a 0 y agrega `numOfIps`).
- Alternativa ZTP/preconfig YAML: sección `dhcpInfo` en `deploymentInfo` (dhcpInterfaceName, dhcpType "server", dhcpAddressMask, startIpAddress/endIpAddress, iPRanges[], gatewayIpAddress, dnsServers[], maximumLease, defaultLease, options, staticIpAssignments[hostname/macAddress/ipAddress]); relay: dhcpType "relay" con dhcpProxyServers[] y option82.
- DHCP failover (EdgeHA): `dhcpFailoverRole` ("primary"/"secondary"), settings compartidos por interfaz física, solo el último role definido aplica si hay duplicados.

## 12.1 DHCP — hallazgos de aplicación en vivo (EC3/16.NE, 9.6)

- **El POST /dhcpConfig del Orchestrator NO activa el DHCP por sí solo**: guarda la config global en la BD del Orchestrator, pero el DHCP server se activa **por interfaz** en el deployment del appliance.
- **Ruta correcta (3 pasos)**:
  1. `POST /dhcpConfig?nePk=` (config global server/relay — referencia de pool/gateway/DNS).
  2. `POST /deployment` (appliance, vía `/appliance/rest?nePk=...&url=/deployment`): incluir el deployment completo actual (GET /deployment primero) + en la interfaz LAN (`modeIfs[].applianceIPs[]` de lan0) el objeto `dhcpd: {"type":"server","server":{...}}`.
  3. El appliance responde `"Deployment configuration successfully applied, rebooting appliance now"` — **reinicia solo** (el POST /deployment con dhcpd nuevo fuerza reboot).
- **Contrato dhcpd.server del deployment (appliance)**: `prefix` es **CIDR string** (`"172.16.200.0/24"`), NO entero — con `"24"` devuelve 500 `"Invalid value - 24"` en "Unable to add/update appliance IPs". Claves: `ipStart`, `ipEnd`, `prefix` (CIDR), `gw[]`, `dns[]`, `ntpd[]`, `netbios[]`, `netbiosNodeType` (1=B en el appliance), `defaultLease`, `maxLease`, `failover` (bool), `host{}`, `ip_range{}`, `options{}`.
- **`sysConfig` del POST /deployment requiere `maxInBW`** (shaper inbound del sistema); sin él → 400 `"Binding is not of correct type ... key: max_bw"` en shaperinbound/wan. Copiar TODOS los campos del GET actual (maxBW, maxInBW, mode, inline, vrfEnable, serverPerSegment, bonding, etc.).
- Cada `applianceIPs[]` debe llevar `mask` entero y `version: 4` (o 6).
- **Verificación** (después del reboot): `GET /dhcpd/config` nativo del appliance (appliance.dhcpdconfig735985) — debe mostrar `lan0: {"type":"server","server":{...}}`. Leases activos en `GET /dhcpd/leases` (appliance.dhcpdleases559133) con ip/mac/client-hostname/state.
- **Validado en vivo**: al terminar el reboot, un cliente Windows (DESKTOP-ESNSE7L) obtuvo lease `172.16.200.100` activo vía lan0.

## 12.2 POST /deployment — replace completo (hallazgo de licencia, validado en vivo)

- **POST /deployment es REPLACE del deployment completo del appliance**, no merge. Si se omite una sección del GET actual, se pierde.
- **`sysConfig.license` es la suscripción "configured" (la que vive en el appliance)**; el portal muestra el "granted" por separado. Si un POST /deployment omite `sysConfig.license`, el appliance queda con licencia local vacía (portal sigue mostrando granted) → sin servicio aunque el grant exista.
- Siempre: `GET /deployment` → copiar íntegro (modeIfs, sysConfig completo incl. license/ifLabels/zones/vrfs, dhcpFailover, dpRoutes) → modificar solo lo necesario → `POST /deployment`.
- Verificar licencia activa en el appliance: `GET /spPortal/licenses/tokens` nativo (appliancegetapi70 con `url=/spPortal/licenses/tokens`) — muestra `ecTier/ecBase/ecBoost/features` con `enable` y desc p.ej. "EC Tier License - 500 Mbps - 500000 kbps bandwidth limit".
- El appliance reinicia con cada POST /deployment aplicado ("rebooting appliance now") — contar con ~2 min de downtime por apply.
