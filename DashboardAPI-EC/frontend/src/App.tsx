import { Box, Button, CssBaseline, Grid, MenuItem, Paper, Select, Stack, ThemeProvider, Typography } from "@mui/material";
import { Activity, Boxes, Database, Gauge, Network, Plus, RadioTower, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { MetricCard } from "./components/MetricCard";
import { AppliancePanel } from "./features/appliances/AppliancePanel";
import { DynamicDashboard } from "./features/dashboard/DynamicDashboard";
import { OrchestratorPanel } from "./features/orchestrators/OrchestratorPanel";
import { SetupWizard } from "./features/setup/SetupWizard";
import { CompatibilityPanel } from "./features/system/CompatibilityPanel";
import { SamplesPanel } from "./features/system/SamplesPanel";
import { TlsDialog } from "./features/system/TlsDialog";
import { api, ApiSample, Appliance, CompatibilityProfile, Dashboard, Orchestrator, SystemOverview } from "./lib/api";
import { theme } from "./theme/theme";

const navigation = [
  { label: "Resumen", icon: <Gauge size={18} />, active: true },
  { label: "Orchestrators", icon: <RadioTower size={18} /> },
  { label: "Appliances", icon: <Boxes size={18} /> },
  { label: "API Explorer", icon: <Database size={18} /> }
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

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!selectedOrchestrator) { setDashboard(null); return; }
    api.dashboard(selectedOrchestrator).then(setDashboard).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [selectedOrchestrator, samples, appliances]);

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
            bgcolor: "#0C0F11",
            display: { xs: "none", md: "flex" },
            flexDirection: "column",
            position: "fixed",
            inset: "0 auto 0 0"
          }}
        >
          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ px: 1, py: 1.5, mb: 2 }}>
            <Box sx={{ width: 34, height: 34, display: "grid", placeItems: "center", borderRadius: 2, bgcolor: "primary.main", color: "#07110E" }}>
              <Network size={20} />
            </Box>
            <Box>
              <Typography fontWeight={900} lineHeight={1.1}>DashboardAPI</Typography>
              <Typography variant="caption" color="primary.main">EdgeConnect · 1.0</Typography>
            </Box>
          </Stack>
          <Stack spacing={0.75}>
            {navigation.map((item) => (
              <Button
                key={item.label}
                color={item.active ? "primary" : "inherit"}
                startIcon={item.icon}
                sx={{ justifyContent: "flex-start", px: 1.5, bgcolor: item.active ? "rgba(47,191,155,.1)" : "transparent" }}
              >
                {item.label}
              </Button>
            ))}
          </Stack>
          <Paper sx={{ mt: "auto", p: 1.5, bgcolor: "rgba(47,191,155,.07)" }}>
            <Typography variant="caption" color="text.secondary">Plataforma</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
              <ShieldCheck size={17} color="#53C57B" />
              <Typography variant="body2" fontWeight={800}>1.0 stable</Typography>
            </Stack>
          </Paper>
        </Box>

        <Box component="main" sx={{ flex: 1, ml: { xs: 0, md: "232px" }, minWidth: 0 }}>
          <Box sx={{ p: { xs: 2, md: 3.5 }, maxWidth: 1500, mx: "auto" }}>
            <Stack direction={{ xs: "column", xl: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", xl: "center" }} spacing={2} sx={{ mb: 3 }}>
              <Box>
                <Typography variant="h1">Estado de la red</Typography>
                <Typography color="text.secondary">Inventario y capacidades obtenidas desde las APIs de EdgeConnect</Typography>
              </Box>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} useFlexGap flexWrap="wrap">
                {orchestrators.length ? <Select size="small" value={selectedOrchestrator} onChange={(event) => setSelectedOrchestrator(event.target.value)} sx={{ minWidth: 220 }}>{orchestrators.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.api_version ?? "sin validar"}</MenuItem>)}</Select> : null}
                <Button variant="contained" startIcon={<Plus size={17} />} onClick={() => setWizardOpen(true)}>Conectar Orchestrator</Button>
                <Button variant="outlined" startIcon={<ShieldCheck size={17} />} onClick={() => setTlsOpen(true)}>Certificado HTTPS</Button>
              </Stack>
            </Stack>

            {error ? <Paper sx={{ p: 2, mb: 2, borderColor: "error.main" }}><Typography color="error">{error}</Typography></Paper> : null}

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Orchestrators" value={overview?.orchestrators ?? 0} detail="Conexiones configuradas" icon={<Network size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Appliances" value={overview?.appliances ?? 0} detail={`${overview?.selected_appliances ?? 0} seleccionados`} icon={<Activity size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Perfiles API" value={overview?.compatibility_profiles ?? profiles.length} detail="9.3 a 9.6" icon={<Database size={22} />} /></Grid>
              <Grid item xs={12} sm={6} lg={3}><MetricCard label="Muestras API" value={overview?.services?.api_samples ?? "0"} detail="Trazabilidad disponible" icon={<ShieldCheck size={22} />} /></Grid>
              <Grid item xs={12}><DynamicDashboard dashboard={dashboard} /></Grid>
              <Grid item xs={12}><OrchestratorPanel items={orchestrators} onChanged={load} onAdd={() => setWizardOpen(true)} /></Grid>
              <Grid item xs={12} lg={5}><CompatibilityPanel profiles={profiles} /></Grid>
              <Grid item xs={12} lg={7}><AppliancePanel items={appliances} onChanged={load} /></Grid>
              <Grid item xs={12}><SamplesPanel items={samples} /></Grid>
            </Grid>
          </Box>
        </Box>
      </Box>
      <SetupWizard open={wizardOpen} onClose={() => setWizardOpen(false)} onComplete={load} />
      {tlsOpen && <TlsDialog onClose={() => setTlsOpen(false)} />}
    </ThemeProvider>
  );
}

export default App;
