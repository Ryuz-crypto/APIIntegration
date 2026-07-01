import { Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { StatusChip } from "../../components/StatusChip";
import { ApiSample } from "../../lib/api";

export function SamplesPanel({ items }: { items: ApiSample[] }) {
  return (
    <Paper sx={{ p: 2 }}>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}
