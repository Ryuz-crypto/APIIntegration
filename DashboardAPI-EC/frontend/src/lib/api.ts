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
  createOrchestrator: (payload: { name: string; base_url: string; credential_label?: string }) =>
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
    })
};
