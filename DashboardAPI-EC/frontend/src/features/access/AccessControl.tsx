import { Alert, Box, Button, Chip, Divider, FormControlLabel, Grid, IconButton, MenuItem, Paper, Stack, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { KeyRound, Plus, RefreshCw, Trash2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api, AuditEvent, AuthUser, UserRole } from "../../lib/api";

const roleLabel: Record<UserRole, string> = { viewer: "Consulta", operator: "Operador", admin: "Administrador" };

export function AccessControl({ identity }: { identity: AuthUser }) {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ username: "", display_name: "", password: "", role: "viewer" as UserRole });
  const [passwords, setPasswords] = useState({ current: "", next: "" });

  async function load() {
    if (identity.role !== "admin") return;
    try { const [nextUsers, nextAudit] = await Promise.all([api.users(), api.audit()]); setUsers(nextUsers); setAudit(nextAudit); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }
  useEffect(() => { void load(); }, [identity.role]);

  async function create() {
    try { await api.createUser(form); setForm({ username: "", display_name: "", password: "", role: "viewer" }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }
  async function patch(user: AuthUser, values: { role?: UserRole; enabled?: boolean }) {
    try { await api.updateUser(user.id, values); await load(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }
  async function remove(user: AuthUser) {
    if (!window.confirm(`¿Eliminar la cuenta ${user.username}?`)) return;
    try { await api.deleteUser(user.id); await load(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }
  async function changePassword() {
    try { await api.changePassword(passwords.current, passwords.next); setPasswords({ current: "", next: "" }); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }

  return <Stack spacing={2.5}>
    <Box><Typography variant="h1">Acceso de usuarios</Typography><Typography color="text.secondary">Cuentas locales, roles, sesiones y actividad administrativa.</Typography></Box>
    {error ? <Alert severity="error">{error}</Alert> : null}
    <Grid container spacing={2}>
      <Grid item xs={12} lg={identity.role === "admin" ? 4 : 6}>
        <Paper sx={{ p: 2.5, height: "100%" }}><Stack spacing={2}>
          <Stack direction="row" spacing={1} alignItems="center"><KeyRound size={20} /><Typography variant="h6" fontWeight={850}>Cambiar mi contraseña</Typography></Stack>
          <TextField label="Contraseña actual" type="password" value={passwords.current} onChange={(e) => setPasswords({ ...passwords, current: e.target.value })} />
          <TextField label="Nueva contraseña" type="password" value={passwords.next} onChange={(e) => setPasswords({ ...passwords, next: e.target.value })} helperText="Mínimo 12 caracteres. Las demás sesiones se cerrarán." />
          <Button variant="contained" onClick={changePassword} disabled={!passwords.current || passwords.next.length < 12}>Actualizar contraseña</Button>
        </Stack></Paper>
      </Grid>
      {identity.role === "admin" ? <Grid item xs={12} lg={8}>
        <Paper sx={{ p: 2.5 }}><Stack spacing={2}>
          <Stack direction="row" spacing={1} alignItems="center"><Plus size={20} /><Typography variant="h6" fontWeight={850}>Nueva cuenta</Typography></Stack>
          <Grid container spacing={1.5}>
            <Grid item xs={12} sm={6}><TextField fullWidth label="Usuario" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Grid>
            <Grid item xs={12} sm={6}><TextField fullWidth label="Nombre visible" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></Grid>
            <Grid item xs={12} sm={7}><TextField fullWidth label="Contraseña temporal" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Grid>
            <Grid item xs={12} sm={5}><TextField select fullWidth label="Rol" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>{Object.entries(roleLabel).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField></Grid>
          </Grid>
          <Button variant="contained" startIcon={<Plus size={17} />} onClick={create} disabled={!form.username || form.password.length < 12}>Crear usuario</Button>
        </Stack></Paper>
      </Grid> : null}
    </Grid>
    {identity.role === "admin" ? <Paper sx={{ overflow: "hidden" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5 }}><Stack direction="row" spacing={1} alignItems="center"><Users size={20} /><Typography variant="h6" fontWeight={850}>Usuarios</Typography></Stack><Button size="small" startIcon={<RefreshCw size={15} />} onClick={load}>Actualizar</Button></Stack>
      <Divider /><Box sx={{ overflowX: "auto" }}><Table><TableHead><TableRow><TableCell>Cuenta</TableCell><TableCell>Rol</TableCell><TableCell>Estado</TableCell><TableCell>Último acceso</TableCell><TableCell align="right">Acciones</TableCell></TableRow></TableHead><TableBody>
        {users.map((user) => <TableRow key={user.id}><TableCell><Typography fontWeight={800}>{user.display_name || user.username}</Typography><Typography variant="caption" color="text.secondary">{user.username}</Typography></TableCell><TableCell><TextField select size="small" value={user.role} onChange={(e) => void patch(user, { role: e.target.value as UserRole })} sx={{ minWidth: 150 }}>{Object.entries(roleLabel).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField></TableCell><TableCell><FormControlLabel control={<Switch checked={user.enabled} onChange={(e) => void patch(user, { enabled: e.target.checked })} />} label={user.enabled ? "Activo" : "Inactivo"} /></TableCell><TableCell>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Nunca"}</TableCell><TableCell align="right"><IconButton color="error" disabled={user.id === identity.id} onClick={() => void remove(user)}><Trash2 size={18} /></IconButton></TableCell></TableRow>)}
      </TableBody></Table></Box>
    </Paper> : null}
    {identity.role === "admin" ? <Paper sx={{ p: 2.5 }}><Typography variant="h6" fontWeight={850} sx={{ mb: 1.5 }}>Actividad reciente</Typography><Stack spacing={1}>{audit.slice(0, 30).map((event) => <Stack key={event.id} direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}><Chip size="small" label={event.action} /><Typography variant="body2" sx={{ flex: 1 }}>{event.actor} · {event.resource_type}</Typography><Typography variant="caption" color="text.secondary">{new Date(event.created_at).toLocaleString()}</Typography></Stack>)}</Stack></Paper> : null}
  </Stack>;
}
