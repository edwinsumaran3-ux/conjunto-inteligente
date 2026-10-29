// @vitest-environment node
import { describe, it, expect, vi } from "vitest";
import { buildGraphModel, catOf, ForceGraph, TwinGraph, TimelineStep } from "./graph";
import { toView, summarize, relTime, LivePoller, humanize, LiveEvent } from "./workflow";

const G: TwinGraph = { nodes: [
  { id: "s", node_type: "site", code: "S1", name: "Conjunto" }, { id: "b", node_type: "building", code: "T1", name: "Torre 1", parent_id: "s" },
  { id: "p", node_type: "equipment", code: "P1", name: "Bomba 1", parent_id: "b" }, { id: "k", node_type: "equipment", code: "TK1", name: "Tanque 1", parent_id: "b" },
  { id: "i1", node_type: "ifcwall", code: "W1", name: "Muro" }, { id: "i2", node_type: "ifcslab", code: "L1", name: "Losa" } ],
  edges: [{ from_node: "s", to_node: "b", relation: "CONTAINS" }, { from_node: "b", to_node: "p", relation: "CONTAINS" }, { from_node: "b", to_node: "k", relation: "CONTAINS" }, { from_node: "b", to_node: "i1", relation: "CONTAINS" }] };
const STEPS: TimelineStep[] = [
  { at: "2026-10-18T10:00:00Z", kind: "anomaly", ref: "a1", severity: "high", state: "active", title: "Anomalía detectada: temperature", detail: "Observado 90 frente a base 46" },
  { at: "2026-10-18T10:01:00Z", kind: "diagnosis", ref: "r1", severity: "high", state: "completed", title: "Diagnóstico ejecutado", detail: "x" },
  { at: "2026-10-18T10:02:00Z", kind: "work_request", ref: "w1", severity: "high", state: "pending", title: "Orden de mantenimiento", detail: "Requiere aprobación humana" },
  { at: "2026-10-18T10:03:00Z", kind: "sst", ref: "s1", severity: "alto", state: "blocked", title: "SST · mantenimiento", detail: "bloqueada" } ];

