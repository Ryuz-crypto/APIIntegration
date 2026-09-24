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
  discoverAppliances: (id: string) =>
    request<Appliance[]>(`/orchestrators/${id}/discover-appliances`, {
      method: "POST"
    }),
  collectAppliance: (id: string) =>
    request<Record<string, unknown>>(`/appliances/${id}/collect`, {
      method: "POST"
    })
};
