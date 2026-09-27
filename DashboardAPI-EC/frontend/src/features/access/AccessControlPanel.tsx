import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Grid, IconButton, MenuItem, Paper, Select, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography
} from "@mui/material";
import { KeyRound, Plus, RefreshCw, ShieldCheck, Trash2, UserCog } from "lucide-react";
import { api, AuditEvent, DashboardUser, Identity } from "../../lib/api";

type Props = { identity: Identity; onNotice: (message: string) => void; onLogout: () => void };

const ROLES: Array<{ value: string; label: string }> = [
  { value: "viewer", label: "Viewer" },
  { value: "operator", label: "Operator" },
  { value: "admin", label: "Admin" }
];

export function AccessControlPanel({ identity, onNotice, onLogout }: Props) {
  const [users, setUsers] = useState<DashboardUser[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [form, setForm] = useState({ username: "", password: "", full_name: "", role: "viewer" });
  const [passwords, setPasswords] = useState({ current: "", next: "" });
  const [error, setError] = useState("");
  const isAdmin = identity.role === "admin";

  async function refresh() {
    try {
      const [nextEvents, nextUsers] = await Promise.all([
        api.auditEvents().catch(() => []),
        isAdmin ? api.users() : Promise.resolve([])
      ]);
      setEvents(nextEvents);
      setUsers(nextUsers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo consultar el control de acceso.");
    }
  }

  useEffect(() => { void refresh(); }, [identity.role]);

  async function create() {
    try {
      await api.createUser(form);
      setForm({ username: "", password: "", full_name: "", role: "viewer" });
      onNotice("Usuario creado.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el usuario.");
    }
  }

  async function update(user: DashboardUser, patch: { role?: string; enabled?: boolean }) {
    try {
      await api.updateUser(user.id, patch);
      onNotice("Usuario actualizado.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar el usuario.");
    }
  }

  async function remove(user: DashboardUser) {
    if (!window.confirm(`Eliminar permanentemente al usuario ${user.username}? Sus sesiones se cerrarán.`)) return;
    try {
      await api.deleteUser(user.id);
      onNotice(`Usuario ${user.username} eliminado.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el usuario.");
    }
  }

  async function rotate() {
    try {
      await api.changePassword(passwords.current, passwords.next);
      setPasswords({ current: "", next: "" });
      onNotice("Contraseña actualizada. Inicia sesión nuevamente.");
      onLogout();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar la contraseña.");
    }
  }

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error" onClose={() => setError("")}>{error}</Alert> : null}
      <Grid container spacing={2}>
        {isAdmin && (
          <Grid item xs={12} lg={5}>
            <Paper sx={{ p: 2, height: "100%" }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <UserCog size={20} />
                <Typography variant="h2">Nuevo usuario</Typography>
              </Stack>
              <Stack spacing={2}>
                <TextField label="Usuario" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
                <TextField label="Nombre completo (opcional)" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
                <TextField label="Contraseña inicial" type="password" autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} helperText="Mínimo 12 caracteres" />
                <TextField select label="Rol" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
                  {ROLES.map((role) => <MenuItem key={role.value} value={role.value}>{role.label}</MenuItem>)}
                </TextField>
                <Button variant="contained" startIcon={<Plus size={17} />} disabled={!form.username || form.password.length < 12} onClick={() => void create()}>
                  Crear usuario
                </Button>
              </Stack>
            </Paper>
          </Grid>
        )}
        {isAdmin && (
          <Grid item xs={12} lg={7}>
            <Paper sx={{ p: 2, height: "100%" }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <ShieldCheck size={20} />
                <Typography variant="h2">Usuarios</Typography>
              </Stack>
              <Stack spacing={1.25}>
                {users.map((user) => (
                  <Stack key={user.id} direction="row" spacing={1.25} alignItems="center" useFlexGap flexWrap="wrap">
                    <Box sx={{ minWidth: 160, flex: 1 }}>
                      <Typography fontWeight={700}>{user.username}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {user.enabled ? "Habilitado" : "Deshabilitado"}
                        {user.last_login_at ? ` · Último acceso ${new Date(user.last_login_at).toLocaleString("es-MX")}` : ""}
                      </Typography>
                    </Box>
                    <Select size="small" value={user.role} onChange={(event) => void update(user, { role: event.target.value })} sx={{ minWidth: 120 }}>
                      {ROLES.map((role) => <MenuItem key={role.value} value={role.value}>{role.value}</MenuItem>)}
                    </Select>
                    <Button size="small" variant="outlined" onClick={() => void update(user, { enabled: !user.enabled })}>
                      {user.enabled ? "Deshabilitar" : "Habilitar"}
                    </Button>
                    <IconButton size="small" disabled={identity.id === user.id} title={identity.id === user.id ? "No puedes eliminar tu usuario actual" : `Eliminar ${user.username}`} onClick={() => void remove(user)}>
                      <Trash2 size={16} />
                    </IconButton>
                  </Stack>
                ))}
              </Stack>
            </Paper>
          </Grid>
        )}
        <Grid item xs={12} lg={isAdmin ? 12 : 6}>
          <Paper sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
              <KeyRound size={20} />
              <Typography variant="h2">Cambiar contraseña</Typography>
            </Stack>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth label="Contraseña actual" type="password" autoComplete="current-password" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth label="Nueva contraseña" type="password" autoComplete="new-password" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} helperText="Mínimo 12 caracteres" />
              </Grid>
              <Grid item xs={12}>
                <Button variant="contained" startIcon={<RefreshCw size={17} />} disabled={passwords.current.length < 12 || passwords.next.length < 12} onClick={() => void rotate()}>
                  Rotar credencial
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <ShieldCheck size={20} />
          <Typography variant="h2">Auditoría de acciones</Typography>
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Fecha</TableCell>
              <TableCell>Actor</TableCell>
              <TableCell>Rol</TableCell>
              <TableCell>Acción</TableCell>
              <TableCell>Destino</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.length ? events.map((event) => (
              <TableRow key={event.id}>
                <TableCell>{new Date(event.created_at).toLocaleString("es-MX")}</TableCell>
                <TableCell>{event.actor}</TableCell>
                <TableCell>{event.role}</TableCell>
                <TableCell>{event.action}</TableCell>
                <TableCell>{event.resource_id ?? "—"}</TableCell>
              </TableRow>
            )) : (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary">Sin eventos de auditoría.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
