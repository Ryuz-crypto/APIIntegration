# Monitoreo en tiempo real y correlación

DashboardAPI-EC 1.5.1 mantiene una conexión WebSocket por el Orchestrator seleccionado. La URL es `/api/v1/realtime/dashboard/{id}` y el navegador cambia automáticamente entre `ws://` y `wss://` según el acceso al panel. Nginx conserva el upgrade de conexión en HTTP y HTTPS.

## Autenticación y actualización

El navegador envía la sesión local mediante el subprotocolo `dashboardapi`; el backend valida que el token exista, no esté revocado y pertenezca a un usuario habilitado. El token no se incluye en la URL. El servidor entrega un snapshot inicial, comprueba cambios cada dos segundos y envía un heartbeat cada 15 segundos cuando no hay datos nuevos. Si se corta la red, el cliente reintenta con espera progresiva de 1 a 15 segundos.

El WebSocket no consulta directamente a los EdgeConnect. Los workers de Celery siguen recolectando y persistiendo las APIs; el canal transmite el modelo correlacionado cuando las muestras cambian. Así, una pestaña lenta o desconectada no altera el polling del Orchestrator.

## Datos utilizados

- `GET /appliance`: inventario, sitios, versiones y estado de equipos.
- `GET /topology`: relaciones de red, consultadas durante el descubrimiento cuando la capacidad existe.
- `GET /stats/timeseries/appliance`: rendimiento y puntos de telemetría.
- `GET /interfaceState/{nePk}`: estado de interfaces.
- `GET /stats/aggregate/tunnel`: estado y estadísticas de túneles.
- `POST /health`: salud adicional cuando el perfil detectado declara la operación.
- Todas las muestras recientes: tasa de éxito y latencia media por operación API.

## Correlación

El índice de salud parte del porcentaje de respuestas API correctas y descuenta señales por métricas fuera de rango, interfaces con incidencia y túneles con incidencia. Las señales consideran pérdida superior a 2 %, latencia superior a 100 ms, jitter superior a 30 ms, CPU/memoria/utilización superior a 85 % y contadores de error mayores que cero.

El panel agrupa las métricas por sitio, muestra prioridades y conserva el enlace **Ver API utilizada** para abrir la muestra que respalda cada widget. Estos umbrales son indicadores operativos para priorización; no sustituyen las políticas o SLA particulares de cada red.

## Diagnóstico

Comprueba el canal desde el navegador observando el badge **WebSocket · EN VIVO**. Si permanece en **Reconectando**, revisa:

```bash
sudo nginx -t
sudo systemctl status nginx dashboardapi-ec
sudo journalctl -u dashboardapi-ec -n 100 --no-pager
```

Después de actualizar desde una versión anterior, el instalador reemplaza la configuración Nginx e incluye los headers `Upgrade` y `Connection` requeridos para WebSocket.
