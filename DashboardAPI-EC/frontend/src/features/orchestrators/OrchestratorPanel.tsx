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
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import { PlugZap, Radar, RefreshCw } from "lucide-react";
import { FormEvent, useState } from "react";
import { StatusChip } from "../../components/StatusChip";
import { api, Orchestrator } from "../../lib/api";

type Props = {
  items: Orchestrator[];
  onChanged: () => void;
};

export function OrchestratorPanel({ items, onChanged }: Props) {
  const [name, setName] = useState("Lab Orchestrator");
  const [baseUrl, setBaseUrl] = useState("https://orchestrator.example.local");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await api.createOrchestrator({ name, base_url: baseUrl, credential_label: "phase-1-secret" });
    onChanged();
  }

  async function validate(id: string) {
    await api.validateOrchestrator(id);
    onChanged();
  }

  async function discover(id: string) {
    await api.discoverAppliances(id);
    onChanged();
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
        <Button type="submit" variant="contained" startIcon={<PlugZap size={16} />}>
          Add Orchestrator
        </Button>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>API</TableCell>
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
