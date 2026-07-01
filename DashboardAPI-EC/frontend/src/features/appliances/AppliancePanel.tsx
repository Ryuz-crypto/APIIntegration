import { Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { StatusChip } from "../../components/StatusChip";
import { Appliance } from "../../lib/api";

export function AppliancePanel({ items }: { items: Appliance[] }) {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h2" sx={{ mb: 2 }}>
        Appliances
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Hostname</TableCell>
            <TableCell>Site</TableCell>
            <TableCell>Version</TableCell>
            <TableCell>Status</TableCell>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}
