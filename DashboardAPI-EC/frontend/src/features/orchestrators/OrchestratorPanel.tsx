import {
  Box,
  Button,
  Chip,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import { AlertCircle, CheckCircle2, PlugZap, Radar, RefreshCw } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { StatusChip } from "../../components/StatusChip";
import { api, Orchestrator, OrchestratorConnectionPlan } from "../../lib/api";

type Props = {
  items: Orchestrator[];
  profiles: string[];
  onChanged: () => void;
};

const AUTH_LABELS: Record<string, string> = {
  none: "None",
  basic: "Basic",
  bearer: "Bearer",
  api_key: "API Key"
};

export function OrchestratorPanel({ items, profiles, onChanged }: Props) {
  const [name, setName] = useState("Lab Orchestrator");
  const [baseUrl, setBaseUrl] = useState("https://orchestrator.example.local");
  const [apiVersion, setApiVersion] = useState("");
  const [authType, setAuthType] = useState("none");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [apiKeyHeader, setApiKeyHeader] = useState("X-API-Key");
  const [verifyTls, setVerifyTls] = useState(true);
  const [timeoutSeconds, setTimeoutSeconds] = useState(20);
  const [connectionPlan, setConnectionPlan] = useState<OrchestratorConnectionPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.connectionPlan(authType).then(setConnectionPlan).catch(() => setConnectionPlan(null));
  }, [authType]);

  const checks = useMemo(() => {
    const apiProfileOk = !apiVersion || profiles.includes(apiVersion);
    const nextChecks = [
      { label: "Name", ok: name.trim().length >= 2 },
      { label: "Base URL", ok: /^https?:\/\//i.test(baseUrl.trim()) },
      { label: "API profile", ok: apiProfileOk },
      { label: "Timeout", ok: timeoutSeconds >= 3 && timeoutSeconds <= 120 }
    ];
    if (authType === "basic") {
      nextChecks.push({ label: "Username", ok: username.trim().length > 0 });
      nextChecks.push({ label: "Password", ok: password.length > 0 });
    }
    if (authType === "bearer") {
      nextChecks.push({ label: "Bearer token", ok: apiToken.length > 0 });
    }
    if (authType === "api_key") {
      nextChecks.push({ label: "API key", ok: apiToken.length > 0 });
      nextChecks.push({ label: "Header", ok: apiKeyHeader.trim().length > 0 });
    }
    return nextChecks;
  }, [apiKeyHeader, apiToken, apiVersion, authType, baseUrl, name, password, profiles, timeoutSeconds, username]);

  const formReady = checks.every((check) => check.ok);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!formReady) {
      setMessage("Complete the required connection parameters before saving.");
      return;
    }
    try {
      await api.createOrchestrator({
        name,
        base_url: baseUrl,
        api_version: apiVersion || undefined,
        credential_label: authType === "none" ? undefined : `${authType}-credential`,
        auth_type: authType,
        username: username || undefined,
        password: password || undefined,
        api_token: apiToken || undefined,
        api_key_header: apiKeyHeader || undefined,
        verify_tls: verifyTls,
        timeout_seconds: timeoutSeconds
      });
      setMessage(null);
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create orchestrator");
    }
  }

  async function validate(id: string) {
    try {
      await api.validateOrchestrator(id);
      setMessage(null);
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Validation failed");
    }
  }

  async function discover(id: string) {
    try {
      await api.discoverAppliances(id);
      setMessage(null);
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Discovery failed");
    }
  }

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h2">Orchestrators</Typography>
        <Tooltip title="Refresh">
          <Button onClick={onChanged} startIcon={<RefreshCw size={16} />} variant="outlined">
            Refresh
          </Button>
        </Tooltip>
      </Box>
      <Box component="form" onSubmit={onSubmit} sx={{ display: "grid", gap: 1.5, mb: 2 }}>
        <TextField size="small" label="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField
          size="small"
          label="Base URL"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />
        <FormControl size="small">
          <InputLabel id="api-version-label">API profile</InputLabel>
          <Select
            labelId="api-version-label"
            label="API profile"
            value={apiVersion}
            onChange={(e) => setApiVersion(e.target.value)}
          >
            <MenuItem value="">Auto detect</MenuItem>
            {profiles.map((version) => (
              <MenuItem key={version} value={version}>
                {version}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small">
          <InputLabel id="auth-type-label">Auth</InputLabel>
          <Select
            labelId="auth-type-label"
            label="Auth"
            value={authType}
            onChange={(e) => setAuthType(e.target.value)}
          >
            <MenuItem value="none">None</MenuItem>
            <MenuItem value="basic">Basic</MenuItem>
            <MenuItem value="bearer">Bearer</MenuItem>
            <MenuItem value="api_key">API Key</MenuItem>
          </Select>
        </FormControl>
        {authType === "basic" ? (
          <>
            <TextField size="small" label="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
            <TextField
              size="small"
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </>
        ) : null}
        {authType === "bearer" || authType === "api_key" ? (
          <TextField
            size="small"
            label={authType === "bearer" ? "Bearer token" : "API key"}
            type="password"
            value={apiToken}
            onChange={(e) => setApiToken(e.target.value)}
          />
        ) : null}
        {authType === "api_key" ? (
          <TextField
            size="small"
            label="Header"
            value={apiKeyHeader}
            onChange={(e) => setApiKeyHeader(e.target.value)}
          />
        ) : null}
        <FormControlLabel
          control={<Checkbox checked={verifyTls} onChange={(e) => setVerifyTls(e.target.checked)} />}
          label="Verify TLS"
        />
        <TextField
          size="small"
          label="Timeout seconds"
          type="number"
          value={timeoutSeconds}
          onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
          inputProps={{ min: 3, max: 120 }}
        />
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          {checks.map((check) => (
            <Chip
              key={check.label}
              size="small"
              color={check.ok ? "success" : "error"}
              icon={check.ok ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
              label={check.label}
              variant={check.ok ? "outlined" : "filled"}
            />
          ))}
        </Stack>
        {connectionPlan ? (
          <Typography variant="caption" color="text.secondary">
            {AUTH_LABELS[connectionPlan.auth_type]} / {connectionPlan.validation_operation} /{" "}
            {connectionPlan.discovery_operation}
          </Typography>
        ) : null}
        <Button type="submit" variant="contained" startIcon={<PlugZap size={16} />} disabled={!formReady}>
          Add Orchestrator
        </Button>
      </Box>
      {message ? (
        <Typography sx={{ mb: 2 }} color="error" variant="body2">
          {message}
        </Typography>
      ) : null}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>API</TableCell>
            <TableCell>Auth</TableCell>
            <TableCell>Last read</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell>
                <Stack spacing={0.25}>
                  <Typography variant="body2" fontWeight={700}>
                    {item.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {item.base_url}
                  </Typography>
                </Stack>
              </TableCell>
              <TableCell>
                <StatusChip status={item.status} />
              </TableCell>
              <TableCell>{item.api_version ?? "pending"}</TableCell>
              <TableCell>{item.auth_type}{item.has_secret ? " / secret" : ""}</TableCell>
              <TableCell>
                <Stack spacing={0.25}>
                  <Typography variant="body2">
                    {item.last_status_code ? `HTTP ${item.last_status_code}` : "not read"}
                  </Typography>
                  <Typography variant="caption" color={item.last_error ? "error" : "text.secondary"}>
                    {item.last_error ?? (item.last_latency_ms ? `${item.last_latency_ms} ms` : "-")}
                  </Typography>
                </Stack>
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => validate(item.id)} startIcon={<Radar size={15} />}>
                  Validate
                </Button>
                <Button size="small" onClick={() => discover(item.id)}>
                  Discover
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}
