import { Box, Button, Chip, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { Activity, Braces, CircleOff, Clock3 } from "lucide-react";
import { useState } from "react";
import { alpha } from "@mui/material/styles";
import { Dashboard, DashboardWidget } from "../../lib/api";
import { ApiInspector } from "../system/ApiInspector";

export function DynamicDashboard({ dashboard, liveState, lastEvent }: { dashboard: Dashboard | null; liveState: "connecting" | "live" | "offline"; lastEvent: string | null }) {
  const [sampleId, setSampleId] = useState<string | null>(null);
  if (!dashboard) return null;
  return (
    <>
      <Paper sx={(theme) => ({ p: { xs: 2, md: 2.5 }, background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, .08)}, ${theme.palette.background.paper} 45%)` })}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 2.5 }}>
          <Box>
            <Typography variant="overline" color="primary.main">Dashboard ensamblado · API {dashboard.api_version ?? "por detectar"}</Typography>
            <Typography variant="h2">{dashboard.orchestrator_name}</Typography>
          </Box>
          <Stack alignItems={{ md: "flex-end" }} spacing={.75}>
            <Chip icon={<Activity size={14} />} size="small" color={liveState === "live" ? "success" : liveState === "connecting" ? "warning" : "error"} label={liveState === "live" ? "WebSocket · EN VIVO" : liveState === "connecting" ? "Conectando…" : "Reconectando"} sx={liveState === "live" ? { "& .MuiChip-icon": { animation: "pulse 1.4s infinite" }, "@keyframes pulse": { "50%": { opacity: .25 } } } : undefined} />
            <Typography variant="caption" color="text.secondary">Actualizado {new Date(lastEvent ?? dashboard.generated_at).toLocaleString()}</Typography>
          </Stack>
        </Stack>
        {dashboard.sections.map((section) => (
          <Box key={section.id} sx={{ mb: 3, "&:last-child": { mb: 0 } }}>
            <Typography variant="h3" sx={{ mb: 1.5 }}>{section.title}</Typography>
            <Grid container spacing={1.5}>
              {section.widgets.map((widget) => (
                <Grid item xs={12} md={widget.visualization === "timeseries" || widget.id === "site-risk" ? 8 : 4} key={widget.id}>
                  <WidgetCard widget={widget} inspect={() => setSampleId(widget.provenance?.sample_id ?? null)} />
                </Grid>
              ))}
            </Grid>
          </Box>
        ))}
      </Paper>
      <ApiInspector sampleId={sampleId} onClose={() => setSampleId(null)} />
    </>
  );
}

function WidgetCard({ widget, inspect }: { widget: DashboardWidget; inspect: () => void }) {
  const muted = widget.status === "unavailable";
  return (
    <Paper variant="outlined" sx={{ p: 2, height: "100%", opacity: muted ? 0.55 : 1, bgcolor: "rgba(8,12,14,.48)", borderTop: "2px solid", borderTopColor: widget.id === "fleet-health" ? "primary.main" : "divider" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
        <Box>
          <Typography fontWeight={850}>{widget.title}</Typography>
          <Typography variant="caption" color="text.secondary">{widget.description}</Typography>
        </Box>
        {widget.status === "unavailable" ? <CircleOff size={18} /> : widget.status === "waiting" ? <Clock3 size={18} /> : null}
      </Stack>
      {widget.value !== null ? <Typography sx={{ fontSize: 34, fontWeight: 900, mt: 1.5 }}>{widget.value}<Box component="span" sx={{ ml: 0.5, fontSize: 13, color: "text.secondary" }}>{widget.unit}</Box></Typography> : null}
      {widget.visualization === "bars" ? <Bars data={widget.data} /> : null}
      {widget.visualization === "timeseries" && widget.data.length ? (
        <Stack spacing={0.75} sx={{ mt: 1.5 }}>
          <Sparkline values={widget.data.slice(0, 24).map((row) => Number(row.value ?? 0)).reverse()} />
          {widget.data.slice(0, 5).map((row, index) => <Stack key={`${String(row.name)}-${index}`} direction="row" justifyContent="space-between"><Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: "65%" }}>{String(row.hostname ?? "")} · {String(row.name)}</Typography><Typography variant="caption" fontWeight={800}>{String(row.value)} {String(row.unit ?? "")}</Typography></Stack>)}
        </Stack>
      ) : null}
      {widget.visualization === "table" && widget.data.length ? (
        <Stack spacing={0.75} sx={{ mt: 1.5 }}>
          {widget.data.slice(0, 5).map((row, index) => {
            const entries = Object.entries(row).slice(0, 3);
            return <Stack key={index} direction="row" justifyContent="space-between" spacing={1} sx={{ borderBottom: "1px solid", borderColor: "divider", pb: 0.6 }}>
              <Typography variant="caption" noWrap sx={{ maxWidth: "45%" }}>{String(entries[0]?.[1] ?? `Fila ${index + 1}`)}</Typography>
              <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: "55%" }}>{entries.slice(1).map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</Typography>
            </Stack>;
          })}
        </Stack>
      ) : null}
      {widget.reason ? <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>{widget.reason}</Typography> : null}
      <Button size="small" startIcon={<Braces size={14} />} disabled={!widget.provenance?.sample_id} onClick={inspect} sx={{ mt: 1.5, px: 0 }}>Ver API utilizada</Button>
    </Paper>
  );
}

function Bars({ data }: { data: Array<Record<string, unknown>> }) {
  const max = Math.max(1, ...data.map((row) => Number(row.value ?? 0)));
  return <Stack spacing={1} sx={{ mt: 1.5 }}>{data.map((row) => <Box key={String(row.label)}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{String(row.label)}</Typography><Typography variant="caption" fontWeight={800}>{String(row.value)}</Typography></Stack><LinearProgress variant="determinate" value={Number(row.value ?? 0) * 100 / max} sx={{ mt: 0.5, height: 5, borderRadius: 3 }} /></Box>)}</Stack>;
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
  const points = values.map((value, index) => `${index * 100 / (values.length - 1)},${36 - ((value - min) * 32 / span)}`).join(" ");
  return <Box component="svg" viewBox="0 0 100 40" preserveAspectRatio="none" sx={{ width: "100%", height: 62, color: "primary.main" }}><polyline fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" points={points} /></Box>;
}
