import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { KeyRound, Network, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, AuthSession } from "../../lib/api";

export function LoginPage({ configured, onAuthenticated }: { configured: boolean; onAuthenticated: (session: AuthSession) => void }) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const session = configured
        ? await api.login(username, password)
        : await api.bootstrap({ username, password, display_name: displayName, admin_token: adminToken });
      onAuthenticated(session);
    } catch (err) { setError(err instanceof Error ? err.message : "No fue posible iniciar sesión."); }
    finally { setBusy(false); }
  }

  return <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2, background: "radial-gradient(circle at 15% 15%, rgba(47,191,155,.18), transparent 35%)" }}>
    <Paper component="form" onSubmit={submit} sx={{ width: "100%", maxWidth: 460, p: { xs: 3, sm: 4 }, border: "1px solid rgba(47,191,155,.25)" }}>
      <Stack spacing={2.25}>
        <Box sx={{ width: 52, height: 52, borderRadius: 3, bgcolor: "primary.main", color: "#07110E", display: "grid", placeItems: "center" }}><Network /></Box>
        <Box><Typography variant="h4" fontWeight={900}>{configured ? "Acceso a DashboardAPI-EC" : "Crear administrador inicial"}</Typography><Typography color="text.secondary">{configured ? "Usa tu cuenta local para abrir la consola." : "Este paso se realiza una sola vez después de instalar."}</Typography></Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
        <TextField label="Usuario" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required autoComplete="username" />
        {!configured ? <TextField label="Nombre visible" value={displayName} onChange={(e) => setDisplayName(e.target.value)} /> : null}
        <TextField label="Contraseña" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required helperText={!configured ? "Mínimo 12 caracteres." : undefined} autoComplete={configured ? "current-password" : "new-password"} />
        {!configured ? <TextField label="Token administrativo de instalación" type="password" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} required helperText="Disponible en /etc/dashboardapi-ec/dashboardapi-ec.env como TLS_ADMIN_TOKEN." /> : null}
        <Button type="submit" variant="contained" size="large" disabled={busy} startIcon={configured ? <KeyRound size={18} /> : <ShieldCheck size={18} />}>{busy ? "Verificando…" : configured ? "Iniciar sesión" : "Crear administrador"}</Button>
        <Typography variant="caption" color="text.secondary" textAlign="center">Powered by Emilio Abundis</Typography>
      </Stack>
    </Paper>
  </Box>;
}
