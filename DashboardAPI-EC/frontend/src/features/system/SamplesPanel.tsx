import { IconButton, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { Braces } from "lucide-react";
import { useState } from "react";
import { StatusChip } from "../../components/StatusChip";
import { ApiSample } from "../../lib/api";
import { ApiInspector } from "./ApiInspector";

export function SamplesPanel({ items }: { items: ApiSample[] }) {
  const [sampleId, setSampleId] = useState<string | null>(null);
  return (
    <><Paper sx={{ p: 2 }}>
      <Typography variant="h2" sx={{ mb: 2 }}>
        Real API Samples
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Operation</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>HTTP</TableCell>
            <TableCell>Latency</TableCell>
            <TableCell>Path</TableCell>
            <TableCell align="right">Inspect</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.slice(0, 8).map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.operation_id}</TableCell>
              <TableCell>
                <StatusChip status={item.ok ? "ok" : "down"} />
              </TableCell>
              <TableCell>{item.status_code ?? "-"}</TableCell>
              <TableCell>{item.duration_ms ? `${item.duration_ms} ms` : "-"}</TableCell>
              <TableCell>{item.path}</TableCell>
              <TableCell align="right"><IconButton size="small" onClick={() => setSampleId(item.id)}><Braces size={16} /></IconButton></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper><ApiInspector sampleId={sampleId} onClose={() => setSampleId(null)} /></>
  );
}
