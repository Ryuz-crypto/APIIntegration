import {
  Box,
  Button,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { Activity } from "lucide-react";
import { useState } from "react";
import { StatusChip } from "../../components/StatusChip";
import { api, Appliance } from "../../lib/api";

export function AppliancePanel({ items, onChanged }: { items: Appliance[]; onChanged: () => void }) {
  const [message, setMessage] = useState<string | null>(null);

  async function collect(id: string) {
    try {
      await api.collectAppliance(id);
      setMessage(null);
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Collection failed");
    }
  }

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h2" sx={{ mb: 2 }}>
        Appliances
      </Typography>
      {message ? (
        <Typography sx={{ mb: 2 }} color="error" variant="body2">
          {message}
        </Typography>
      ) : null}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Hostname</TableCell>
            <TableCell>Site</TableCell>
            <TableCell>Version</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Last metrics</TableCell>
            <TableCell>Read</TableCell>
            <TableCell align="right">Collect</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.hostname}</TableCell>
              <TableCell>{item.site ?? "unset"}</TableCell>
              <TableCell>{item.software_version ?? "unknown"}</TableCell>
              <TableCell>
                <StatusChip status={item.status} />
              </TableCell>
              <TableCell>
                <MetricSummary metrics={item.last_metrics} />
              </TableCell>
              <TableCell>
                <Stack spacing={0.25}>
                  <Typography variant="body2">
                    {item.last_status_code ? `HTTP ${item.last_status_code}` : "not sampled"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {item.last_latency_ms ? `${item.last_latency_ms} ms` : "-"}
                  </Typography>
                </Stack>
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => collect(item.id)} startIcon={<Activity size={15} />}>
                  Metrics
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}

function MetricSummary({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics ?? {}).slice(0, 4);
  if (entries.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        no values
      </Typography>
    );
  }
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
      {entries.map(([key, value]) => (
        <Typography
          key={key}
          variant="caption"
          sx={{ bgcolor: "rgba(255,255,255,0.06)", borderRadius: 1, px: 0.75, py: 0.25 }}
        >
          {key}: {String(value)}
        </Typography>
      ))}
    </Box>
  );
}
