import { Box, CssBaseline, Grid, Paper, ThemeProvider, Typography } from "@mui/material";
import { Activity, Database, Network, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { MetricCard } from "./components/MetricCard";
import { AppliancePanel } from "./features/appliances/AppliancePanel";
import { OrchestratorPanel } from "./features/orchestrators/OrchestratorPanel";
import { CompatibilityPanel } from "./features/system/CompatibilityPanel";
import { api, Appliance, CompatibilityProfile, Orchestrator, SystemOverview } from "./lib/api";
import { theme } from "./theme/theme";

function App() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [orchestrators, setOrchestrators] = useState<Orchestrator[]>([]);
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [profiles, setProfiles] = useState<CompatibilityProfile[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [nextOverview, nextOrchestrators, nextAppliances, nextProfiles] = await Promise.all([
        api.overview(),
        api.orchestrators(),
        api.appliances(),
        api.profiles()
      ]);
      setOverview(nextOverview);
      setOrchestrators(nextOrchestrators);
      setAppliances(nextAppliances);
      setProfiles(nextProfiles);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown API error");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default", p: { xs: 2, md: 3 } }}>
        <Box
          component="header"
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
            mb: 3
          }}
        >
          <Box>
            <Typography variant="h1">DashboardAPI-EC</Typography>
            <Typography color="text.secondary">EdgeConnect NOC/SOC platform foundation</Typography>
          </Box>
          <Paper sx={{ px: 1.5, py: 1, color: "primary.main" }}>
            <ShieldCheck size={22} />
          </Paper>
        </Box>

        {error ? (
          <Paper sx={{ p: 2, mb: 2, borderColor: "error.main" }}>
            <Typography color="error">{error}</Typography>
          </Paper>
        ) : null}

        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="Orchestrators"
              value={overview?.orchestrators ?? 0}
              detail="Inventory and topology polling"
              icon={<Network size={22} />}
            />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="Appliances"
              value={overview?.appliances ?? 0}
              detail={`${overview?.selected_appliances ?? 0} selected`}
              icon={<Activity size={22} />}
            />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="API Profiles"
              value={overview?.compatibility_profiles ?? profiles.length}
              detail="9.3 through 9.6"
              icon={<Database size={22} />}
            />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="Services"
              value="Ready"
              detail="API, DB, Redis, worker"
              icon={<ShieldCheck size={22} />}
            />
          </Grid>
          <Grid item xs={12} lg={7}>
            <OrchestratorPanel items={orchestrators} onChanged={load} />
          </Grid>
          <Grid item xs={12} lg={5}>
            <CompatibilityPanel profiles={profiles} />
          </Grid>
          <Grid item xs={12}>
            <AppliancePanel items={appliances} />
          </Grid>
        </Grid>
      </Box>
    </ThemeProvider>
  );
}

export default App;
