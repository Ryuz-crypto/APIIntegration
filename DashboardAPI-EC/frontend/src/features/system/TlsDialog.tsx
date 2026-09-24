import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";

type Status = { state: string; message?: string; hostname?: string; expires_at?: string };
const endpoint = `${import.meta.env.VITE_API_BASE_URL ?? "/api/v1"}/system/tls`;

export function TlsDialog({ onClose }: { onClose: () => void }) {
  const [token, setToken] = useState("");
  const [hostname, setHostname] = useState("");
  const [password, setPassword] = useState("");
  const [certificate, setCertificate] = useState<File>();
  const [key, setKey] = useState<File>();
  const [status, setStatus] = useState<Status>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const secure = location.protocol === "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);

  async function request(init: RequestInit = {}) {
    const response = await fetch(endpoint, { ...init, headers: { "X-TLS-Admin-Token": token } });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Revisa los archivos y los campos requeridos.");
    setStatus(data);
    return data as Status;
  }

  useEffect(() => {
    if (status?.state !== "pending") return;
    const timer = window.setInterval(() => {
      void request().catch(() => setError("No se pudo consultar el resultado. Revisa la conexión y pulsa Consultar estado."));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.state, token]);

  async function upload() {
    if (!certificate) return;
    setBusy(true); setError("");
    const data = new FormData();
    data.append("hostname", hostname);
    data.append("certificate", certificate);
    if (key) data.append("key", key);
    data.append("password", password);
    try { await request({ method: "POST", body: data }); setPassword(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar el certificado."); }
    finally { setBusy(false); }
  }

  return <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
    <DialogTitle>Certificado HTTPS</DialogTitle>
    <DialogContent>
      <Stack spacing={2} sx={{ pt: 1 }}>
        <Typography color="text.secondary">Protege el acceso al dashboard con un certificado de tu organización. Disponible en la instalación Ubuntu mediante .deb.</Typography>
        {!secure && <Alert severity="warning">Primera carga: abre un túnel SSH con <code>ssh -L 8080:127.0.0.1:8081 usuario@servidor</code> y entra a http://localhost:8080. Así proteges la clave privada durante la transferencia.</Alert>}
        <TextField label="Clave de administración HTTPS" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} helperText="TLS_ADMIN_TOKEN del archivo /etc/dashboardapi-ec/dashboardapi-ec.env" />
        <TextField label="Nombre DNS o IP del dashboard" placeholder="dashboard.ejemplo.com" value={hostname} onChange={e => setHostname(e.target.value)} helperText="Debe coincidir con los SAN del certificado. No incluyas https:// ni una ruta." />
        <Typography variant="body2">Certificado PEM/DER con su clave, o paquete PFX/P12 sin archivo de clave adicional. Máximo 256 KiB por archivo.</Typography>
        <TextField type="file" label="Certificado o paquete PFX/P12" InputLabelProps={{ shrink: true }} inputProps={{ accept: ".pem,.crt,.cer,.der,.pfx,.p12" }} onChange={e => setCertificate((e.target as HTMLInputElement).files?.[0])} />
        <TextField type="file" label="Clave privada (solo PEM/DER)" InputLabelProps={{ shrink: true }} inputProps={{ accept: ".key,.pem,.der" }} onChange={e => setKey((e.target as HTMLInputElement).files?.[0])} />
        <TextField label="Contraseña del archivo, si tiene" type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} />
        {error && <Alert severity="error">{error}</Alert>}
        {status?.state === "pending" && <Alert severity="info">Certificado validado. Esperando que Nginx active HTTPS…</Alert>}
        {status?.state === "error" && <Alert severity="error">{status.message}</Alert>}
        {status?.state === "http" && <Alert severity="info">Aún no se ha activado HTTPS desde este panel.</Alert>}
        {status?.state === "active" && <Alert severity="success">HTTPS activo para {status.hostname}. Vence: {status.expires_at ? new Date(status.expires_at).toLocaleDateString() : "—"}. Abre https://{status.hostname?.includes(":") ? `[${status.hostname}]` : status.hostname} para continuar.</Alert>}
      </Stack>
    </DialogContent>
    <DialogActions sx={{ px: 3, pb: 2, flexWrap: "wrap" }}>
      <Button onClick={onClose} disabled={busy}>Cerrar</Button>
      <Button disabled={!secure || !token || busy} onClick={() => { setError(""); void request().catch(err => setError(err.message)); }}>Consultar estado</Button>
      <Button variant="contained" disabled={!secure || !token || !hostname || !certificate || busy || status?.state === "pending"} onClick={() => void upload()}>{busy ? "Validando…" : "Cargar y activar HTTPS"}</Button>
    </DialogActions>
  </Dialog>;
}
