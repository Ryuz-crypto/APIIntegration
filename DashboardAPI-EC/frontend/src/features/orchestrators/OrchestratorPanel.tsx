import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { Cloud, Plus, Radar, RefreshCw, Server } from "lucide-react";
import { useState } from "react";
import { StatusChip } from "../../components/StatusChip";
import { api, Orchestrator } from "../../lib/api";

type Props = {
  items: Orchestrator[];
  onChanged: () => void;
  onAdd: () => void;
};

export function OrchestratorPanel({ items, onChanged, onAdd }: Props) {
  const [message, setMessage] = useState<string | null>(null);

  async function validate(item: Orchestrator) {
    if (item.auth_type === "session_otp") {
      setMessage("La sesión requiere un código OTP nuevo. Vuelve a ejecutar el asistente de conexión.");
      return;
    }
    try {
      await api.validateOrchestrator(item.id);
      setMessage(null);
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No fue posible validar el Orchestrator");
    }
  }

  return (
    <Paper sx={{ p: 2.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h2">Orchestrators</Typography>
          <Typography variant="body2" color="text.secondary">Conexiones y perfiles detectados</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button onClick={onChanged} color="inherit" startIcon={<RefreshCw size={15} />}>Actualizar</Button>
          <Button onClick={onAdd} variant="contained" startIcon={<Plus size={16} />}>Conectar</Button>
        </Stack>
      </Stack>

      {message ? <Typography color="warning.main" variant="body2" sx={{ mb: 2 }}>{message}</Typography> : null}

      <Stack spacing={1.25}>
        {items.length === 0 ? (
          <Box sx={{ py: 5, textAlign: "center", border: "1px dashed", borderColor: "divider", borderRadius: 2 }}>
            <Cloud size={30} color="#2FBF9B" />
            <Typography fontWeight={800} sx={{ mt: 1 }}>Conecta tu primer Orchestrator</Typography>
            <Typography variant="body2" color="text.secondary">Detectaremos versión, APIs e inventario automáticamente.</Typography>
          </Box>
        ) : items.map((item) => {
          const count = Object.keys(item.capabilities?.operations ?? {}).length;
          return (
            <Box
              key={item.id}
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "40px minmax(180px,1fr) 110px 90px 110px auto" },
                gap: 1.5,
                alignItems: "center",
                p: 1.5,
                borderRadius: 2,
                bgcolor: "rgba(255,255,255,.025)",
                border: "1px solid rgba(255,255,255,.06)"
              }}
            >
              <Box sx={{ color: "primary.main", display: { xs: "none", md: "grid" }, placeItems: "center" }}>
                {item.deployment_type === "oaas" ? <Cloud size={21} /> : <Server size={21} />}
              </Box>
              <Box>
                <Typography fontWeight={800}>{item.name}</Typography>
                <Typography variant="caption" color="text.secondary">{item.base_url}</Typography>
              </Box>
              <StatusChip status={item.status} />
              <Box>
                <Typography variant="caption" color="text.secondary">Versión</Typography>
                <Typography fontWeight={800}>{item.api_version ?? "—"}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Capacidades</Typography>
                <Typography fontWeight={800}>{count || "—"}</Typography>
              </Box>
              <Button size="small" onClick={() => validate(item)} startIcon={<Radar size={15} />}>Validar</Button>
            </Box>
          );
        })}
      </Stack>
    </Paper>
  );
}
