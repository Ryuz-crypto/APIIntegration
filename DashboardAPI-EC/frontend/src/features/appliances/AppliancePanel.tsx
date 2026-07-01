import { Button, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
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
