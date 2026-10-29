import { userFailureMessage } from './core/errors/userFailure';
import { uncachedUrl } from './httpCache';
import { configuredApiBase } from './apiBase';

export type TwinOverview = {
  nodes_total: number;
  points: { total: number; good: number; stale: number; never: number };
  devices: { total: number; online: number };
  open_anomalies: number;
  open_anomalies_by_severity: Record<string, number>;
  health: { avg: number | null; min: number | null; assessed_nodes: number };
  bim: { models: number; entities: number; ids_pass: number; ids_fail: number; bindings: number; ifc_nodes: number };
  pending_work_requests: number;
};

export type TwinAnomaly = {
  anomaly_id: string;
  node_id: string;
  node_name: string | null;
  node_code: string | null;
  metric: string;
  severity: string;
  status: string;
  score: number | null;
  observed_value: number | string | null;
  baseline_value: number | string | null;
  detected_at: string;
};

export type MaintenanceOrderStatus =
  | 'pending_approval'
  | 'critical'
  | 'scheduled'
  | 'in_progress'
  | 'pending_quote'
  | 'blocked'
  | 'completed'
  | 'cancelled';

export type MaintenanceOrder = {
  id: string;
  code: string;
  title: string;
  description: string;
  category: string;
  severity: string;
  status: MaintenanceOrderStatus;
  property_id: string | null;
  unit_id: string | null;
  asset_node_id: string | null;
  resident_id: string | null;
  vendor_id: string | null;
  vendor_name: string | null;
  cost_cop: number | null;
  sla_due_at: string | null;
  reporter_kind: string;
  reporter_name: string;
  created_at: string;
  updated_at: string;
  version: number;
};

export type MaintenanceOrderPage = {
  items: MaintenanceOrder[];
  total: number;
  page: number;
  page_size: number;
};

export type MaintenancePage<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type MaintenanceUnit = {
  id: string;
  property_id: string;
  code: string;
  name: string;
  unit_type: string;
  property_name: string;
  occupancy_status: string;
};

export type MaintenanceResident = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  active: boolean;
  primary_unit_id: string | null;
  unit_code: string | null;
  unit_name: string | null;
  property_name: string | null;
  unit_ids: string[];
};

export type MaintenanceVendor = {
  id: string;
  name: string;
  nit: string;
  categories: string[];
  status: 'active' | 'suspended' | 'inactive';
  documents_current: boolean;
  documents_valid_until: string | null;
  rating: number | null;
  version: number;
};

export type TenantUser = {
  id: string;
  email: string;
  is_active: boolean;
  roles: string[];
};

export type ResidentWrite = {
  full_name: string;
  phone: string | null;
  active?: boolean;
  unit_ids: string[];
  primary_unit_id: string;
};

export type VendorWrite = {
  name: string;
  nit: string;
  categories: string[];
  status: MaintenanceVendor['status'];
  documents_valid_until: string | null;
  rating: number | null;
};

export type TwinNode = {
  id: string;
  parent_id: string | null;
  parent_name: string | null;
  node_type: string;
  code: string;
  name: string;
  status: string;
  latitude: number | null;
  longitude: number | null;
  elevation_m: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type TwinPoint = {
  id: string;
  node_id: string;
  code: string;
  name: string;
  semantic_kind: string;
  canonical_unit: string | null;
  engineering_min: number | null;
  engineering_max: number | null;
  stale_after_seconds: number;
  value: number | string | null;
  unit: string | null;
  quality: string | null;
  quality_reason: string | null;
  observed_at: string | null;
  freshness: 'NO_DATA' | 'STALE' | 'FRESH' | string;
};

export type TwinModelVersion = {
  id: string;
  model_key: string;
  version: string;
  source_format: string;
  lifecycle_status: string;
  content_sha256: string | null;
  created_at: string;
  has_file: boolean;
  filename: string | null;
  size_bytes: number | null;
  entity_count: number;
};

export type TwinNodePage = { items: TwinNode[]; total: number; limit: number; offset: number };

export type SensorSimulationProfile = {
  profile_id: string;
  name: string;
  semantic_kind: string;
  unit: string;
  engineering_min: number;
  engineering_max: number;
  supports_alarm: boolean;
};

export type SimulatedDevice = {
  device_id: string;
  node_id: string;
  node_name: string;
  point_id: string;
  code: string;
  name: string;
  semantic_kind: string;
  unit: string;
  profile_id: string;
  latest_value: number | null;
  latest_unit: string | null;
  latest_quality: string | null;
  latest_observed_at: string | null;
  data_origin: 'simulated';
  hardware_connected: false;
};

export type SensorSimulationRun = {
  run_id: string;
  status: 'accepted' | 'duplicate';
  scenario: 'normal' | 'alarm';
  data_origin: 'simulated';
  hardware_connected: false;
  samples: Array<{
    source_message_id: string;
    status: string;
    value?: number;
    unit?: string;
    quality?: string;
    quality_reason?: string;
  }>;
  diagnostic: {
    diagnostic_run_id: string;
    severity: string;
    health_score: number;
    anomalies_created_or_updated: number;
  } | null;
};

export class DashboardApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'DashboardApiError';
  }
}

