import { useEffect, useState } from "react";
import { ShieldAlert, Check, X, Timer } from "lucide-react";
import type { PendingApproval } from "../../types/agent";

interface HumanApprovalModalProps {
  pending: PendingApproval[];
  operatorName: string;
  onDecide: (approvalId: string, decision: "APPROVED" | "REJECTED") => void;
}

function remainingSeconds(expiresAt: string): number {
  return Math.max(0, Math.round((new Date(expiresAt).getTime() - Date.now()) / 1000));
}

/**
 * Se muestra únicamente cuando hay aprobaciones pendientes (interfaz
 * "intermitente" descrita en el requisito): si la cola está vacía, no
 * ocupa espacio en el dashboard. Cada tarjeta trae su propio temporizador
 * de caducidad — coincide con `APPROVAL_TIMEOUT_S` del backend — y al
 * vencer, la acción original ya no puede confirmarse: el backend aplica el
 * fallback seguro automáticamente.
 */
export default function HumanApprovalModal({ pending, operatorName, onDecide }: HumanApprovalModalProps) {
  const [, forceTick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  if (pending.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 bg-ops-bg/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl border border-ops-red/40 bg-ops-bg shadow-2xl p-5 space-y-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center gap-2 text-ops-red">
          <ShieldAlert className="w-5 h-5" />
          <h3 className="text-sm font-semibold">Validación humana requerida ({pending.length})</h3>
        </div>
        {pending.map((p) => {
          const secs = remainingSeconds(p.expires_at);
          return (
            <div key={p.approval_id} className="rounded-xl border border-ops-panel2 bg-ops-panel p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-ops-ink">{p.agent_name} propone <span className="text-ops-red">{p.action_type}</span></span>
                <span className="text-[11px] text-ops-amber flex items-center gap-1"><Timer className="w-3 h-3" /> {secs}s</span>
              </div>
              <p className="text-xs text-ops-inkdim">{p.rationale}</p>
              <p className="text-[11px] text-ops-inkfaint">Severidad {p.severity} · zona {p.zone || "n/d"} · equipo {p.target_device_id || "n/d"} · fallback si vence: {p.fallback_action}</p>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => onDecide(p.approval_id, "APPROVED")}
                  disabled={secs === 0}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-ops-green hover:bg-ops-green text-white text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-40"
                >
                  <Check className="w-3.5 h-3.5" /> confirmar ({operatorName})
                </button>
                <button
                  onClick={() => onDecide(p.approval_id, "REJECTED")}
                  disabled={secs === 0}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-ops-panel2 hover:bg-ops-linesoft text-ops-ink text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-40"
                >
                  <X className="w-3.5 h-3.5" /> rechazar
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
