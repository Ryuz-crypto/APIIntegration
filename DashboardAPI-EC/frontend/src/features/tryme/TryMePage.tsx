import {
  Alert, Box, Button, Chip, Divider, Grid, IconButton, InputAdornment, List,
  ListItemButton, ListItemText, MenuItem, Paper, Select, Stack, Tab, Tabs,
  TextField, Tooltip, Typography
} from "@mui/material";
import {
  Camera, Download, FileJson, Play, Search, Trash2, Upload, X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  api, type Orchestrator, type TryMeCatalog, type TryMeOperation,
  type TryMeResult, type TryMeSnapshot
} from "../../lib/api";

type Props = { orchestrators: Orchestrator[]; selectedId: string; onSelect: (id: string) => void };
type VisibleOutput = TryMeResult | { response: Record<string, unknown>; request: Record<string, unknown>; response_headers: Record<string, string>; error?: string | null };

const methodColor: Record<string, "success" | "info" | "warning" | "error" | "secondary"> = {
  GET: "success", POST: "info", PUT: "warning", PATCH: "secondary", DELETE: "error"
};

export function TryMePage({ orchestrators, selectedId, onSelect }: Props) {
  const [catalog, setCatalog] = useState<TryMeCatalog>();
  const [selected, setSelected] = useState<TryMeOperation>();
  const [snapshots, setSnapshots] = useState<TryMeSnapshot[]>([]);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("all");
  const [values, setValues] = useState<Record<string, string>>({});
  const [body, setBody] = useState("");
  const [headers, setHeaders] = useState("{}");
  const [confirmation, setConfirmation] = useState("");
  const [result, setResult] = useState<VisibleOutput>();
  const [responseTab, setResponseTab] = useState(0);
  const [snapshotName, setSnapshotName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const upload = useRef<HTMLInputElement>(null);

  async function load(id = selectedId) {
    if (!id) return;
    setBusy(true); setError("");
    try {
      const [nextCatalog, nextSnapshots] = await Promise.all([api.tryMeCatalog(id), api.tryMeSnapshots(id)]);
      setCatalog(nextCatalog); setSnapshots(nextSnapshots);
      setSelected((current) => nextCatalog.operations.find((item) => item.operation_id === current?.operation_id) ?? nextCatalog.operations[0]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo cargar Try Me."); }
    finally { setBusy(false); }
  }

  useEffect(() => { void load(); }, [selectedId]);
  useEffect(() => {
    if (!selected) return;
    const defaults: Record<string, string> = {};
    selected.parameters.forEach((parameter) => {
      const example = parameter.example;
      defaults[`${parameter.location}:${parameter.name}`] = example == null ? "" : String(example);
    });
    setValues(defaults);
    const example = selected.request_example ?? schemaExample(selected.request_schema);
    setBody(example == null ? "" : JSON.stringify(example, null, 2));
    setHeaders("{}"); setConfirmation(""); setResult(undefined); setError("");
  }, [selected?.operation_id]);

  const tags = useMemo(() => Array.from(new Set(catalog?.operations.flatMap((item) => item.tags) ?? [])).sort(), [catalog]);
  const filtered = useMemo(() => (catalog?.operations ?? []).filter((item) => {
    const needle = search.toLowerCase();
    return (tag === "all" || item.tags.includes(tag)) && (!needle || `${item.method} ${item.path} ${item.summary} ${item.operation_id}`.toLowerCase().includes(needle));
  }), [catalog, search, tag]);
  const expected = selected?.mutating ? `EJECUTAR ${selected.method} ${selected.path}` : "";

  async function execute() {
    if (!selected || !selectedId) return;
    setBusy(true); setError("");
    try {
      const parsedHeaders = parseObject(headers, "Los headers deben ser un objeto JSON.") as Record<string, string>;
      const parsedBody = body.trim() ? JSON.parse(body) : null;
      const pathParams: Record<string, string> = {};
      const queryParams: Record<string, unknown> = {};
      selected.parameters.forEach((parameter) => {
        const value = values[`${parameter.location}:${parameter.name}`];
        if (parameter.required && !value) throw new Error(`Completa el parámetro requerido: ${parameter.name}.`);
        if (!value && !parameter.required) return;
        if (parameter.location === "path") pathParams[parameter.name] = value;
        if (parameter.location === "query") queryParams[parameter.name] = typedValue(value, parameter.schema.type);
        if (parameter.location === "header") parsedHeaders[parameter.name] = value;
      });
      const next = await api.executeTryMe({
        orchestrator_id: selectedId, method: selected.method, path: selected.path,
        path_params: pathParams, query_params: queryParams, headers: parsedHeaders,
        body: parsedBody, confirmation
      });
      setResult(next); setResponseTab(0); setSnapshotName(`${selected.method} ${selected.summary}`.slice(0, 150));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo ejecutar la API."); }
    finally { setBusy(false); }
  }

  async function saveSnapshot() {
    if (!result || !("sample_id" in result) || !snapshotName.trim()) return;
    setBusy(true); setError("");
    try {
      await api.saveTryMeSnapshot(result.sample_id, snapshotName.trim());
      setSnapshots(await api.tryMeSnapshots(selectedId));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar el snapshot."); }
    finally { setBusy(false); }
  }

  async function importSwagger(file?: File) {
    if (!file || !selectedId) return;
    const orchestrator = orchestrators.find((item) => item.id === selectedId);
    const detected = orchestrator?.swagger_version || orchestrator?.api_version || "9.6";
    const parts = detected.split(".");
    const version = parts[0] === "9" && parts[1] === "7" ? "9.6" : parts.slice(0, 2).join(".");
    setBusy(true); setError("");
    try { await api.uploadSwagger(version, file); await load(selectedId); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo importar el Swagger."); }
    finally { setBusy(false); if (upload.current) upload.current.value = ""; }
  }

  async function synchronize() {
    if (!selectedId) return;
    setBusy(true); setError("");
    try { await api.syncTryMeCatalog(selectedId); await load(selectedId); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se encontró el Swagger en el Orchestrator."); }
    finally { setBusy(false); }
  }

  return <Stack spacing={2.5}>
    <Paper sx={{ p: 2.25 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <Box sx={{ flex: 1 }}><Typography variant="h2">Try Me · Swagger Explorer</Typography><Typography color="text.secondary">Prueba todas las operaciones del contrato de cada Orchestrator y conserva evidencia exportable.</Typography></Box>
        <Select size="small" value={selectedId} onChange={(event) => onSelect(event.target.value)} sx={{ minWidth: 240 }}>
          {orchestrators.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.api_version ?? "sin validar"}</MenuItem>)}
        </Select>
        <input ref={upload} hidden type="file" accept=".json,.yaml,.yml,application/json" onChange={(event) => void importSwagger(event.target.files?.[0])} />
        <Button variant="outlined" startIcon={<Download size={17} />} onClick={() => void synchronize()} disabled={!selectedId || busy}>Traer del Orchestrator</Button>
        <Button variant="outlined" startIcon={<Upload size={17} />} onClick={() => upload.current?.click()} disabled={!selectedId || busy}>Importar Swagger</Button>
      </Stack>
      {catalog ? <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} alignItems="center"><Chip size="small" label={`${catalog.operations.length} APIs`} color="primary" /><Chip size="small" label={`v${catalog.version}`} /><Typography variant="caption" color="text.secondary">{catalog.source}</Typography></Stack> : null}
    </Paper>
    {error ? <Alert severity="error" action={<IconButton size="small" onClick={() => setError("")}><X size={15} /></IconButton>}>{error}</Alert> : null}
    {!orchestrators.length ? <Alert severity="info">Conecta y valida un Orchestrator antes de utilizar Try Me.</Alert> : null}
    <Grid container spacing={2}>
      <Grid item xs={12} lg={4}>
        <Paper sx={{ overflow: "hidden", height: { lg: 720 }, display: "flex", flexDirection: "column" }}>
          <Stack spacing={1} sx={{ p: 1.5 }}>
            <TextField size="small" placeholder="Buscar método, path u operación" value={search} onChange={(event) => setSearch(event.target.value)} InputProps={{ startAdornment: <InputAdornment position="start"><Search size={16} /></InputAdornment> }} />
            <Select size="small" value={tag} onChange={(event) => setTag(event.target.value)}><MenuItem value="all">Todos los grupos</MenuItem>{tags.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select>
          </Stack><Divider />
          <List dense sx={{ overflow: "auto", flex: 1, py: 0 }}>
            {filtered.map((item) => <ListItemButton key={`${item.method}:${item.path}`} selected={selected?.method === item.method && selected.path === item.path} onClick={() => setSelected(item)} sx={{ gap: 1, alignItems: "flex-start" }}>
              <Chip size="small" color={methodColor[item.method]} label={item.method} sx={{ mt: .6, width: 66, fontWeight: 800 }} />
              <ListItemText primary={item.summary} secondary={item.path} primaryTypographyProps={{ fontWeight: 700, fontSize: 13 }} secondaryTypographyProps={{ sx: { fontFamily: "monospace", overflowWrap: "anywhere" } }} />
            </ListItemButton>)}
          </List>
        </Paper>
      </Grid>
      <Grid item xs={12} lg={8}>
        {selected ? <Stack spacing={2}>
          <Paper sx={{ p: 2 }}><Stack direction="row" spacing={1} alignItems="center"><Chip color={methodColor[selected.method]} label={selected.method} sx={{ fontWeight: 900 }} /><Typography fontFamily="monospace" fontWeight={700} sx={{ overflowWrap: "anywhere" }}>{selected.path}</Typography></Stack><Typography variant="h2" sx={{ mt: 1.5 }}>{selected.summary}</Typography>{selected.description ? <Typography color="text.secondary" sx={{ mt: .75 }}>{selected.description}</Typography> : null}</Paper>
          <Paper sx={{ p: 2 }}><Typography variant="h2" sx={{ mb: 1.5 }}>Parámetros</Typography><Grid container spacing={1.5}>{selected.parameters.map((parameter) => <Grid item xs={12} md={6} key={`${parameter.location}:${parameter.name}`}><TextField fullWidth size="small" required={parameter.required} label={`${parameter.name} · ${parameter.location}`} value={values[`${parameter.location}:${parameter.name}`] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [`${parameter.location}:${parameter.name}`]: event.target.value }))} helperText={parameter.description || String(parameter.schema.type ?? "string")} /></Grid>)}</Grid>{!selected.parameters.length ? <Typography color="text.secondary">Esta operación no declara parámetros.</Typography> : null}</Paper>
          {selected.method !== "GET" || Object.keys(selected.request_schema).length ? <Paper sx={{ p: 2 }}><Typography variant="h2" sx={{ mb: 1.5 }}>Request body · JSON</Typography><TextField fullWidth multiline minRows={8} maxRows={22} value={body} onChange={(event) => setBody(event.target.value)} placeholder="{}" inputProps={{ style: { fontFamily: "monospace", fontSize: 13 } }} /></Paper> : null}
          <Paper sx={{ p: 2 }}><Typography variant="h2" sx={{ mb: 1.5 }}>Headers adicionales</Typography><TextField fullWidth multiline minRows={2} value={headers} onChange={(event) => setHeaders(event.target.value)} inputProps={{ style: { fontFamily: "monospace" } }} helperText="JSON. Authorization, cookies y X-Auth-Token siempre provienen de la credencial cifrada del Orchestrator." /></Paper>
          {selected.mutating ? <Alert severity="warning"><Typography fontWeight={800}>Esta operación puede cambiar el comportamiento del Orchestrator.</Typography><Typography variant="body2">Revisa los datos y escribe la confirmación exacta.</Typography><Stack spacing={1.25} sx={{ mt: 1.5 }}><Typography variant="caption">Escribe: <code>{expected}</code></Typography><TextField size="small" label="Confirmación" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></Stack></Alert> : null}
          <Button size="large" variant="contained" startIcon={<Play size={18} />} disabled={busy || (selected.mutating && confirmation !== expected)} onClick={() => void execute()}>Ejecutar {selected.method}</Button>
          {result ? <ResponsePanel result={result} tab={responseTab} onTab={setResponseTab} snapshotName={snapshotName} setSnapshotName={setSnapshotName} onSnapshot={saveSnapshot} busy={busy} /> : null}
        </Stack> : <Paper sx={{ p: 4 }}><Typography color="text.secondary">Selecciona una operación Swagger.</Typography></Paper>}
      </Grid>
      <Grid item xs={12}><SnapshotPanel items={snapshots} onOpen={(item) => { setResult({ request: item.request_data, response: item.response_data, response_headers: {} }); setResponseTab(0); window.scrollTo({ top: 0, behavior: "smooth" }); }} onDelete={async (id) => { await api.deleteTryMeSnapshot(id); setSnapshots(await api.tryMeSnapshots(selectedId)); }} /></Grid>
    </Grid>
  </Stack>;
}

function ResponsePanel({ result, tab, onTab, snapshotName, setSnapshotName, onSnapshot, busy }: { result: VisibleOutput; tab: number; onTab: (value: number) => void; snapshotName: string; setSnapshotName: (value: string) => void; onSnapshot: () => void; busy: boolean }) {
  const payload = tab === 0 ? result.response : tab === 1 ? result.request : result.response_headers;
  const status = "status_code" in result ? result.status_code : null;
  return <Paper sx={{ overflow: "hidden" }}><Stack direction={{ xs: "column", sm: "row" }} alignItems={{ sm: "center" }} spacing={1} sx={{ p: 1.5 }}><Typography variant="h2" sx={{ flex: 1 }}>Salida {status ? `· HTTP ${status}` : ""}</Typography><Button size="small" startIcon={<Download size={15} />} onClick={() => download("try-me-result.json", JSON.stringify(result, null, 2), "application/json")}>JSON</Button><Button size="small" startIcon={<Download size={15} />} onClick={() => download("try-me-result.csv", toCsv(result.response), "text/csv")}>CSV</Button></Stack><Divider /><Tabs value={tab} onChange={(_, value) => onTab(value)}><Tab label="Response" /><Tab label="Request" /><Tab label="Headers" /></Tabs>{result.error ? <Alert severity="error">{result.error}</Alert> : null}<Box component="pre" sx={{ m: 0, p: 2, maxHeight: 480, overflow: "auto", bgcolor: "rgba(0,0,0,.25)", fontSize: 12 }}>{JSON.stringify(payload, null, 2)}</Box>{"sample_id" in result ? <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ p: 1.5 }}><TextField size="small" fullWidth label="Nombre del snapshot" value={snapshotName} onChange={(event) => setSnapshotName(event.target.value)} /><Button variant="outlined" startIcon={<Camera size={16} />} disabled={busy || !snapshotName.trim()} onClick={onSnapshot}>Guardar snapshot</Button></Stack> : null}</Paper>;
}

function SnapshotPanel({ items, onOpen, onDelete }: { items: TryMeSnapshot[]; onOpen: (item: TryMeSnapshot) => void; onDelete: (id: string) => Promise<void> }) {
  return <Paper sx={{ p: 2 }}><Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}><Camera size={19} /><Typography variant="h2">Snapshots</Typography><Chip size="small" label={items.length} /></Stack>{items.length ? <Grid container spacing={1}>{items.map((item) => <Grid item xs={12} md={6} lg={4} key={item.id}><Paper variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" spacing={1}><Chip size="small" color={methodColor[item.method]} label={item.method} /><Box sx={{ flex: 1, minWidth: 0 }}><Typography fontWeight={800} noWrap>{item.name}</Typography><Typography variant="caption" color="text.secondary" noWrap>{item.path}</Typography></Box><Tooltip title="Abrir"><IconButton size="small" onClick={() => onOpen(item)}><FileJson size={16} /></IconButton></Tooltip><Tooltip title="Eliminar"><IconButton size="small" color="error" onClick={() => void onDelete(item.id)}><Trash2 size={16} /></IconButton></Tooltip></Stack><Typography variant="caption">HTTP {item.status_code ?? "—"} · {new Date(item.created_at).toLocaleString()}</Typography></Paper></Grid>)}</Grid> : <Typography color="text.secondary">Guarda una salida para compararla o exportarla después.</Typography>}</Paper>;
}

function parseObject(value: string, message: string): Record<string, unknown> { const parsed = JSON.parse(value); if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(message); return parsed; }
function typedValue(value: string, type: unknown): unknown { if (type === "integer" || type === "number") return Number(value); if (type === "boolean") return value === "true"; if (type === "array") return value.split(",").map((item) => item.trim()); return value; }
function schemaExample(schema: Record<string, unknown>): unknown { const properties = schema.properties; if (properties && typeof properties === "object") return Object.fromEntries(Object.entries(properties).map(([key, value]) => [key, schemaExample(value as Record<string, unknown>)])); if (schema.type === "array") return [schemaExample((schema.items as Record<string, unknown>) ?? {})]; if (Array.isArray(schema.enum)) return schema.enum[0]; return schema.example ?? schema.default ?? ({ string: "", integer: 0, number: 0, boolean: false } as Record<string, unknown>)[String(schema.type)] ?? null; }
function download(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url); }
function toCsv(value: unknown): string { const rows: string[][] = [["path", "value"]]; const walk = (item: unknown, path: string) => { if (item && typeof item === "object") Object.entries(item).forEach(([key, child]) => walk(child, path ? `${path}.${key}` : key)); else rows.push([path, item == null ? "" : String(item)]); }; walk(value, ""); return rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(",")).join("\n"); }