describe("modelo del grafo", () => {
  it("clasifica por categoría y oculta los nodos técnicos IFC por defecto", () => {
    expect(catOf("building")).toBe("location"); expect(catOf("equipment")).toBe("bim"); expect(catOf("sensor")).toBe("iot");
    const m = buildGraphModel(G); expect(m.nodes.map((n) => n.id).sort()).toEqual(["b", "k", "p", "s"]); expect(buildGraphModel(G, { showIfc: true }).nodes).toHaveLength(6);
    expect(m.edges.every((e) => m.nodes.some((n) => n.id === e.source) && m.nodes.some((n) => n.id === e.target))).toBe(true);
  });
  it("el equipo enfocado añade sus sensores IoT, la anomalía activa (pulso) y la actividad SST bloqueada", () => {
    const m = buildGraphModel(G, { focusId: "p", points: [{ id: "pt1", name: "Temperatura", value: 90, canonical_unit: "°C" }], steps: STEPS });
    expect(m.nodes.find((n) => n.cat === "iot")!.label).toBe("Temperatura 90 °C"); const al = m.nodes.find((n) => n.cat === "alert")!; expect(al.pulse).toBe(true);
    const sst = m.nodes.find((n) => n.cat === "sst")!; expect(sst.pulse).toBe(true); expect(m.edges.find((e) => e.target === sst.id)).toMatchObject({ source: "b", alert: true });
  });
});
describe("motor de fuerzas", () => {
  it("converge, sin NaN y dentro del lienzo; los conectados quedan más cerca que los no conectados", () => {
    const m = buildGraphModel(G, { focusId: "p", points: [{ id: "pt1", name: "T", value: 1 }], steps: STEPS }); const f = new ForceGraph(m.nodes, m.edges, 400, 300); f.run(400);
    for (const n of f.nodes) { expect(Number.isFinite(n.x) && Number.isFinite(n.y)).toBe(true); expect(n.x).toBeGreaterThanOrEqual(0); expect(n.x).toBeLessThanOrEqual(400); expect(n.y).toBeLessThanOrEqual(300); }
    expect(f.energy()).toBeLessThan(5);
    const d = (a: string, b: string) => { const A = f.nodes.find((n) => n.id === a)!, B = f.nodes.find((n) => n.id === b)!; return Math.hypot(A.x - B.x, A.y - B.y); };
    expect(d("b", "p")).toBeLessThan(d("s", "p"));
  });
  it("determinista, respeta nodos fijos y permite hit-test", () => {
    const run = () => { const m = buildGraphModel(G); const f = new ForceGraph(m.nodes, m.edges, 300, 300); f.nodes[0].fixed = true; f.nodes[0].x = 50; f.nodes[0].y = 60; f.run(200); return f; };
    const a = run(), b = run(); expect(a.nodes.map((n) => [n.x.toFixed(3), n.y.toFixed(3)])).toEqual(b.nodes.map((n) => [n.x.toFixed(3), n.y.toFixed(3)]));
    expect([a.nodes[0].x, a.nodes[0].y]).toEqual([50, 60]); const n = a.nodes[2]; expect(a.hit(n.x, n.y)!.id).toBe(n.id); expect(a.hit(-999, -999)).toBeNull();
  });
});
describe("flujo de trabajo y actividad en vivo", () => {
  it("resume qué bloquea y qué espera aprobación humana", () => {
    const v = toView(STEPS, Date.parse("2026-10-18T10:10:00Z")); expect(v[0]).toMatchObject({ icon: "alert", when: "hace 10 min", state: "active" });
    expect(summarize(v)).toMatchObject({ blocked: 1, awaitingHuman: 1, open: 1 }); expect(summarize(v).headline).toContain("bloqueo(s) SST");
    expect(summarize([]).headline).toBe("Sin actividad registrada"); expect(relTime("2026-10-18T10:00:00Z", Date.parse("2026-10-18T10:00:10Z"))).toBe("hace instantes");
  });
  it("el sondeo fija el cursor en la cabeza (la historia no se anuncia como nueva) y luego entrega solo lo nuevo", async () => {
    const store: LiveEvent[] = [{ event_id: "e1", sequence: 1, topic: "twin.anomaly.detected", correlation_id: null, payload: { severity: "high" }, payload_sha256: "x" }];
    const replay = async (t: string, after: number) => store.filter((e) => e.topic === t && e.sequence > after); const got: LiveEvent[][] = [];
    const lp = new LivePoller(replay, (e) => { got.push(e); }); const hist = await lp.prime(); expect(hist).toHaveLength(1); expect(await lp.pollOnce()).toHaveLength(0);
    store.push({ event_id: "e2", sequence: 2, topic: "sst.approval.decided", correlation_id: null, payload: { status: "approved" }, payload_sha256: "y" });
    const fresh = await lp.pollOnce(); expect(fresh.map((e) => e.event_id)).toEqual(["e2"]); expect(got).toHaveLength(1); expect(await lp.pollOnce()).toHaveLength(0);
    expect(humanize(fresh[0])).toEqual({ text: "Aprobación SST aprobada", tone: "ok" }); expect(humanize(store[0]).tone).toBe("bad");
  });
  it("detiene el polling y reporta el primer error de autenticación sin reintentar en bucle", async () => {
    vi.useFakeTimers();
    const failure = new Error("401");
    let rejectNext = false;
    const replay = vi.fn(async () => {
      if (rejectNext) {
        rejectNext = false;
        throw failure;
      }
      return [];
    });
    const onError = vi.fn();
    const poller = new LivePoller(replay, () => undefined, ["topic"]);
    await poller.prime();
    rejectNext = true;
    poller.start(1000, onError);

    await vi.advanceTimersByTimeAsync(1000);
    expect(onError).toHaveBeenCalledOnce();
    const callsAfterFailure = replay.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5000);
    expect(replay).toHaveBeenCalledTimes(callsAfterFailure);
    vi.useRealTimers();
  });
});
