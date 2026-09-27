import { Box, Button, CssBaseline, Grid, MenuItem, Paper, Select, Stack, ThemeProvider, Typography } from "@mui/material";
import { Activity, Boxes, Database, Download, FlaskConical, Gauge, LogOut, Network, Palette, Plus, RadioTower, ShieldCheck, UserCog, Workflow } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { MetricCard } from "./components/MetricCard";
import { AppliancePanel } from "./features/appliances/AppliancePanel";
import { AccessControlPanel } from "./features/access/AccessControlPanel";
import { LoginScreen } from "./features/access/LoginScreen";
import { DynamicDashboard } from "./features/dashboard/DynamicDashboard";
import { OrchestratorPanel } from "./features/orchestrators/OrchestratorPanel";
import { SetupWizard } from "./features/setup/SetupWizard";
import { CompatibilityPanel } from "./features/system/CompatibilityPanel";
import { SamplesPanel } from "./features/system/SamplesPanel";
import { TlsDialog } from "./features/system/TlsDialog";
import { AppearanceDialog } from "./features/system/AppearanceDialog";
import { UpdateDialog } from "./features/system/UpdateDialog";
import { api, Appliance, ApiSample, AppearanceSettings, CompatibilityProfile, Dashboard, Identity, Orchestrator, SystemOverview, configureSessionToken } from "./lib/api";
import { createDashboardTheme, defaultAppearance } from "./theme/theme";

const TryMePage = lazy(() => import("./features/tryme/TryMePage").then((module) => ({ default: module.TryMePage })));

type View = "dashboard" | "tryme" | "access";

const navigation = [
  { id: "summary", view: "dashboard" as View, label: "Resumen", icon: <Gauge size={18} /> },
  { id: "orchestrators", view: "dashboard" as View, label: "Orchestrators", icon: <RadioTower size={18} /> },
  { id: "appliances", view: "dashboard" as View, label: "Appliances", icon: <Boxes size={18} /> },
  { id: "explorer", view: "dashboard" as View, label: "API Explorer", icon: <Database size={18} /> },
  { id: "tryme", view: "tryme" as View, label: "Try Me", icon: <FlaskConical size={18} /> },
  { id: "access", view: "access" as View, label: "Control de acceso", icon: <UserCog size={18} /> }
];

