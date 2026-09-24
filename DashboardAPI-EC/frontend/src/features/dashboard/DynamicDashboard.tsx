import { Box, Button, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { Braces, CircleOff, Clock3 } from "lucide-react";
import { useState } from "react";
import { Dashboard, DashboardWidget } from "../../lib/api";
import { ApiInspector } from "../system/ApiInspector";

export function DynamicDashboard({ dashboard }: { dashboard: Dashboard | null }) {
  const [sampleId, setSampleId] = useState<string | null>(null);
  if (!dashboard) return null;
  return (
    <>
      <Paper sx={{ p: { xs: 2, md: 2.5 }, background: "linear-gradient(135deg, rgba(47,191,155,.08), rgba(20,26,29,.82) 45%)" }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 2.5 }}>
          <Box>
            <Typography variant="overline" color="primary.main">Dashboard ensamblado · API {dashboard.api_version ?? "por detectar"}</Typography>
            <Typography variant="h2">{dashboard.orchestrator_name}</Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">Generado {new Date(dashboard.generated_at).toLocaleString()}</Typography>
        </Stack>
        {dashboard.sections.map((section) => (
          <Box key={section.id} sx={{ mb: 3, "&:last-child": { mb: 0 } }}>
            <Typography variant="h3" sx={{ mb: 1.5 }}>{section.title}</Typography>
            <Grid container spacing={1.5}>
              {section.widgets.map((widget) => (
                <Grid item xs={12} md={widget.visualization === "timeseries" ? 8 : 4} key={widget.id}>
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
    <Paper variant="outlined" sx={{ p: 2, height: "100%", opacity: muted ? 0.55 : 1, bgcolor: "rgba(8,12,14,.48)" }}>
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
          {widget.data.slice(0, 5).map((row, index) => <Stack key={`${String(row.name)}-${index}`} direction="row" justifyContent="space-between"><Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: "65%" }}>{String(row.hostname ?? "")} · {String(row.name)}</Typography><Typography variant="caption" fontWeight={800}>{String(row.value)} {String(row.unit ?? "")}</Typography></Stack>)}
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