export class DashboardApi {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  private async request<T>(path: string): Promise<T> {
    const response = await fetch(uncachedUrl(`${this.baseUrl.replace(/\/$/, '')}${path}`), {
      cache: 'no-store',
      headers: { Authorization: `Bearer ${this.token}` },
    });

    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = undefined;
      }
      throw new DashboardApiError(response.status, userFailureMessage(response.status, payload).message);
    }

    return response.json() as Promise<T>;
  }

  private async write<T>(path: string, body: unknown): Promise<T> {
    return this.mutate<T>('POST', path, body);
  }

  private async mutate<T>(method: 'POST' | 'PUT' | 'PATCH', path: string, body: unknown): Promise<T> {
    const response = await fetch(uncachedUrl(`${this.baseUrl.replace(/\/$/, '')}${path}`), {
      method,
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = undefined;
      }
      throw new DashboardApiError(response.status, userFailureMessage(response.status, payload).message);
    }

    return response.json() as Promise<T>;
  }

  overview(): Promise<TwinOverview> {
    return this.request('/api/v1/digital-twin/overview');
  }

  anomalies(limit = 6): Promise<TwinAnomaly[]> {
    return this.request(`/api/v1/digital-twin/anomalies?status=open&limit=${limit}`);
  }

  nodes(options: { limit?: number; offset?: number; search?: string } = {}): Promise<TwinNodePage> {
    const params = new URLSearchParams();
    if (options.limit != null) params.set('limit', String(options.limit));
    if (options.offset != null) params.set('offset', String(options.offset));
    if (options.search?.trim()) params.set('search', options.search.trim());
    const query = params.size ? `?${params}` : '';
    return this.request(`/api/v1/digital-twin/nodes${query}`);
  }

  points(limit = 200): Promise<TwinPoint[]> {
    return this.request(`/api/v1/digital-twin/points?limit=${limit}`);
  }

  simulatorProfiles(): Promise<SensorSimulationProfile[]> {
    return this.request('/api/v1/digital-twin/simulations/catalog');
  }

  simulatedDevices(): Promise<SimulatedDevice[]> {
    return this.request('/api/v1/digital-twin/simulations/devices');
  }

  createSimulatedDevice(input: { node_id: string; profile_id: string; code: string; name?: string }): Promise<{
    device_id: string;
    point_id: string;
    node_id: string;
    code: string;
    name: string;
    profile_id: string;
    data_origin: 'simulated';
    hardware_connected: false;
  }> {
    return this.write('/api/v1/digital-twin/simulations/devices', input);
  }

  runSimulation(deviceId: string, scenario: 'normal' | 'alarm', runId: string): Promise<SensorSimulationRun> {
    return this.write(`/api/v1/digital-twin/simulations/devices/${encodeURIComponent(deviceId)}/run`, {
      scenario,
      run_id: runId,
    });
  }

  modelVersions(): Promise<TwinModelVersion[]> {
    return this.request('/api/v1/digital-twin/model-versions');
  }

  maintenanceOrders(options: { mine?: boolean; status?: string; page?: number; pageSize?: number } = {}): Promise<MaintenanceOrderPage> {
    const params = new URLSearchParams({
      page: String(options.page ?? 1),
      page_size: String(options.pageSize ?? 50),
    });
    if (options.status) params.set('status', options.status);
    const path = options.mine ? '/api/v1/maintenance/orders/mine' : '/api/v1/maintenance/orders';
    return this.request(`${path}?${params}`);
  }

  maintenanceUnits(options: { page?: number; pageSize?: number; q?: string } = {}): Promise<MaintenancePage<MaintenanceUnit>> {
    const params = new URLSearchParams({
      page: String(options.page ?? 1),
      page_size: String(options.pageSize ?? 100),
    });
    if (options.q?.trim()) params.set('q', options.q.trim());
    return this.request(`/api/v1/maintenance/units?${params}`);
  }

  maintenanceResidents(options: { page?: number; pageSize?: number; q?: string } = {}): Promise<MaintenancePage<MaintenanceResident>> {
    const params = new URLSearchParams({
      page: String(options.page ?? 1),
      page_size: String(options.pageSize ?? 100),
    });
    if (options.q?.trim()) params.set('q', options.q.trim());
    return this.request(`/api/v1/maintenance/residents?${params}`);
  }

  maintenanceVendors(options: { page?: number; pageSize?: number; q?: string } = {}): Promise<MaintenancePage<MaintenanceVendor>> {
    const params = new URLSearchParams({
      page: String(options.page ?? 1),
      page_size: String(options.pageSize ?? 100),
    });
    if (options.q?.trim()) params.set('q', options.q.trim());
    return this.request(`/api/v1/maintenance/vendors?${params}`);
  }

  tenantUsers(): Promise<TenantUser[]> {
    return this.request('/api/v1/users');
  }

  createMaintenanceResident(input: ResidentWrite & { user_id: string }): Promise<{ id: string; status: string }> {
    return this.write('/api/v1/maintenance/residents', input);
  }

  updateMaintenanceResident(residentId: string, input: ResidentWrite): Promise<{ id: string; status: string }> {
    return this.mutate('PUT', `/api/v1/maintenance/residents/${encodeURIComponent(residentId)}`, input);
  }

  createMaintenanceVendor(input: VendorWrite): Promise<{ id: string; status: string }> {
    return this.write('/api/v1/maintenance/vendors', input);
  }

  updateMaintenanceVendor(vendorId: string, input: VendorWrite): Promise<{ id: string; status: string }> {
    return this.mutate('PUT', `/api/v1/maintenance/vendors/${encodeURIComponent(vendorId)}`, input);
  }

  createMaintenanceOrder(input: {
    title: string;
    description: string;
    category: string;
    severity: string;
  }): Promise<{ id: string; code: string; status: MaintenanceOrderStatus }> {
    return this.write('/api/v1/maintenance/orders', input);
  }

  approveMaintenanceOrder(orderId: string, expectedVersion: number): Promise<{
    id: string;
    status: MaintenanceOrderStatus;
    version: number;
  }> {
    return this.write(`/api/v1/maintenance/orders/${encodeURIComponent(orderId)}/approve`, {
      expected_version: expectedVersion,
    });
  }

  transitionMaintenanceOrder(
    orderId: string,
    status: MaintenanceOrderStatus,
    expectedVersion: number,
  ): Promise<{ id: string; status: MaintenanceOrderStatus; version: number }> {
    return this.mutate(
      'PATCH',
      `/api/v1/maintenance/orders/${encodeURIComponent(orderId)}/status`,
      { status, expected_version: expectedVersion },
    );
  }

  async login(tenantId: string, email: string, password: string): Promise<string> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, '')}/api/v1/auth/login`, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: tenantId, email, password }),
    });

    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = undefined;
      }
      throw new DashboardApiError(response.status, userFailureMessage(response.status, payload).message);
    }

    const result = (await response.json()) as { access_token: string };
    if (!result.access_token) throw new Error('El servicio de autenticación no devolvió un token.');
    return result.access_token;
  }
}

export function dashboardApiBase(): string {
  return configuredApiBase();
}
