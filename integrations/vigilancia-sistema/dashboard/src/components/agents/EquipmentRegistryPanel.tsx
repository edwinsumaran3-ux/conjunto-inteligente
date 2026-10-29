import { useCallback, useEffect, useState } from "react";
import { ShieldOff, Plane, Camera, Bot as RobotIcon, Zap } from "lucide-react";
import { api } from "../../api/client";

interface EquipmentRow {
  equipment_id: string;
  equipment_type: "DRONE" | "PTZ_CAMERA" | "GROUND_ROBOT" | "IR_ACTUATOR";
  is_connected: boolean;
  state: string;
  values: Record<string, unknown>;
}

const ICON: Record<EquipmentRow["equipment_type"], typeof Plane> = {
  DRONE: Plane, PTZ_CAMERA: Camera, GROUND_ROBOT: RobotIcon, IR_ACTUATOR: Zap,
};

/**
 * Refleja el `EquipmentRegistry` del orquestador: cada fila es un
 * adaptador boundary (dron/PTZ/robot/IR). Mientras no se conecte el
 * transporte real del fabricante, el estado se muestra como
 * "unavailable/digital-only/off" — es información honesta, no un error.
 */
export default function EquipmentRegistryPanel() {
  const [rows, setRows] = useState<EquipmentRow[]>([]);
  const [stopping, setStopping] = useState(false);

  const refresh = useCallback(async () => {
    try { setRows(await api.equipmentRegistry() as EquipmentRow[]); } catch { /* orquestador no disponible */ }
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]);

  const handleEmergencyStop = async () => {
    setStopping(true);
    try { await api.equipmentEmergencyStop(); } finally { setStopping(false); await refresh(); }
  };

  return (
    <div className="rounded-xl border border-ops-panel2 bg-ops-bg/60 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ops-ink">Registro de equipos (dron · PTZ · robot · IR)</h3>
        <button onClick={handleEmergencyStop} disabled={stopping} className="px-3 py-1.5 rounded-lg bg-ops-red hover:bg-ops-red text-white text-xs font-medium flex items-center gap-1.5 disabled:opacity-50">
          <ShieldOff className="w-3.5 h-3.5" /> {stopping ? "deteniendo..." : "parada de emergencia global"}
        </button>
      </div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const Icon = ICON[r.equipment_type] ?? Zap;
          return (
            <div key={r.equipment_id} className="flex items-center justify-between px-3 py-2 rounded-lg border border-ops-panel2 bg-ops-panel text-xs">
              <span className="flex items-center gap-2 text-ops-ink"><Icon className="w-4 h-4 text-ops-inkdim" /> {r.equipment_id}</span>
              <span className="text-ops-inkdim">{r.state}</span>
            </div>
          );
        })}
        {rows.length === 0 && <p className="text-xs text-ops-inkfaint py-2 text-center">Sin equipos registrados o agent-orchestrator no disponible.</p>}
      </div>
    </div>
  );
}
