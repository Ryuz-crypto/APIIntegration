const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type SystemOverview = {
  orchestrators: number;
  appliances: number;
  selected_appliances: number;
  compatibility_profiles: number;
  services: Record<string, string>;
};

export type Orchestrator = {
  id: string;
  name: string;
  base_url: string;
  api_version: string | null;
  status: string;
  polling_enabled: boolean;
  polling_active_seconds: number;
  polling_idle_seconds: number;
  credential_label: string | null;
  auth_type: string;
  username: string | null;
  api_key_header: string | null;
  verify_tls: boolean;
  timeout_seconds: number;
  has_secret: boolean;
  last_validated_at: string | null;
  last_status_code: number | null;
  last_latency_ms: number | null;
  last_error: string | null;
};

export type Appliance = {
  id: string;
  orchestrator_id: string;
  hostname: string;
  serial_number: string | null;
  site: string | null;
  model: string | null;
  software_version: string | null;
  status: string;
  selected_for_monitoring: boolean;
  last_metrics: Record<string, unknown>;
  last_collected_at: string | null;
  last_status_code: number | null;
  last_latency_ms: number | null;
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
  error: string | null;
  created_at: string;
};

export type OrchestratorConnectionPlan = {
  auth_type: string;
  required_fields: {
    field: string;
    label: string;
    required: boolean;
    secret: boolean;
  }[];
  supported_versions: string[];
  validation_operation: string;
  discovery_operation: string;
  metrics_operation: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<SystemOverview>("/system/overview"),
  orchestrators: () => request<Orchestrator[]>("/orchestrators"),
  appliances: () => request<Appliance[]>("/appliances"),
  profiles: () => request<CompatibilityProfile[]>("/compatibility/profiles"),
  samples: () => request<ApiSample[]>("/samples"),
  connectionPlan: (authType: string) =>
    request<OrchestratorConnectionPlan>(`/orchestrators/connection-plan?auth_type=${encodeURIComponent(authType)}`),
  createOrchestrator: (payload: {
    name: string;
    base_url: string;
    api_version?: string;
    credential_label?: string;
    auth_type: string;
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
  validateOrchestrator: (id: string) =>
    request(`/orchestrators/${id}/validate`, {
      method: "POST"
    }),
  discoverAppliances: (id: string) =>
    request<Appliance[]>(`/orchestrators/${id}/discover-appliances`, {
      method: "POST"
    }),
  collectAppliance: (id: string) =>
    request<Record<string, unknown>>(`/appliances/${id}/collect`, {
      method: "POST"
    })
};
