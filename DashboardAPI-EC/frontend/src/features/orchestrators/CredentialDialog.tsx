import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, MenuItem, Select, Stack, TextField, Typography
} from "@mui/material";
import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api, Orchestrator } from "../../lib/api";

type Props = {
  orchestrator: Orchestrator | null;
  onClose: () => void;
  onSaved: () => void;
};

export function CredentialDialog({ orchestrator, onClose, onSaved }: Props) {
  const [authType, setAuthType] = useState("api_key");
  const [label, setLabel] = useState("");
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const [loginType, setLoginType] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orchestrator) return;
    setAuthType(orchestrator.auth_type);
    setLabel(orchestrator.credential_label ?? "");
    setUsername(orchestrator.username ?? "");
    setLoginType(orchestrator.login_type);
    setSecret("");
    setError(null);
  }, [orchestrator]);

  async function save() {
    if (!orchestrator) return;
    setWorking(true);
    setError(null);
    try {
      await api.updateCredentials(orchestrator.id, {
        credential_label: label || undefined,
        auth_type: authType,
        login_type: loginType,
        username: username || undefined,
        password: ["basic", "session", "session_otp"].includes(authType) ? (secret || undefined) : undefined,
        api_token: ["api_key", "bearer"].includes(authType) ? (secret || undefined) : undefined,
        api_key_header: "X-Auth-Token"
      });
      onSaved();
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setWorking(false);
    }
  }

  const usesPassword = ["basic", "session", "session_otp"].includes(authType);
  return (
    <Dialog open={Boolean(orchestrator)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        <Stack direction="row" spacing={1} alignItems="center"><KeyRound color="#2FBF9B" /><Typography variant="h2">Credenciales guardadas</Typography></Stack>
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">Cada Orchestrator conserva su propia credencial cifrada. Deja el secreto vacío para mantener el actual.</Alert>
          {error ? <Alert severity="error">{error}</Alert> : null}
          <TextField label="Etiqueta" value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Producción · solo lectura" />
          <FormControl>
            <InputLabel id="credential-method-label">Método</InputLabel>
            <Select labelId="credential-method-label" label="Método" value={authType} onChange={(event) => setAuthType(event.target.value)}>
              <MenuItem value="api_key">API key · X-Auth-Token</MenuItem>
              <MenuItem value="bearer">Bearer token</MenuItem>
              <MenuItem value="session">Sesión</MenuItem>
              <MenuItem value="session_otp">Sesión con OTP</MenuItem>
              <MenuItem value="basic">HTTP Basic</MenuItem>
            </Select>
          </FormControl>
          {usesPassword ? <TextField label="Usuario" value={username} onChange={(event) => setUsername(event.target.value)} /> : null}
          <TextField label={usesPassword ? "Nueva contraseña" : "Nueva API key"} type="password" value={secret} onChange={(event) => setSecret(event.target.value)} helperText={orchestrator?.has_secret ? "Hay un secreto cifrado configurado." : "Debes configurar un secreto."} />
          {usesPassword ? <FormControl><InputLabel id="credential-provider-label">Proveedor</InputLabel><Select labelId="credential-provider-label" label="Proveedor" value={loginType} onChange={(event) => setLoginType(Number(event.target.value))}><MenuItem value={0}>Local</MenuItem><MenuItem value={1}>RADIUS</MenuItem><MenuItem value={2}>TACACS</MenuItem></Select></FormControl> : null}
          {authType === "session_otp" ? <Alert severity="warning">El OTP nunca se almacena. Esta conexión requiere validación interactiva y no admite recolección desatendida.</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Cancelar</Button><Button variant="contained" disabled={working} onClick={save}>{working ? "Guardando…" : "Guardar cifrado"}</Button></DialogActions>
    </Dialog>
  );
}
