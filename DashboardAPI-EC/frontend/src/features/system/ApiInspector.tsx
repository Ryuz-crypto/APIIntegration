import {
  Box, CircularProgress, Drawer, IconButton, Stack, Tab, Tabs, Typography
} from "@mui/material";
import { Copy, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiTrace } from "../../lib/api";

export function ApiInspector({ sampleId, onClose }: { sampleId: string | null; onClose: () => void }) {
  const [trace, setTrace] = useState<ApiTrace | null>(null);
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sampleId) return;
    setTrace(null);
    setError(null);
    setTab(0);
    api.trace(sampleId).then(setTrace).catch((reason) => setError(String(reason)));
  }, [sampleId]);

  const code = trace ? [trace.code_examples.curl, trace.code_examples.python, trace.code_examples.javascript][tab] : "";

  return (
    <Drawer anchor="right" open={Boolean(sampleId)} onClose={onClose} PaperProps={{ sx: { width: { xs: "100%", md: 620 }, bgcolor: "#101416" } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 3, py: 2, borderBottom: "1px solid rgba(255,255,255,.08)" }}>
        <Box>
          <Typography variant="overline" color="primary.main">Inspector API</Typography>
          <Typography variant="h2">{trace?.operation_id ?? "Cargando evidencia"}</Typography>
        </Box>
        <IconButton onClick={onClose}><X /></IconButton>
      </Stack>
      {!trace && !error ? <Box sx={{ p: 5, textAlign: "center" }}><CircularProgress /></Box> : null}
      {error ? <Typography color="error" sx={{ p: 3 }}>{error}</Typography> : null}
      {trace ? (
        <Box sx={{ p: 3, overflow: "auto" }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 2 }}>
            <Badge text={trace.method} accent />
            <Badge text={`HTTP ${trace.status_code ?? "-"}`} />
            <Badge text={`${trace.duration_ms ?? "-"} ms`} />
            <Badge text={`API ${trace.api_version ?? "-"}`} />
          </Stack>
          <Typography variant="caption" color="text.secondary">Ruta invocada</Typography>
          <CodeBlock value={trace.path} />

          <Typography variant="h3" sx={{ mt: 3, mb: 1 }}>Valores utilizados</Typography>
          <CodeBlock value={JSON.stringify(trace.request_params, null, 2)} />
          <Typography variant="h3" sx={{ mt: 3, mb: 1 }}>Valores extraídos</Typography>
          <CodeBlock value={JSON.stringify(trace.extracted_values, null, 2)} />
          {trace.transformations.length ? (
            <Box sx={{ mt: 3 }}>
              <Typography variant="h3" sx={{ mb: 1 }}>Transformaciones</Typography>
              {trace.transformations.map((item) => <Typography key={item} color="text.secondary">• {item}</Typography>)}
            </Box>
          ) : null}
          <Typography variant="h3" sx={{ mt: 3, mb: 1 }}>Respuesta sanitizada</Typography>
          <CodeBlock value={JSON.stringify(trace.sanitized_payload, null, 2)} />

          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 3 }}>
            <Tabs value={tab} onChange={(_, value) => setTab(value)}>
              <Tab label="cURL" /><Tab label="Python" /><Tab label="JavaScript" />
            </Tabs>
            <IconButton title="Copiar ejemplo" onClick={() => void navigator.clipboard.writeText(code)}><Copy size={17} /></IconButton>
          </Stack>
          <CodeBlock value={code} />
        </Box>
      ) : null}
    </Drawer>
  );
}

function Badge({ text, accent = false }: { text: string; accent?: boolean }) {
  return <Box sx={{ px: 1.25, py: 0.5, borderRadius: 4, bgcolor: accent ? "rgba(47,191,155,.16)" : "rgba(255,255,255,.06)", color: accent ? "primary.main" : "text.secondary", fontSize: 12, fontWeight: 800 }}>{text}</Box>;
}

function CodeBlock({ value }: { value: string }) {
  return <Box component="pre" sx={{ m: 0, mt: 0.75, p: 1.5, borderRadius: 2, bgcolor: "#080B0D", border: "1px solid rgba(255,255,255,.07)", color: "#C9D5D1", fontSize: 12, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{value}</Box>;
}
