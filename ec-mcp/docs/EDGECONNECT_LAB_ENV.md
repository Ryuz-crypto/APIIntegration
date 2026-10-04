# EdgeConnect Lab Environment — snapshot del laboratorio (México)

Datos específicos del ambiente de pruebas. Reglas y métodos generales viven en `EDGECONNECT_EXPERT_SKILL.md`.

## Postura de seguridad (snapshot)

- **EC-CLOUD (1-4.NE) ilegibles vía Orchestrator**: error 500 `PortalWS: DH key exchange is not completed` en toda lectura appliance-scoped (IDS/zones/tunnels). Canal WS Orchestrator↔appliance sin handshake DH completado; reintenta o reconecta el appliance, no es problema de config.
- **14.NE MATAMOROS**: único con IDS/IPS activo (`ips_inline`), 0 eventos en ventana 24h.
- **16.NE EC3**: IDS/IPS desactivado a propósito (licencia adv_sec retirada tras pruebas); licencia portal tier 500 Mbps restaurada manualmente.
- Zone matrix vacía (0 políticas inter-zona) en 14.NE y 16.NE → tráfico inter-zona en default policy; hallazgo para endurecimiento futuro.
- SSE: Zscaler/Netskope/Axis con conectividad 0 y 0 appliances asociados (sin integración configurada en este Orchestrator).
- Región NFR (regionId 3) creada para appliances de pruebas NFR; EC3 movido ahí. Sin hubs asignados todavía → sin túneles esperado hasta asignar hubs de overlay en NFR.

## 12. DHCP (Orchestrator `/dhcpConfig`) — contrato real
- `POST /dhcpConfig` (dhcpconfigpost220): body con 3 claves top: `mode` ("server"|"relay"), `serverConfig` (para mode=server) y `relayConfig` (para mode=relay), más `dhcpFoSetting` (failover, p.ej. `{"my_ip","peer_ip","role","mclt","split",...}`; vacío si no hay EdgeHA). **Requiere `nePk` como query param** (los GET hermanos también lo declaran).
- `serverConfig` claves: `startIp`, `endIp`, `defaultSubnetMask`, `defaultLease` (s 1-2147483647, default 86400), `maxLease` (default 172800), `defaultGateway`, `defaultGatewayEnabled`, `dnsServers[]`, `ntpServers[]`, `netBiosServers[]`, `netBiosNodeType` ("B"|"P"|"M"|"H"), `blockStartIp`, `blockMask`, `startOffset`, `endOffset`, `options{}`, `staticIps[]`, `reservations[]`, `localReservations[]`, `applianceReservations[]`, `failover` (bool).
- `relayConfig` claves: `destDhcpServer`, `opt82` (bool; si true, al menos un subOpt debe ser true), `opt82Policy` ("append"|"replace"|"forward"|"discard"), `opt82SubOpt{1,5,10,11,150,151,152}` (bools), `serverPerSegment` (bool).
- `POST /dhcpConfig/reservations?nePk=` (dhcpreservationspost223): body `{"ifName":"lan0","mask":24,"serialNum":"<serial>","startIp":"<subnet>"}` — reserva subred del pool.
- `POST /dhcpConfig/reservations/gms` (dhcpreservationsgmspost224): body lista `[{"ifName":"lan0","ip":"172.16.200.5","mask":24,"neId":"16.NE","source":"local"}]` — actualiza/limpia reservaciones locales aún no aplicadas al appliance.
- `POST /dhcpConfig/reset` (dhcpconfigreset225): **POST sin body**, limpia todas las reservaciones del pool.
- `GET /dhcpConfig/leases` (dhcpdleases221): query `nePk` (requerido), `cached` (true=cache, false=appliance), `maxLease` (límite, default/máx 10000). Si devuelve 400 "supply correct input", verificar que el conector propagó `nePk` en el query string.
- Alternativa ZTP/preconfig YAML: sección `dhcpInfo` en `deploymentInfo` (dhcpInterfaceName, dhcpType "server", dhcpAddressMask, startIpAddress/endIpAddress, iPRanges[], gatewayIpAddress, dnsServers[], maximumLease, defaultLease, options, staticIpAssignments[hostname/macAddress/ipAddress]); relay: dhcpType "relay" con dhcpProxyServers[] y option82.
- DHCP failover (EdgeHA): `dhcpFailoverRole` ("primary"/"secondary"), settings compartidos por interfaz física, solo el último role definido aplica si hay duplicados.