function App() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [orchestrators, setOrchestrators] = useState<Orchestrator[]>([]);
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [profiles, setProfiles] = useState<CompatibilityProfile[]>([]);
  const [samples, setSamples] = useState<ApiSample[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [selectedOrchestrator, setSelectedOrchestrator] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [tlsOpen, setTlsOpen] = useState(false);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [view, setView] = useState<View>("dashboard");
  const [appearance, setAppearance] = useState<AppearanceSettings>(defaultAppearance);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const theme = useMemo(() => createDashboardTheme(appearance), [appearance]);
  const BrandIcon = { network: Network, activity: Activity, gauge: Gauge, workflow: Workflow }[appearance.icon];

  async function load() {
    try {
      const [nextOverview, nextOrchestrators, nextAppliances, nextProfiles, nextSamples] = await Promise.all([
        api.overview(), api.orchestrators(), api.appliances(), api.profiles(), api.samples()
      ]);
      setOverview(nextOverview);
      setOrchestrators(nextOrchestrators);
      setSelectedOrchestrator((current) => nextOrchestrators.some((item) => item.id === current) ? current : (nextOrchestrators[0]?.id ?? ""));
      setAppliances(nextAppliances);
      setProfiles(nextProfiles);
      setSamples(nextSamples);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible consultar la API");
    }
  }

  function logout() {
    void api.logout().catch(() => undefined);
    window.sessionStorage.removeItem("dashboardapi-session-token");
    configureSessionToken("");
    setIdentity(null);
    setOverview(null);
    setOrchestrators([]);
    setAppliances([]);
    setSamples([]);
    setView("dashboard");
  }

  useEffect(() => {
    api.appearance().then(setAppearance).catch(() => undefined);
    const stored = window.sessionStorage.getItem("dashboardapi-session-token");
    if (!stored) { setSessionChecked(true); return; }
    configureSessionToken(stored);
    api.me()
      .then((nextIdentity) => { setIdentity(nextIdentity); setSessionChecked(true); })
      .catch(() => {
        window.sessionStorage.removeItem("dashboardapi-session-token");
        configureSessionToken("");
        setSessionChecked(true);
      });
  }, []);

  useEffect(() => { if (identity) { void load(); } }, [identity]);
  useEffect(() => {
    if (!selectedOrchestrator) { setDashboard(null); return; }
    api.dashboard(selectedOrchestrator).then(setDashboard).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [selectedOrchestrator, samples, appliances]);

  if (!sessionChecked) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
          <Typography color="text.secondary">Verificando sesión…</Typography>
        </Box>
      </ThemeProvider>
    );
  }

  if (!identity) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <LoginScreen onAuthenticated={(token) => {
          configureSessionToken(token);
          api.me().then(setIdentity).catch(() => {
            window.sessionStorage.removeItem("dashboardapi-session-token");
            configureSessionToken("");
          });
        }} />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default", display: "flex" }}>
        <Box
          component="aside"
          sx={{
            width: 232,
            p: 2,
            borderRight: "1px solid rgba(255,255,255,.07)",
            bgcolor: appearance.header,
            display: { xs: "none", md: "flex" },
            flexDirection: "column",
            position: "fixed",
            inset: "0 auto 0 0"
          }}
        >
          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ px: 1, py: 1.5, mb: 2 }}>
            <Box sx={{ width: 34, height: 34, display: "grid", placeItems: "center", borderRadius: 2, bgcolor: "primary.main", color: "#07110E" }}>
              <BrandIcon size={20} />
            </Box>
            <Box>
              <Typography fontWeight={900} lineHeight={1.1}>{appearance.panel_name}</Typography>
              <Typography variant="caption" color="primary.main">EdgeConnect · 1.3</Typography>
            </Box>
          </Stack>
          <Stack spacing={0.75}>
            {navigation.map((item) => (
              <Button
                key={item.label}
                color={(item.id === "summary" && view === "dashboard") || view === item.view && item.view !== "dashboard" ? "primary" : "inherit"}
                startIcon={item.icon}
                onClick={() => setView(item.view)}
                sx={{ justifyContent: "flex-start", px: 1.5, bgcolor: (item.id === "summary" && view === "dashboard") || view === item.view && item.view !== "dashboard" ? "rgba(47,191,155,.1)" : "transparent" }}
              >
                {item.label}
              </Button>
            ))}
          </Stack>
          <Paper sx={{ mt: "auto", p: 1.5, bgcolor: "rgba(47,191,155,.07)" }}>
            <Typography variant="caption" color="text.secondary">Plataforma</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
              <ShieldCheck size={17} color="#53C57B" />
              <Typography variant="body2" fontWeight={800}>1.3 stable</Typography>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
                {identity.username} · {identity.role}
              </Typography>
              <Button size="small" startIcon={<LogOut size={15} />} onClick={logout} sx={{ minWidth: 0, px: 1 }}>Salir</Button>
            </Stack>
          </Paper>
        </Box>

        <Box component="main" sx={{ flex: 1, ml: { xs: 0, md: "232px" }, minWidth: 0 }}>
          <Box sx={{ p: { xs: 2, md: 3.5 }, maxWidth: 1500, mx: "auto" }}>
            <Stack direction={{ xs: "column", xl: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", xl: "center" }} spacing={2} sx={{ mb: 3 }}>
              <Box>
                <Typography variant="h1">{view === "tryme" ? "Laboratorio de APIs" : view === "access" ? "Control de acceso" : "Estado de la red"}</Typography>
                <Typography color="text.secondary">{view === "tryme" ? "Explora, ejecuta y conserva salidas de los Swagger conectados." : view === "access" ? "Gestiona usuarios, roles y auditoría del dashboard." : appearance.welcome_message}</Typography>
              </Box>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} useFlexGap flexWrap="wrap">
                {view !== "access" && orchestrators.length ? <Select size="small" value={selectedOrchestrator} onChange={(event) => setSelectedOrchestrator(event.target.value)} sx={{ minWidth: 220 }}>{orchestrators.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.api_version ?? "sin validar"}</MenuItem>)}</Select> : null}
                {view !== "access" && <Button variant="contained" startIcon={<Plus size={17} />} onClick={() => setWizardOpen(true)}>Conectar Orchestrator</Button>}
                {view !== "access" && <Button variant="outlined" startIcon={<ShieldCheck size={17} />} onClick={() => setTlsOpen(true)}>Certificado HTTPS</Button>}
                {view !== "access" && <Button variant="outlined" startIcon={<Palette size={17} />} onClick={() => setAppearanceOpen(true)}>Apariencia</Button>}
                {view !== "access" && <Button variant="outlined" startIcon={<Download size={17} />} onClick={() => setUpdateOpen(true)}>Actualizar</Button>}
              </Stack>
            </Stack>

            {error ? <Paper sx={{ p: 2, mb: 2, borderColor: "error.main" }}><Typography color="error">{error}</Typography></Paper> : null}

            {view === "tryme" ? <Suspense fallback={<Paper sx={{ p: 4 }}><Typography color="text.secondary">Cargando Swagger Explorer…</Typography></Paper>}><TryMePage orchestrators={orchestrators} selectedId={selectedOrchestrator} onSelect={setSelectedOrchestrator} /></Suspense> : view === "access" ? <AccessControlPanel identity={identity} onNotice={setError} onLogout={logout} /> : <Grid container spacing={2}>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Orchestrators" value={overview?.orchestrators ?? 0} detail="Conexiones configuradas" icon={<Network size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Appliances" value={overview?.appliances ?? 0} detail={`${overview?.selected_appliances ?? 0} seleccionados`} icon={<Activity size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Perfiles API" value={overview?.compatibility_profiles ?? profiles.length} detail="9.3–9.6 · 9.7 usa API 9.6" icon={<Database size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Muestras API" value={overview?.services?.api_samples ?? "0"} detail="Trazabilidad disponible" icon={<ShieldCheck size={22} />} /></Grid>
              <Grid item xs={12}><DynamicDashboard dashboard={dashboard} /></Grid>
              <Grid item xs={12}><OrchestratorPanel items={orchestrators} onChanged={load} onAdd={() => setWizardOpen(true)} /></Grid>
              <Grid item xs={12} lg={5}><CompatibilityPanel profiles={profiles} /></Grid>
              <Grid item xs={12} lg={7}><AppliancePanel items={appliances} onChanged={load} /></Grid>
              <Grid item xs={12}><SamplesPanel items={samples} /></Grid>
            </Grid>}
            <Typography component="footer" variant="caption" color="text.secondary" textAlign="center" sx={{ display: "block", py: 3 }}>Powered by Emilio Abundis</Typography>
          </Box>
        </Box>
      </Box>
      <SetupWizard open={wizardOpen} onClose={() => setWizardOpen(false)} onComplete={load} />
      {tlsOpen && <TlsDialog onClose={() => setTlsOpen(false)} />}
      {appearanceOpen && <AppearanceDialog value={appearance} onClose={() => setAppearanceOpen(false)} onSaved={setAppearance} />}
      {updateOpen && <UpdateDialog onClose={() => setUpdateOpen(false)} />}
    </ThemeProvider>
  );
}

export default App;
