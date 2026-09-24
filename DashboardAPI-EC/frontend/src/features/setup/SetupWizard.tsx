import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography
} from "@mui/material";
import { CheckCircle2, Cloud, KeyRound, Server, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { api, ValidationResult } from "../../lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  onComplete: () => void;
};

const steps = ["Entorno", "Conexión", "Autenticación", "Seguridad", "Detectar"];

export function SetupWizard({ open, onClose, onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [deploymentType, setDeploymentType] = useState("oaas");
  const [name, setName] = useState("EdgeConnect Orchestrator");
  const [baseUrl, setBaseUrl] = useState("");
  const [tenant, setTenant] = useState("");
  const [authType, setAuthType] = useState("api_key");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [otp, setOtp] = useState("");
  const [loginType, setLoginType] = useState(0);
  const [verifyTls, setVerifyTls] = useState(true);
  const [timeoutSeconds, setTimeoutSeconds] = useState(20);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);

  const authReady = useMemo(() => {
    if (authType === "api_key") return Boolean(apiToken);
    if (["session", "session_otp", "basic"].includes(authType)) {
      return Boolean(username && password && (authType !== "session_otp" || otp));
    }
    return true;
  }, [apiToken, authType, otp, password, username]);

  function reset() {
    setStep(0);
    setError(null);
    setResult(null);
  }

  async function connect() {
    setWorking(true);
    setError(null);
    try {
      const orchestrator = await api.createOrchestrator({
        name,
        base_url: baseUrl,
        deployment_type: deploymentType,
        tenant: tenant || undefined,
        credential_label: authType === "api_key" ? "read-only-api-key" : "interactive-session",
        auth_type: authType,
        login_type: loginType,
        username: username || undefined,
        password: password || undefined,
        api_token: apiToken || undefined,
        api_key_header: "X-Auth-Token",
        verify_tls: verifyTls,
        timeout_seconds: timeoutSeconds
      });
      const validation = await api.validateOrchestrator(orchestrator.id, otp || undefined);
      setResult(validation);
      if (validation.status === "validated") {
        await api.discoverAppliances(orchestrator.id);
        onComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible completar la conexión");
    } finally {
      setWorking(false);
    }
  }

  function close() {
    reset();
    onClose();
  }

  const nextDisabled =
    (step === 1 && (!name || !baseUrl)) ||
    (step === 2 && !authReady) ||
    working;

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="md">
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box sx={{ display: "grid", placeItems: "center", color: "primary.main" }}>
            <ShieldCheck size={25} />
          </Box>
          <Box>
            <Typography variant="h2">Conectar EdgeConnect</Typography>
            <Typography variant="body2" color="text.secondary">
              El asistente detectará versión, capacidades e inventario.
            </Typography>
          </Box>
        </Stack>
      </DialogTitle>
      <DialogContent>
        <Stepper activeStep={step} alternativeLabel sx={{ py: 3 }}>
          {steps.map((label) => (
            <Step key={label}><StepLabel>{label}</StepLabel></Step>
          ))}
        </Stepper>

        {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

        {step === 0 ? (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            {[
              { value: "oaas", title: "Orchestrator as a Service", detail: "API key recomendada; MFA permanece en el acceso humano.", icon: <Cloud /> },
              { value: "on_prem", title: "On-premises", detail: "API key o sesión local con CSRF.", icon: <Server /> }
            ].map((option) => (
              <Paper
                key={option.value}
                onClick={() => setDeploymentType(option.value)}
                sx={{
                  p: 2.5,
                  flex: 1,
                  cursor: "pointer",
                  borderColor: deploymentType === option.value ? "primary.main" : "divider",
                  bgcolor: deploymentType === option.value ? "rgba(47,191,155,.08)" : "background.paper"
                }}
              >
                <Box sx={{ color: "primary.main", mb: 1 }}>{option.icon}</Box>
                <Typography fontWeight={800}>{option.title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{option.detail}</Typography>
              </Paper>
            ))}
          </Stack>
        ) : null}

        {step === 1 ? (
          <Stack spacing={2}>
            <TextField label="Nombre" value={name} onChange={(event) => setName(event.target.value)} />
            <TextField
              label="URL del Orchestrator"
              placeholder="https://orchestrator.example.com"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              helperText="Puede ser el host o la URL terminada en /gms/rest."
            />
            <TextField label="Tenant o región (opcional)" value={tenant} onChange={(event) => setTenant(event.target.value)} />
          </Stack>
        ) : null}

        {step === 2 ? (
          <Stack spacing={2}>
            <FormControl>
              <InputLabel id="wizard-auth-label">Método</InputLabel>
              <Select labelId="wizard-auth-label" label="Método" value={authType} onChange={(event) => setAuthType(event.target.value)}>
                <MenuItem value="api_key">API key · X-Auth-Token</MenuItem>
                <MenuItem value="session">Sesión con usuario y contraseña</MenuItem>
                <MenuItem value="session_otp">Sesión interactiva con OTP</MenuItem>
                <MenuItem value="basic">HTTP Basic</MenuItem>
              </Select>
            </FormControl>
            {authType === "api_key" ? (
              <TextField label="API key" type="password" value={apiToken} onChange={(event) => setApiToken(event.target.value)} />
            ) : (
              <>
                <TextField label="Usuario" value={username} onChange={(event) => setUsername(event.target.value)} />
                <TextField label="Contraseña" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                <FormControl>
                  <InputLabel id="login-type-label">Proveedor</InputLabel>
                  <Select labelId="login-type-label" label="Proveedor" value={loginType} onChange={(event) => setLoginType(Number(event.target.value))}>
                    <MenuItem value={0}>Local</MenuItem>
                    <MenuItem value={1}>RADIUS</MenuItem>
                    <MenuItem value={2}>TACACS</MenuItem>
                  </Select>
                </FormControl>
                {authType === "session_otp" ? (
                  <TextField label="Código de un solo uso" value={otp} onChange={(event) => setOtp(event.target.value)} helperText="Se usa una vez y no se almacena." />
                ) : null}
              </>
            )}
            {deploymentType === "oaas" && authType !== "api_key" ? (
              <Alert severity="warning">Para operación continua en OaaS se recomienda una API key de solo lectura.</Alert>
            ) : null}
          </Stack>
        ) : null}

        {step === 3 ? (
          <Stack spacing={2}>
            <FormControlLabel control={<Checkbox checked={verifyTls} onChange={(event) => setVerifyTls(event.target.checked)} />} label="Verificar certificado TLS" />
            <TextField
              label="Timeout"
              type="number"
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
              inputProps={{ min: 5, max: 120 }}
              helperText="Segundos por solicitud. Recomendado: 20."
            />
            {!verifyTls ? <Alert severity="warning">Desactivar TLS debe limitarse a laboratorios controlados.</Alert> : null}
          </Stack>
        ) : null}

        {step === 4 ? (
          <Stack spacing={2}>
            <Paper sx={{ p: 2.5, bgcolor: "rgba(255,255,255,.025)" }}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                {result?.status === "validated" ? <CheckCircle2 color="#53C57B" /> : <KeyRound color="#2FBF9B" />}
                <Box>
                  <Typography fontWeight={800}>{result?.status === "validated" ? "Conexión validada" : "Listo para detectar"}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {result ? `Versión ${result.detected_version ?? "no reconocida"} · ${Object.keys(result.capabilities).length} capacidades` : `${name} · ${baseUrl}`}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
            {result && result.status !== "validated" ? <Alert severity="warning">{result.message}</Alert> : null}
            <Typography variant="body2" color="text.secondary">
              Se comprobarán autenticación, versión, perfil compatible e inventario. El código OTP no se guardará.
            </Typography>
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={close}>Cancelar</Button>
        {step > 0 && !result ? <Button onClick={() => setStep((current) => current - 1)}>Atrás</Button> : null}
        {step < 4 ? (
          <Button variant="contained" disabled={nextDisabled} onClick={() => setStep((current) => current + 1)}>Continuar</Button>
        ) : result?.status === "validated" ? (
          <Button variant="contained" onClick={close}>Abrir dashboard</Button>
        ) : (
          <Button variant="contained" disabled={working} onClick={connect}>{working ? "Detectando…" : "Conectar y detectar"}</Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
