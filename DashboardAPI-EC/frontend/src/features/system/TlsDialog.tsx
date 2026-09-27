import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Status = { state: string; message?: string; hostname?: string; expires_at?: string };
export function TlsDialog({ onClose }: { onClose: () => void }) {
  const [hostname, setHostname] = useState("");
  const [password, setPassword] = useState("");
  const [certificate, setCertificate] = useState<File>();
  const [key, setKey] = useState<File>();
  const [status, setStatus] = useState<Status>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    const data = await api.tlsStatus();
    setStatus(data);
    return data as Status;
  }

  useEffect(() => {
    if (status?.state !== "pending") return;
    const timer = window.setInterval(() => {
      void refresh().catch(() => setError("No se pudo consultar el resultado. Revisa la conexión y pulsa Consultar estado."));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.state]);

  async function upload() {
    if (!certificate) return;
    setBusy(true); setError("");
    try { const next = await api.uploadTls(hostname, certificate, key, password); setStatus(next); setPassword(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar el certificado."); }
    finally { setBusy(false); }
  }

  return <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
    <DialogTitle>Certificado HTTPS</DialogTitle>
    <DialogContent>
      <Stack spacing={2} sx={{ pt: 1 }}>
        <Typography color="text.secondary">Protege el acceso al dashboard con un certificado de tu organización. Disponible en la instalación Ubuntu mediante .deb.</Typography>
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
      <Button disabled={busy} onClick={() => { setError(""); void refresh().catch(err => setError(err.message)); }}>Consultar estado</Button>
      <Button variant="contained" disabled={!hostname || !certificate || busy || status?.state === "pending"} onClick={() => void upload()}>{busy ? "Validando…" : "Validar y activar HTTPS"}</Button>
    </DialogActions>
  </Dialog>;
}
