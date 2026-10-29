import { Bot, Activity, Clock } from "lucide-react";
import type { AgentAction, AgentStatus } from "../../types/agent";

interface AgentStatusPanelProps {
  status: AgentStatus | null;
  recentActions: AgentAction[];
  online: boolean;
}

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: "text-ops-red", HIGH: "text-ops-amber", MEDIUM: "text-ops-accent", LOW: "text-ops-inkdim",
};

export default function AgentStatusPanel({ status, recentActions, online }: AgentStatusPanelProps) {
  return (
    <div className="rounded-xl border border-ops-panel2 bg-ops-bg/60 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ops-ink flex items-center gap-2"><Bot className="w-4 h-4 text-ops-accent" /> Orquestador de agentes</h3>
        <span className={`text-[11px] px-2 py-0.5 rounded-full ${online ? "bg-ops-green/15 text-ops-green" : "bg-ops-linesoft/40 text-ops-inkdim"}`}>
          {online ? "loop activo" : "sin conexión"}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {(status?.agents ?? []).map((a) => (
          <span key={a} className="text-[11px] px-2 py-1 rounded-lg bg-ops-panel border border-ops-panel2 text-ops-ink flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-ops-accent" /> {a}
          </span>
        ))}
        {(status?.agents ?? []).length === 0 && <span className="text-xs text-ops-inkfaint">sin agentes reportados</span>}
      </div>

      {status?.last_incident && (
        <p className="text-xs text-ops-inkdim flex items-center gap-1.5">
          <Clock className="w-3 h-3" /> último incidente evaluado: <span className="text-ops-ink">{status.last_incident.kind}</span>
        </p>
      )}

      <div>
        <p className="text-xs text-ops-inkdim mb-1.5">Acciones recientes</p>
        <div className="space-y-1 max-h-56 overflow-y-auto">
          {recentActions.length === 0 && <p className="text-xs text-ops-inkfaint">Sin actividad todavía.</p>}
          {recentActions.map((a) => (
            <div key={a.action_id} className="flex items-center justify-between text-xs px-2 py-1.5 rounded-lg bg-ops-panel border border-ops-panel2">
              <span className="text-ops-ink">{a.agent_name} → {a.action_type}</span>
              <span className={SEVERITY_COLOR[a.severity] ?? "text-ops-inkdim"}>{a.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
