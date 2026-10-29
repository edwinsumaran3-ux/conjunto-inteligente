/** Grafo de conocimiento: modelo (BIM / Ubicación / IoT / SST) + motor de fuerzas (repulsión, resortes, gravedad, enfriamiento). Puro: se prueba en Node. */
export type Cat = "bim" | "location" | "iot" | "sst" | "alert";
export const CAT_COLOR: Record<Cat, string> = { bim: "#3b82f6", location: "#10b981", iot: "#f59e0b", sst: "#ef4444", alert: "#ef4444" };
export const CAT_LABEL: Record<Cat, string> = { bim: "BIM", location: "Ubicación", iot: "IoT", sst: "SST", alert: "Alerta" };

export interface GNode { id: string; label: string; cat: Cat; x: number; y: number; vx: number; vy: number; r: number; fixed?: boolean; pulse?: boolean; ref?: string; twinId?: string; }
export interface GEdge { source: string; target: string; relation?: string; alert?: boolean; }
export interface TwinGraph { nodes: { id: string; node_type: string; code: string; name: string; parent_id?: string | null }[]; edges: { from_node: string; to_node: string; relation: string }[]; }
export interface TimelineStep { at: string; kind: string; ref: string; severity: string | null; state: string; title: string; detail: string; }
export interface PointInfo { id: string; name: string; value: number | null; canonical_unit?: string | null; quality?: string | null; }

export const catOf = (nodeType: string): Cat => {
  const t = nodeType.toLowerCase();
  if (["site", "building", "floor", "storey", "space", "zone", "room"].includes(t)) return "location";
  if (["device", "sensor", "point", "gateway", "meter"].includes(t)) return "iot";
  return "bim";                                                       // equipment, system, asset, ifc*
};

export interface ModelOpts { showIfc?: boolean; focusId?: string | null; points?: PointInfo[]; steps?: TimelineStep[]; }
export function buildGraphModel(g: TwinGraph, o: ModelOpts = {}): { nodes: GNode[]; edges: GEdge[] } {
  const keep = g.nodes.filter((n) => o.showIfc || !n.node_type.toLowerCase().startsWith("ifc"));
  const ids = new Set(keep.map((n) => n.id));
  const nodes: GNode[] = keep.map((n, i) => ({ id: n.id, twinId: n.id, label: n.name || n.code, cat: catOf(n.node_type), x: 0, y: 0, vx: 0, vy: 0, r: n.id === o.focusId ? 22 : catOf(n.node_type) === "location" ? 16 : 18, ref: n.code }));
  const edges: GEdge[] = g.edges.filter((e) => ids.has(e.from_node) && ids.has(e.to_node)).map((e) => ({ source: e.from_node, target: e.to_node, relation: e.relation }));
  const focus = o.focusId && ids.has(o.focusId) ? o.focusId : null;
  if (focus) {
    for (const p of o.points ?? []) {
      const id = `pt:${p.id}`; nodes.push({ id, label: `${p.name}${p.value != null ? ` ${Math.round(p.value * 10) / 10}${p.canonical_unit ? " " + p.canonical_unit : ""}` : ""}`, cat: "iot", x: 0, y: 0, vx: 0, vy: 0, r: 14, ref: p.id });
      edges.push({ source: focus, target: id, relation: "MEASURES" });
    }
    const parentOf = (id: string) => g.nodes.find((n) => n.id === id)?.parent_id ?? null; const zone = parentOf(focus) ?? focus;
    for (const s of o.steps ?? []) {
      if (s.kind === "anomaly" && s.state === "active") { const id = `an:${s.ref}`; nodes.push({ id, label: s.title.replace("Anomalía detectada: ", "⚠ "), cat: "alert", pulse: true, x: 0, y: 0, vx: 0, vy: 0, r: 15, ref: s.ref }); edges.push({ source: focus, target: id, relation: "ANOMALY", alert: true }); }
      if (s.kind === "sst") { const id = `sst:${s.ref}`; nodes.push({ id, label: s.title.replace("SST · ", "SST: "), cat: "sst", pulse: s.state === "blocked", x: 0, y: 0, vx: 0, vy: 0, r: 15, ref: s.ref }); edges.push({ source: ids.has(zone) ? zone : focus, target: id, relation: "ACTIVITY", alert: s.state === "blocked" }); }
    }
  }
  return { nodes, edges };
}

/** Motor de fuerzas determinista (semilla circular), con enfriamiento tipo d3-force. */
export class ForceGraph {
  alpha = 1; private byId = new Map<string, GNode>();
  private opt: { repulsion: number; spring: number; rest: number; gravity: number; damping: number };
  constructor(public nodes: GNode[], public edges: GEdge[], public w: number, public h: number, opt?: Partial<{ repulsion: number; spring: number; rest: number; gravity: number; damping: number }>) {
    const rest = Math.max(70, Math.min(150, Math.min(w, h) * 0.4));   // la longitud natural escala con el lienzo: el grafo aprovecha el espacio disponible
    this.opt = { repulsion: 2600 * (rest / 90) ** 2, spring: 0.045, rest, gravity: 0.008, damping: 0.82, ...opt };
    nodes.forEach((n, i) => { this.byId.set(n.id, n); const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2, r = Math.min(w, h) * 0.3; if (!n.x && !n.y) { n.x = w / 2 + Math.cos(a) * r; n.y = h / 2 + Math.sin(a) * r; } });
  }
  resize(w: number, h: number) { this.w = w; this.h = h; this.alpha = Math.max(this.alpha, 0.3); }
  reheat(a = 0.6) { this.alpha = Math.max(this.alpha, a); }
  tick(): void {
    const { repulsion, spring, rest, gravity, damping } = this.opt, N = this.nodes;
    for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
      let dx = N[j].x - N[i].x, dy = N[j].y - N[i].y, d2 = dx * dx + dy * dy; if (d2 < 1) { dx = (i - j) * 0.5 + 0.1; dy = 0.1; d2 = dx * dx + dy * dy; }
      const f = (repulsion * this.alpha) / d2, d = Math.sqrt(d2), fx = (dx / d) * f, fy = (dy / d) * f;
      N[i].vx -= fx; N[i].vy -= fy; N[j].vx += fx; N[j].vy += fy;
    }
    for (const e of this.edges) {
      const a = this.byId.get(e.source), b = this.byId.get(e.target); if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - rest) * spring * this.alpha, fx = (dx / d) * f, fy = (dy / d) * f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }
    for (const n of N) {
      n.vx += (this.w / 2 - n.x) * gravity * this.alpha; n.vy += (this.h / 2 - n.y) * gravity * this.alpha;
      if (n.fixed) { n.vx = n.vy = 0; continue; }
      n.vx *= damping; n.vy *= damping; n.x += n.vx; n.y += n.vy;
      const m = n.r + 6; n.x = Math.min(this.w - m, Math.max(m, n.x)); n.y = Math.min(this.h - m, Math.max(m, n.y));
    }
    this.alpha *= 0.985; if (this.alpha < 0.002) this.alpha = 0.002;
  }
  run(ticks: number) { for (let i = 0; i < ticks; i++) this.tick(); }
  energy(): number { return this.nodes.reduce((s, n) => s + n.vx * n.vx + n.vy * n.vy, 0); }
  hit(x: number, y: number): GNode | null {
    for (let i = this.nodes.length - 1; i >= 0; i--) { const n = this.nodes[i]; if ((x - n.x) ** 2 + (y - n.y) ** 2 <= (n.r + 4) ** 2) return n; }
    return null;
  }
}
