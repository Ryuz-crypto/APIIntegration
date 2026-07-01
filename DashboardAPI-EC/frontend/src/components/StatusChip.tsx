import { Chip } from "@mui/material";

const colorByStatus: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
  ready: "success",
  ok: "success",
  validated: "success",
  supported: "success",
  configured: "info",
  pending: "warning",
  preview: "warning",
  down: "error"
};

export function StatusChip({ status }: { status: string }) {
  return <Chip size="small" label={status} color={colorByStatus[status] ?? "default"} />;
}
