import { Box, Paper, Typography } from "@mui/material";
import type { ReactNode } from "react";

type MetricCardProps = {
  label: string;
  value: string | number;
  detail: string;
  icon: ReactNode;
};

export function MetricCard({ label, value, detail, icon }: MetricCardProps) {
  return (
    <Paper sx={{ p: 2, minHeight: 118 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
        <Box sx={{ color: "primary.main", display: "grid", placeItems: "center" }}>{icon}</Box>
      </Box>
      <Typography sx={{ mt: 1, fontSize: "2rem", fontWeight: 700 }}>{value}</Typography>
      <Typography variant="body2" color="text.secondary">
        {detail}
      </Typography>
    </Paper>
  );
}
