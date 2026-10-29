/** Cliente tipado del API del gemelo digital. Sin dependencias; errores explícitos (nunca se tragan). */
import { uncachedUrl } from "../../src/httpCache";

export class Api {
  private currentToken: string;
  private currentAuthVersion = 0;

  constructor(public base = "", token = "") { this.currentToken = token; }

  get token() { return this.currentToken; }
  set token(value: string) {
    if (value !== this.currentToken) {
      this.currentToken = value;
      this.currentAuthVersion += 1;
    }
  }
  get authVersion() { return this.currentAuthVersion; }

  private url(p: string) { return `${this.base.replace(/\/$/, "")}/api/v1/digital-twin${p}`; }
  async req(path: string, init: RequestInit = {}): Promise<Response> {
    const token = this.token, authVersion = this.authVersion;
    const method = (init.method || "GET").toUpperCase();
    const url = method === "GET" ? uncachedUrl(this.url(path)) : this.url(path);
    const r = await fetch(url, { ...init, cache: "no-store", headers: { ...(init.headers || {}), Authorization: `Bearer ${token}` } });
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      if (authVersion !== this.authVersion) throw new ApiError(409, path, "Superseded request", authVersion);
      throw new ApiError(r.status, path, body, authVersion);
    }
    if (authVersion !== this.authVersion) throw new ApiError(409, path, "Superseded request", authVersion);
    return r;
  }
  json<T = any>(path: string): Promise<T> { return this.req(path).then((r) => r.json()); }
  async postJson<T = any>(path: string, body: unknown): Promise<T> {
    return (await this.req(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
  }
  /** Login real (/auth/login). Devuelve el token; la sesión lo guarda tras validar el primer endpoint protegido. */
  async login(tenantId: string, email: string, password: string): Promise<string> {
    const r = await fetch(`${this.base.replace(/\/$/, "")}/api/v1/auth/login`, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password, tenant_id: tenantId }) });
    if (!r.ok) throw new ApiError(r.status, "/auth/login", await r.text().catch(() => ""));
    const token = (await r.json()).access_token;
    if (typeof token !== "string" || !token) throw new Error("El servicio de autenticación no devolvió un token.");
    return token;
  }
  /** Flujo operativo real del equipo: anomalía -> diagnóstico -> cadena de falla -> orden de mantenimiento -> SST de la zona. */
  timeline(nodeId: string) { return this.json<{ node_id: string; steps: any[] }>(`/nodes/${nodeId}/timeline`); }
  /** Replay verificable de eventos en tiempo real (ruta fuera del prefijo del gemelo). */
  async replay(topic: string, afterSequence: number, limit = 100): Promise<any[]> {
    const token = this.token, authVersion = this.authVersion;
    const r = await fetch(uncachedUrl(`${this.base.replace(/\/$/, "")}/api/v1/realtime/events?topic=${encodeURIComponent(topic)}&after_sequence=${afterSequence}&limit=${limit}`), { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      if (authVersion !== this.authVersion) throw new ApiError(409, "/realtime/events", "Superseded request", authVersion);
      throw new ApiError(r.status, "/realtime/events", body, authVersion);
    }
    if (authVersion !== this.authVersion) throw new ApiError(409, "/realtime/events", "Superseded request", authVersion);
    return (await r.json()).events;
  }
  /** Salud por GlobalId IFC (un solo pedido para teñir todo el modelo). */
  healthMap() { return this.json<{ global_id: string; node_id: string; name: string; node_type: string; health_score: number | null; health_severity: string | null; open_anomalies: number; worst_severity: string | null }[]>("/bim/health-map"); }
  graph() { return this.json<{ nodes: any[]; edges: any[] }>("/graph"); }
  /** Enlaza el GUID IFC de un elemento de la geometría con un nodo operativo del gemelo (equipo con telemetría/anomalías). */
  linkElement(globalId: string, nodeId: string) {
    return this.postJson("/bindings", { node_id: nodeId, identifier_system: "IFC", identifier_type: "GUID", identifier: globalId });
  }
  overview() { return this.json("/overview"); }
  anomalies(limit = 50) { return this.json(`/anomalies?status=open&limit=${limit}`); }
  modelVersions() { return this.json<any[]>("/model-versions"); }
  async modelFile(id: string) { return new Uint8Array(await (await this.req(`/model-versions/${id}/file`)).arrayBuffer()); }
  lookup(globalId: string) { return this.json(`/bim/lookup?global_id=${encodeURIComponent(globalId)}`); }
  nodeDetail(id: string) { return this.json(`/nodes/${id}/detail`); }
  series(pointId: string, minutes = 120) { return this.json<any[]>(`/points/${pointId}/series?minutes=${minutes}`); }
  importIfc(content: string, filename: string) {
    const key = filename.replace(/\.ifc$/i, "").slice(0, 60) || "modelo";
    return this.postJson("/bim/ifc/import", { content, model_key: key, version: new Date().toISOString().slice(0, 19), materialize_nodes: true, filename });
  }
}
export class ApiError extends Error {
  constructor(public status: number, public path: string, public body: string, public authVersion: number | null = null) {
    super(`${status} ${path} ${body.slice(0, 160)}`);
  }
}
export const sevColor = (s?: string | null): number => ({ critical: 0xe5484d, high: 0xe5484d, medium: 0xf0b429, warning: 0xf0b429, low: 0xf0b429 } as Record<string, number>)[(s || "").toLowerCase()] ?? 0x2fbf71;
