/** Flujo operativo (línea de tiempo real) y actividad en vivo (replay de eventos): modelos de vista puros. */
import type { TimelineStep } from "./graph";
export type WfState = "completed" | "active" | "pending" | "blocked";
export interface WfView { state: WfState; kind: string; title: string; detail: string; when: string; severity: string | null; icon: string; }
const ICON: Record<string, string> = { anomaly: "alert", diagnosis: "search", failure_chain: "link", work_request: "wrench", sst: "shield" };

export const relTime = (iso: string, now = Date.now()): string => {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 45) return "hace instantes"; if (s < 3600) return `hace ${Math.round(s / 60)} min`; if (s < 86400) return `hace ${Math.round(s / 3600)} h`; return `hace ${Math.round(s / 86400)} d`;
};
export const toView = (steps: TimelineStep[], now = Date.now()): WfView[] =>
  steps.map((s) => ({ state: (["completed", "active", "pending", "blocked"].includes(s.state) ? s.state : "active") as WfState, kind: s.kind, title: s.title, detail: s.detail, when: relTime(s.at, now), severity: s.severity, icon: ICON[s.kind] ?? "dot" }));
/** Resumen ejecutivo: qué impide avanzar y qué espera a una persona. */
export function summarize(v: WfView[]): { blocked: number; awaitingHuman: number; open: number; headline: string } {
  const blocked = v.filter((x) => x.state === "blocked").length, awaitingHuman = v.filter((x) => x.state === "pending").length, open = v.filter((x) => x.state === "active").length;
  const headline = blocked ? `${blocked} bloqueo(s) SST impiden la intervención` : awaitingHuman ? `${awaitingHuman} acción(es) esperan aprobación humana` : open ? `${open} evento(s) activo(s)` : v.length ? "Sin pendientes" : "Sin actividad registrada";
  return { blocked, awaitingHuman, open, headline };
}

export interface LiveEvent { event_id: string; sequence: number; topic: string; correlation_id: string | null; payload: Record<string, unknown>; payload_sha256: string; }
export const LIVE_TOPICS = ["twin.anomaly.detected", "sst.approval.decided", "agent.operation.started", "edge.command.issued"] as const;
const SEV_ES: Record<string, string> = { critical: "crítica", high: "alta", medium: "media", low: "baja", info: "informativa" };
const TXT: Record<string, (p: any) => { text: string; tone: "bad" | "warn" | "ok" | "info" }> = {
  "twin.anomaly.detected": (p) => ({ text: `Anomalía ${SEV_ES[String(p.severity)] ?? p.severity ?? ""} detectada en el gemelo`, tone: p.severity === "critical" || p.severity === "high" ? "bad" : "warn" }),
  "sst.approval.decided": (p) => ({ text: `Aprobación SST ${p.status === "approved" ? "aprobada" : String(p.status ?? "decidida")}`, tone: p.status === "approved" ? "ok" : "warn" }),
  "agent.operation.started": () => ({ text: "Operación autónoma iniciada tras aprobación humana", tone: "info" }),
  "edge.command.issued": (p) => ({ text: `Comando físico emitido: ${p.command_type ?? "—"}`, tone: "warn" }),
};
export const humanize = (e: LiveEvent) => (TXT[e.topic] ?? (() => ({ text: e.topic, tone: "info" as const })))(e.payload);

export type ReplayFn = (topic: string, afterSequence: number, limit: number) => Promise<LiveEvent[]>;
type LiveEventHandler = (events: LiveEvent[]) => void | Promise<void>;
/** Sondeo del replay de eventos con cursor por tópico. La primera pasada fija el cursor en la cabeza y devuelve la historia reciente sin notificarla como "nueva". */
export class LivePoller {
  private cursor = new Map<string, number>(); private timer: ReturnType<typeof setInterval> | null = null; private primed = false;
  constructor(private replay: ReplayFn, private onNew: LiveEventHandler, private topics: readonly string[] = LIVE_TOPICS) {}
  async prime(history = 8): Promise<LiveEvent[]> {
    const all: LiveEvent[] = [];
    for (const t of this.topics) { const ev = await this.replay(t, 0, 500); this.cursor.set(t, ev.reduce((m, e) => Math.max(m, e.sequence), 0)); all.push(...ev); }
    this.primed = true; return all.sort((a, b) => a.sequence - b.sequence).slice(-history);
  }
  async pollOnce(): Promise<LiveEvent[]> {
    if (!this.primed) await this.prime(); const fresh: LiveEvent[] = [];
    for (const t of this.topics) { const ev = await this.replay(t, this.cursor.get(t) ?? 0, 100); if (ev.length) { this.cursor.set(t, Math.max(...ev.map((e) => e.sequence))); fresh.push(...ev); } }
    fresh.sort((a, b) => a.sequence - b.sequence); if (fresh.length) await this.onNew(fresh); return fresh;
  }
  start(ms = 5000, onError: (error: unknown) => void = (error) => console.error("Falló la actualización de actividad en vivo.", error)) {
    this.stop();
    this.timer = setInterval(() => {
      void this.pollOnce().catch((error: unknown) => {
        this.stop();
        onError(error);
      });
    }, ms);
  }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }
}
