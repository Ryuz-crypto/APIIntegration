const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
let accessToken = sessionStorage.getItem("dashboardapi-session") ?? "";

export function setAccessToken(token: string) {
  accessToken = token;
  if (token) sessionStorage.setItem("dashboardapi-session", token);
  else sessionStorage.removeItem("dashboardapi-session");
}

export type UserRole = "viewer" | "operator" | "admin";
export type AuthUser = {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  enabled: boolean;
  created_at: string;
  last_login_at: string | null;
};
export type AuthSession = { token: string; expires_at: string; user: AuthUser };
export type AuditEvent = {
  id: string; actor: string; action: string; resource_type: string;
  resource_id: string | null; details: Record<string, unknown>; created_at: string;
};

export type SystemOverview = {
  orchestrators: number;
  appliances: number;
  selected_appliances: number;
  compatibility_profiles: number;
  services: Record<string, string>;
};

export type AppearanceSettings = {
  primary: string;
  secondary: string;
  header: string;
  background: string;
  surface: string;
  text: string;
  icon: "network" | "activity" | "gauge" | "workflow";
  font: "inter" | "system" | "humanist" | "technical" | "mono";
  panel_name: string;
  welcome_message: string;
};

export type ReleaseStatus = {
  ok: boolean;
  current: string;
  current_release: string;
  latest: string;
  latest_stable: string;
  update_available: boolean;
  releases: string[];
  error?: string;
};

export type UpdateStatus = {
  state: "idle" | "pending" | "running" | "success" | "error";
  current?: string;
  version?: string;
  message?: string;
  backup?: string;
  completed_at?: string;
};

export type TryMeParameter = {
  name: string;
  location: "path" | "query" | "header" | "body";
  required: boolean;
  description: string;
  schema: Record<string, unknown>;
  example: unknown;
};

export type TryMeOperation = {
  operation_id: string;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  summary: string;
  description: string;
  tags: string[];
  parameters: TryMeParameter[];
  request_schema: Record<string, unknown>;
  request_example: unknown;
  mutating: boolean;
};

export type TryMeCatalog = {
  orchestrator_id: string;
  version: string;
  source: string;
  title: string;
  operations: TryMeOperation[];
};

export type TryMeResult = {
  sample_id: string;
  ok: boolean;
  operation_id: string;
  method: string;
  path: string;
  status_code: number | null;
  duration_ms: number | null;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  response_headers: Record<string, string>;
  error?: string | null;
  executed_at: string;
};

export type TryMeSnapshot = {
  id: string;
  orchestrator_id: string;
  sample_id: string;
  name: string;
  operation_id: string;
  method: string;
  path: string;
  status_code: number | null;
  request_data: Record<string, unknown>;
  response_data: Record<string, unknown>;
  created_at: string;
};

export type Orchestrator = {
  id: string;
  name: string;
  base_url: string;
  deployment_type: string;
  tenant: string | null;
  api_version: string | null;
  swagger_version: string | null;
  status: string;
  polling_enabled: boolean;
  polling_active_seconds: number;
  polling_idle_seconds: number;
  credential_label: string | null;
  auth_type: string;
  login_type: number;
  username: string | null;
  api_key_header: string | null;
  verify_tls: boolean;
  timeout_seconds: number;
  has_secret: boolean;
  capabilities: {
    source?: string;
    operations?: Record<string, boolean>;
    verified?: string[];
  };
  last_validated_at: string | null;
  credentials_updated_at: string | null;
};

export type CredentialStatus = {
  orchestrator_id: string;
  credential_label: string | null;
  auth_type: string;
  username: string | null;
  api_key_header: string | null;
  configured: boolean;
  encrypted_at_rest: boolean;
  supports_unattended_polling: boolean;
  updated_at: string | null;
};

export type ValidationResult = {
  orchestrator_id: string;
  status: string;
  detected_version: string | null;
  compatibility_profile: string | null;
  message: string;
  status_code: number | null;
  duration_ms: number | null;
  capabilities: Record<string, boolean>;
};

