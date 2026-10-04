# EdgeConnect Lab Environment — snapshot del laboratorio (México)

Datos específicos del ambiente de pruebas. Reglas y métodos generales viven en `EDGECONNECT_EXPERT_SKILL.md`.

## Postura de seguridad (snapshot)

- **EC-CLOUD (1-4.NE) ilegibles vía Orchestrator**: error 500 `PortalWS: DH key exchange is not completed` en toda lectura appliance-scoped (IDS/zones/tunnels). Canal WS Orchestrator↔appliance sin handshake DH completado; reintenta o reconecta el appliance, no es problema de config.
- **14.NE MATAMOROS**: único con IDS/IPS activo (`ips_inline`), 0 eventos en ventana 24h.
- **16.NE EC3**: IDS/IPS desactivado a propósito (licencia adv_sec retirada tras pruebas); licencia portal tier 500 Mbps restaurada manualmente.
- Zone matrix vacía (0 políticas inter-zona) en 14.NE y 16.NE → tráfico inter-zona en default policy; hallazgo para endurecimiento futuro.
- SSE: Zscaler/Netskope/Axis con conectividad 0 y 0 appliances asociados (sin integración configurada en este Orchestrator).
- Región NFR (regionId 3) creada para appliances de pruebas NFR; EC3 movido ahí. Sin hubs asignados todavía → sin túneles esperado hasta asignar hubs de overlay en NFR.
