import { Download, RefreshCw } from "lucide-react";
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Stack, TextField, Typography
} from "@mui/material";
import { useEffect, useState } from "react";
import { api, type ReleaseStatus, type UpdateStatus } from "../../lib/api";

export function UpdateDialog({ onClose }: { onClose: () => void }) {
  const [token, setToken] = useState("");
  const [releases, setReleases] = useState<ReleaseStatus>();
  const [status, setStatus] = useState<UpdateStatus>();
  const [selected, setSelected] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true); setError("");
    try {
      const result = await api.releases(token);
      setReleases(result);
      setSelected(result.latest_stable || result.latest || "");
      setStatus(await api.updateStatus(token));
      if (!result.ok) setError(result.error || "No se pudo consultar el canal oficial.");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo consultar el canal oficial."); }
    finally { setBusy(false); }
  }

  async function update() {
    setBusy(true); setError("");
    try { setStatus(await api.updateSystem(token, selected, confirmation)); setConfirmation(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo programar la actualización."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!token || !status || !["pending", "running"].includes(status.state)) return;
    const timer = window.setInterval(() => {
      void api.updateStatus(token).then((next) => {
        setStatus(next);
        if (next.state === "success") window.setTimeout(() => window.location.reload(), 1500);
      }).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.state, token]);

  const expected = selected ? `ACTUALIZAR ${selected}` : "";
  return <Dialog open onClose={busy || status?.state === "running" ? undefined : onClose} fullWidth maxWidth="sm">
    <DialogTitle>Actualizar DashboardAPI-EC</DialogTitle>
    <DialogContent>
      <Stack spacing={2} sx={{ pt: 1 }}>
        <Typography color="text.secondary">Consulta únicamente etiquetas oficiales. Antes de instalar se respalda PostgreSQL, configuración, Nginx y certificados.</Typography>
        <TextField label="Clave administrativa" type="password" value={token} autoComplete="off" onChange={(event) => setToken(event.target.value)} helperText="Es la misma TLS_ADMIN_TOKEN utilizada para administrar HTTPS." />
        <Button variant="outlined" startIcon={<RefreshCw size={17} />} disabled={!token || busy} onClick={() => void check()}>Buscar versiones</Button>
        {error ? <Alert severity="error">{error}</Alert> : null}
        {releases?.ok ? <Stack spacing={1.5}>
          <Typography>Instalada: <strong>{releases.current_release}</strong></Typography>
          <Typography>Última estable: <strong>{releases.latest_stable || "Sin publicación"}</strong></Typography>
          <TextField select label="Versión oficial" value={selected} onChange={(event) => { setSelected(event.target.value); setConfirmation(""); }}>
            {releases.releases.map((release) => <MenuItem key={release} value={release}>{release}</MenuItem>)}
          </TextField>
          {selected ? <><Typography variant="caption">Escribe exactamente: <code>{expected}</code></Typography><TextField label="Confirmación" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></> : null}
        </Stack> : null}
        {status ? <Alert severity={status.state === "error" ? "error" : status.state === "success" ? "success" : "info"}>{status.message || `Estado: ${status.state}`}{status.backup ? ` Respaldo: ${status.backup}` : ""}</Alert> : null}
      </Stack>
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose} disabled={busy || status?.state === "running"}>Cerrar</Button>
      <Button variant="contained" startIcon={<Download size={17} />} disabled={busy || !selected || confirmation !== expected || releaseKey(selected) <= releaseKey(releases?.current_release ?? "v0.0.0-stable")} onClick={() => void update()}>Aplicar actualización</Button>
    </DialogActions>
  </Dialog>;
}

function releaseKey(value: string): number {
  const match = value.match(/^v?(\d+)\.(\d+)\.(\d+)-stable$/);
  if (!match) return 0;
  return Number(match[1]) * 1_000_000 + Number(match[2]) * 1_000 + Number(match[3]);
}