export type Appliance = {
  id: string;
  orchestrator_id: string;
  hostname: string;
  serial_number: string | null;
  ne_pk: string | null;
  site: string | null;
  model: string | null;
  software_version: string | null;
  status: string;
  selected_for_monitoring: boolean;
};

export type CompatibilityProfile = {
  version: string;
  status: string;
  source: string;
  operations: string[];
};

export type ApiSample = {
  id: string;
  orchestrator_id: string;
  appliance_id: string | null;
  api_version: string | null;
  operation_id: string;
  method: string;
  path: string;
  status_code: number | null;
  duration_ms: number | null;
  ok: boolean;
  payload: Record<string, unknown>;
  request_params: Record<string, unknown>;
  extracted_values: Record<string, unknown>;
  transformations: string[];
  error: string | null;
  created_at: string;
};

export type ApiTrace = ApiSample & {
  sanitized_payload: Record<string, unknown>;
  code_examples: { curl: string; python: string; javascript: string };
};

export type DashboardWidget = {
  id: string;
  title: string;
  description: string;
  visualization: "stat" | "bars" | "table" | "timeseries" | "status";
  status: "ready" | "waiting" | "unavailable";
  reason: string | null;
  value: number | string | null;
  unit: string | null;
  data: Array<Record<string, unknown>>;
  required_operations: string[];
  provenance: {
    sample_id: string | null;
    operation_id: string;
    method: string | null;
    path: string | null;
    collected_at: string | null;
  } | null;
};

