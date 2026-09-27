import {
  Activity, Gauge, Network, Palette, RotateCcw, Save, Workflow
} from "lucide-react";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Grid, MenuItem, Paper, Stack, TextField, Typography
} from "@mui/material";
import { useEffect, useState } from "react";
import { api, type AppearanceSettings } from "../../lib/api";
import { defaultAppearance } from "../../theme/theme";

const icons = { network: Network, activity: Activity, gauge: Gauge, workflow: Workflow };
const fonts = {
  inter: "Inter", system: "Sistema", humanist: "Humanista",
  technical: "Técnica", mono: "Monoespaciada"
};
const colors: Array<[keyof AppearanceSettings, string]> = [
  ["primary", "Principal"], ["secondary", "Secundario"], ["header", "Encabezado"],
  ["background", "Fondo"], ["surface", "Paneles"], ["text", "Texto"]
];

export function AppearanceDialog({ value, onClose, onSaved }: {
  value: AppearanceSettings;
  onClose: () => void;
  onSaved: (value: AppearanceSettings) => void;
}) {
  const [draft, setDraft] = useState(value);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setDraft(value), [value]);
  const PreviewIcon = icons[draft.icon];

  async function save() {
    setBusy(true); setError("");
    try { onSaved(await api.updateAppearance(draft)); onClose(); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar la apariencia."); }
    finally { setBusy(false); }
  }

  return <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="md">
    <DialogTitle><Stack direction="row" spacing={1} alignItems="center"><Palette size={21} /><span>Apariencia del dashboard</span></Stack></DialogTitle>
    <DialogContent>
      <Grid container spacing={2} sx={{ pt: 1 }}>
        <Grid item xs={12} md={7}>
          <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            <TextField label="Nombre del panel" value={draft.panel_name} inputProps={{ maxLength: 80 }} onChange={(event) => setDraft({ ...draft, panel_name: event.target.value })} />
            <TextField label="Mensaje principal" value={draft.welcome_message} inputProps={{ maxLength: 240 }} multiline minRows={2} onChange={(event) => setDraft({ ...draft, welcome_message: event.target.value })} />
            <TextField select label="Tipografía" value={draft.font} onChange={(event) => setDraft({ ...draft, font: event.target.value as AppearanceSettings["font"] })}>
              {Object.entries(fonts).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
            </TextField>
            <Box>
              <Typography variant="body2" fontWeight={800} sx={{ mb: 1 }}>Icono principal</Typography>
              <Stack direction="row" spacing={1}>{Object.entries(icons).map(([name, Icon]) => <Button key={name} variant={draft.icon === name ? "contained" : "outlined"} aria-label={`Icono ${name}`} onClick={() => setDraft({ ...draft, icon: name as AppearanceSettings["icon"] })}><Icon size={20} /></Button>)}</Stack>
            </Box>
            <Grid container spacing={1.5}>{colors.map(([key, label]) => <Grid item xs={6} sm={4} key={key}>
              <TextField fullWidth label={label} type="color" value={String(draft[key])} InputLabelProps={{ shrink: true }} inputProps={{ "aria-label": `Color ${label}` }} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} />
            </Grid>)}</Grid>
          </Stack>
        </Grid>
        <Grid item xs={12} md={5}>
          <Paper sx={{ overflow: "hidden", bgcolor: draft.background, color: draft.text, borderColor: draft.primary }}>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ p: 2, bgcolor: draft.header, color: draft.text }}>
              <Box sx={{ width: 42, height: 42, display: "grid", placeItems: "center", borderRadius: 2, bgcolor: draft.primary, color: draft.header }}><PreviewIcon size={25} /></Box>
              <Box><Typography fontWeight={900}>{draft.panel_name}</Typography><Typography variant="caption">Powered by Emilio Abundis</Typography></Box>
            </Stack>
            <Box sx={{ p: 2 }}><Typography color={draft.secondary} fontWeight={800}>Vista previa</Typography><Typography variant="body2" sx={{ mt: 1 }}>{draft.welcome_message}</Typography><Paper sx={{ mt: 2, p: 1.5, bgcolor: draft.surface, color: draft.text }}>Panel de ejemplo</Paper></Box>
          </Paper>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>La apariencia se guarda en el servidor y se aplica a todos los usuarios. La atribución permanece visible.</Typography>
        </Grid>
      </Grid>
    </DialogContent>
    <DialogActions>
      <Button startIcon={<RotateCcw size={16} />} onClick={() => setDraft(defaultAppearance)}>Restablecer</Button>
      <Button onClick={onClose} disabled={busy}>Cancelar</Button>
      <Button variant="contained" startIcon={<Save size={16} />} disabled={busy || draft.panel_name.trim().length < 3} onClick={() => void save()}>Guardar apariencia</Button>
    </DialogActions>
  </Dialog>;
}
