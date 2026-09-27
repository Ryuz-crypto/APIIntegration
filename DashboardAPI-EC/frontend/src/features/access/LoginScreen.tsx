import { useEffect, useState } from "react";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { KeyRound, LogIn, ShieldCheck, UserCog } from "lucide-react";
import { api, AuthStatus, configureSessionToken } from "../../lib/api";
import { defaultAppearance } from "../../theme/theme";

type Props = { onAuthenticated: (token: string) => void };

export function LoginScreen({ onAuthenticated }: Props) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.authStatus().then(setStatus).catch(() => setStatus(null)); }, []);

  async function login() {
    setBusy(true); setError("");
    try {
      const result = await api.login(username, password);
      configureSessionToken(result.token);
      window.sessionStorage.setItem("dashboardapi-session-token", result.token);
      onAuthenticated(result.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  async function bootstrap() {
    setBusy(true); setError("");
    try {
      await api.bootstrapAdmin(username, password, adminToken);
      const result = await api.login(username, password);
      configureSessionToken(result.token);
      window.sessionStorage.setItem("dashboardapi-session-token", result.token);
      onAuthenticated(result.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el administrador.");
    } finally {
      setBusy(false);
    }
  }

  const needsBootstrap = status ? !status.users_configured : false;

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", bgcolor: defaultAppearance.background, p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 440, width: "100%" }}>
        <Stack direction="row" spacing={1.25} alignItems="center" sx={{ mb: 3 }}>
          <Box sx={{ width: 40, height: 40, display: "grid", placeItems: "center", borderRadius: 2, bgcolor: defaultAppearance.primary, color: "#07110E" }}>
            <ShieldCheck size={22} />
          </Box>
          <Box>
            <Typography fontWeight={900} lineHeight={1.1}>DashboardAPI-EC</Typography>
            <Typography variant="caption" color="text.secondary">EdgeConnect · 1.3 stable</Typography>
          </Box>
        </Stack>
        {needsBootstrap ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            Aún no existen usuarios. Crea el primer administrador con la clave de administración.
          </Alert>
        ) : null}
        {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
        <Stack spacing={2}>
          <TextField label="Usuario" value={username} autoComplete="username" onChange={(event) => setUsername(event.target.value)} />
          <TextField label="Contraseña" type="password" value={password} autoComplete={needsBootstrap ? "new-password" : "current-password"} onChange={(event) => setPassword(event.target.value)} helperText={needsBootstrap ? "Mínimo 12 caracteres" : undefined} />
          {needsBootstrap ? (
            <TextField label="Clave de administración (TLS_ADMIN_TOKEN)" type="password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} helperText="Consúltala en el servidor: sudo sed -n 's/^TLS_ADMIN_TOKEN=//p' /etc/dashboardapi-ec/dashboardapi-ec.env" />
          ) : null}
          {needsBootstrap ? (
            <Button variant="contained" startIcon={<UserCog size={17} />} disabled={busy || !username || password.length < 12 || !adminToken} onClick={() => void bootstrap()}>
              Crear administrador y entrar
            </Button>
          ) : (
            <Button variant="contained" startIcon={<LogIn size={17} />} disabled={busy || !username || !password} onClick={() => void login()}>
              Iniciar sesión
            </Button>
          )}
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", mt: 3 }}>
          <KeyRound size={13} style={{ verticalAlign: "middle", marginRight: 6 }} />
          Acceso con roles viewer, operator y admin.
        </Typography>
      </Paper>
    </Box>
  );
}
