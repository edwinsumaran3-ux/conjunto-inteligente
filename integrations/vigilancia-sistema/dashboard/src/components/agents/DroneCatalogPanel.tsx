import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { Plane, Link2, Clock, Radar } from "lucide-react";
import { api } from "../../api/client";
import type { DroneModel } from "../../types/drone";

/**
 * Catálogo de referencia de modelos de dron profesionales para seguridad y
 * vigilancia (DJI, Elistair, Teal, Easy Aerial, Quantum-Systems, Alpha
 * Unmanned Systems, Autel, AV Systems). Registrar un modelo aquí solo
 * añade contexto de fabricante/autonomía al `EquipmentRegistry`; el
 * adaptador sigue siendo fail-closed hasta integrar el SDK real de ese
 * fabricante (ver `equipment_adapters/drone_adapter_boundary.py`).
 */
export default function DroneCatalogPanel() {
  const [catalog, setCatalog] = useState<DroneModel[]>([]);
  const [equipmentId, setEquipmentId] = useState("drone-02");
  const [selected, setSelected] = useState<string>("");
  const [status, setStatus] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setCatalog(await api.droneCatalog() as DroneModel[]); } catch { /* agent-orchestrator no disponible */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const handleRegister = async () => {
    if (!selected || !equipmentId) return;
    const r = await api.registerDrone(equipmentId, selected);
    setStatus(`${r.vendor} ${r.model} registrado como ${equipmentId} (fail-closed hasta conectar SDK del fabricante)`);
  };

  return (
    <div className="rounded-xl border border-ops-panel2 bg-ops-bg/60 p-4 space-y-3">
      <h3 className="text-sm font-semibold text-ops-ink flex items-center gap-2"><Plane className="w-4 h-4 text-ops-accent" /> Catálogo de drones de referencia</h3>

      <div className="grid sm:grid-cols-2 gap-2">
        {catalog.map((d) => (
          <button
            key={d.key}
            onClick={() => setSelected(d.key)}
            className={`text-left px-3 py-2 rounded-lg border text-xs space-y-1 ${selected === d.key ? "border-ops-accent bg-ops-panel" : "border-ops-panel2 bg-ops-panel/50"}`}
          >
            <p className="text-ops-ink font-medium">{d.vendor} {d.model}</p>
            <p className="text-ops-inkdim">{d.category}{d.tethered ? " · atado" : ""}</p>
            <div className="flex items-center gap-3 text-ops-inkfaint">
              {d.max_flight_time_min && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{d.max_flight_time_min} min</span>}
              {d.detection_range_km && <span className="flex items-center gap-1"><Radar className="w-3 h-3" />{d.detection_range_km} km</span>}
            </div>
          </button>
        ))}
        {catalog.length === 0 && <p className="text-xs text-ops-inkfaint col-span-2 text-center py-3">Catálogo no disponible (agent-orchestrator sin conexión).</p>}
      </div>

      <div className="flex flex-wrap items-end gap-2 pt-1">
        <label className="text-xs text-ops-inkdim flex flex-col gap-1">
          Identificador del equipo
          <input value={equipmentId} onChange={(e: ChangeEvent<HTMLInputElement>) => setEquipmentId(e.target.value)} className="bg-ops-panel border border-ops-panel2 rounded-lg px-2 py-1.5 text-xs w-32" />
        </label>
        <button onClick={handleRegister} disabled={!selected} className="px-3 py-1.5 rounded-lg bg-ops-accent text-ops-bg text-xs font-medium flex items-center gap-1.5 disabled:opacity-50">
          <Link2 className="w-3.5 h-3.5" /> registrar en la flota
        </button>
      </div>
      {status && <p className="text-[11px] text-ops-green">{status}</p>}
    </div>
  );
}