export type Dashboard = {
  orchestrator_id: string;
  orchestrator_name: string;
  api_version: string | null;
  generated_at: string;
  sections: Array<{ id: string; title: string; widgets: DashboardWidget[] }>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    const text = await response.text();
    let detail: unknown;
    try { detail = JSON.parse(text).detail; } catch { /* Non-JSON proxy error. */ }
    throw new Error(typeof detail === "string" ? detail : `HTTP ${response.status}: no se pudo completar la solicitud.`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  authStatus: () => request<{ users_configured: boolean; version: string }>("/auth/status"),
  bootstrap: (payload: { username: string; password: string; display_name: string; admin_token: string }) => request<AuthSession>("/auth/bootstrap", { method: "POST", body: JSON.stringify(payload) }),
  login: (username: string, password: string) => request<AuthSession>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<AuthUser>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  users: () => request<AuthUser[]>("/auth/users"),
  createUser: (payload: { username: string; password: string; display_name: string; role: UserRole }) => request<AuthUser>("/auth/users", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (id: string, payload: { display_name?: string; role?: UserRole; enabled?: boolean }) => request<AuthUser>(`/auth/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteUser: (id: string) => request<void>(`/auth/users/${id}`, { method: "DELETE" }),
  changePassword: (current_password: string, new_password: string) => request<void>("/auth/password", { method: "POST", body: JSON.stringify({ current_password, new_password }) }),
  audit: () => request<AuditEvent[]>("/auth/audit"),
  startOtp: (id: string) => request<{ status: string; challenge_id: string; expires_in: number; message: string }>(`/orchestrators/${id}/auth/start`, { method: "POST" }),
  completeOtp: (id: string, challenge_id: string, otp: string) => request<ValidationResult>(`/orchestrators/${id}/auth/complete`, { method: "POST", body: JSON.stringify({ challenge_id, otp }) }),
  cancelOtp: (id: string, challenge_id: string) => request<{ status: string }>(`/orchestrators/${id}/auth/cancel`, { method: "POST", body: JSON.stringify({ challenge_id }) }),
  overview: () => request<SystemOverview>("/system/overview"),
  appearance: () => request<AppearanceSettings>("/system/appearance"),
  updateAppearance: (payload: AppearanceSettings) => request<AppearanceSettings>("/system/appearance", { method: "PUT", body: JSON.stringify(payload) }),
  releases: (token: string) => request<ReleaseStatus>("/system/releases", { headers: { "X-TLS-Admin-Token": token } }),
  updateStatus: (token: string) => request<UpdateStatus>("/system/update", { headers: { "X-TLS-Admin-Token": token } }),
  updateSystem: (token: string, version: string, confirmation: string) => request<UpdateStatus>("/system/update", {
    method: "POST",
    headers: { "X-TLS-Admin-Token": token },
    body: JSON.stringify({ version, confirmation })
  }),
  tryMeCatalog: (orchestratorId: string) => request<TryMeCatalog>(`/try-me/catalog/${orchestratorId}`),
  syncTryMeCatalog: (orchestratorId: string) => request<TryMeCatalog>(`/try-me/catalog/${orchestratorId}/sync`, { method: "POST" }),
  executeTryMe: (payload: {
    orchestrator_id: string;
    method: string;
    path: string;
    path_params: Record<string, string>;
    query_params: Record<string, unknown>;
    headers: Record<string, string>;
    body: unknown;
    confirmation: string;
  }, adminToken: string) => request<TryMeResult>("/try-me/execute", {
    method: "POST",
    headers: adminToken ? { "X-TLS-Admin-Token": adminToken } : {},
    body: JSON.stringify(payload)
  }),
  tryMeSnapshots: (orchestratorId: string) => request<TryMeSnapshot[]>(`/try-me/snapshots/${orchestratorId}`),
  saveTryMeSnapshot: (sampleId: string, name: string) => request<TryMeSnapshot>("/try-me/snapshots", {
    method: "POST", body: JSON.stringify({ sample_id: sampleId, name })
  }),
  deleteTryMeSnapshot: (snapshotId: string) => request<void>(`/try-me/snapshots/${snapshotId}`, { method: "DELETE" }),
  uploadSwagger: async (version: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}/compatibility/swagger?version=${encodeURIComponent(version)}&activate=false&catalog_only=true`, { method: "POST", body: form, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    }
    return response.json() as Promise<{ version: string; operation_count: number; checksum: string }>;
  },
  orchestrators: () => request<Orchestrator[]>("/orchestrators"),
  appliances: () => request<Appliance[]>("/appliances"),
  profiles: () => request<CompatibilityProfile[]>("/compatibility/profiles"),
  samples: () => request<ApiSample[]>("/samples"),
  trace: (sampleId: string) => request<ApiTrace>(`/samples/${sampleId}/trace`),
  dashboard: (orchestratorId: string) => request<Dashboard>(`/dashboard/${orchestratorId}`),
  createOrchestrator: (payload: {
    name: string;
    base_url: string;
    deployment_type: string;
    tenant?: string;
    credential_label?: string;
    auth_type: string;
    login_type: number;
    username?: string;
    password?: string;
    api_token?: string;
    api_key_header?: string;
    verify_tls: boolean;
    timeout_seconds: number;
  }) =>
    request<Orchestrator>("/orchestrators", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  validateOrchestrator: (id: string, otp?: string) =>
    request<ValidationResult>(`/orchestrators/${id}/validate`, {
      method: "POST",
      body: JSON.stringify(otp ? { otp } : {})
    }),
  credentialStatus: (id: string) => request<CredentialStatus>(`/orchestrators/${id}/credential-status`),
  updateCredentials: (id: string, payload: {
    credential_label?: string;
    auth_type: string;
    login_type: number;
    username?: string;
    password?: string;
    api_token?: string;
    api_key_header?: string;
  }) => request<Orchestrator>(`/orchestrators/${id}/credentials`, {
    method: "PUT",
    body: JSON.stringify(payload)
  }),
  discoverAppliances: (id: string) =>
    request<Appliance[]>(`/orchestrators/${id}/discover-appliances`, {
      method: "POST"
    }),
  collectAppliance: (id: string) =>
    request<Record<string, unknown>>(`/appliances/${id}/collect`, {
      method: "POST"
    }),
  setApplianceMonitoring: (id: string, enabled: boolean) =>
    request<Appliance>(`/appliances/${id}/monitoring`, {
      method: "PATCH",
      body: JSON.stringify({ enabled, active_seconds: 5, idle_seconds: 300 })
    })
};
