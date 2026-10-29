import { useMemo } from "react";
import { useEquipmentTopology } from "../../hooks/useEquipmentTopology";
import TopologyNode from "./TopologyNode";
import TopologyLegend from "./TopologyLegend";

function kindOf(deviceClass: string): "CAMERA" | "SENSOR_LASER" | "SENSOR_IR" | "UNKNOWN" {
  if (deviceClass === "CAMERA") return "CAMERA";
  if (deviceClass === "SENSOR_LASER") return "SENSOR_LASER";
  if (deviceClass === "SENSOR_IR") return "SENSOR_IR";
  return "UNKNOWN";
}

/**
 * Diagrama en vivo de cómo está cableada la instalación: qué sensores
 * láser/IR están asociados a qué cámaras (malla de cascada) y el estado de
 * conectividad de cada equipo con el gateway. Se recalcula cada pocos
 * segundos vía `useEquipmentTopology`, sin intervención manual.
 */
export default function EquipmentTopologyBoard() {
  const { edgeDevices, discovered, mesh, online } = useEquipmentTopology();

  const sensors = discovered.filter((d) => d.device_class === "SENSOR_LASER" || d.device_class === "SENSOR_IR");
  const cameras = discovered.filter((d) => d.device_class === "CAMERA");

  const layout = useMemo(() => {
    const gatewayPos = { x: 60, y: 220 };
    const sensorPos = new Map(sensors.map((s, i) => [s.device_id, { x: 220, y: 60 + i * 70 }]));
    const cameraPos = new Map(cameras.map((c, i) => [c.device_id, { x: 460, y: 40 + i * 60 }]));
    return { gatewayPos, sensorPos, cameraPos };
  }, [sensors, cameras]);

  const height = Math.max(300, sensors.length * 70 + 60, cameras.length * 60 + 60);
  const width = 560;

  return (
    <div className="rounded-xl border border-ops-panel2 bg-ops-bg/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ops-ink">Pizarra de equipos — flujo en tiempo real</h3>
        <span className={`text-[11px] px-2 py-0.5 rounded-full ${online ? "bg-ops-green/15 text-ops-green" : "bg-ops-linesoft/40 text-ops-inkdim"}`}>
          {online ? "conectado" : "sin datos del edge"}
        </span>
      </div>
      <TopologyLegend />
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full mt-3" style={{ maxHeight: 480 }}>
        {edgeDevices.map((g) => (
          <TopologyNode key={g.device_id} x={layout.gatewayPos.x} y={layout.gatewayPos.y} label={g.device_id} sublabel="edge-gateway" kind="GATEWAY" online={g.healthy} />
        ))}
        {sensors.map((s) => {
          const pos = layout.sensorPos.get(s.device_id)!;
          return (
            <g key={s.device_id}>
              <line x1={layout.gatewayPos.x} y1={layout.gatewayPos.y} x2={pos.x} y2={pos.y} stroke="#1e293b" strokeWidth={1.5} />
              {(mesh[s.device_id] || []).map((camId) => {
                const camPos = layout.cameraPos.get(camId);
                if (!camPos) return null;
                return <line key={camId} x1={pos.x} y1={pos.y} x2={camPos.x} y2={camPos.y} stroke="#f87171" strokeDasharray="4 3" strokeWidth={1.5} opacity={0.7} />;
              })}
            </g>
          );
        })}
        {cameras.map((c) => {
          const pos = layout.cameraPos.get(c.device_id)!;
          return <line key={`gw-${c.device_id}`} x1={layout.gatewayPos.x} y1={layout.gatewayPos.y} x2={pos.x} y2={pos.y} stroke="#1e293b" strokeWidth={1} />;
        })}
        {sensors.map((s) => {
          const pos = layout.sensorPos.get(s.device_id)!;
          return <TopologyNode key={s.device_id} x={pos.x} y={pos.y} label={s.vendor || s.device_id} sublabel={s.zone} kind={kindOf(s.device_class)} online={s.auto_connected} />;
        })}
        {cameras.map((c) => {
          const pos = layout.cameraPos.get(c.device_id)!;
          return <TopologyNode key={c.device_id} x={pos.x} y={pos.y} label={c.vendor || c.device_id} sublabel={c.zone} kind="CAMERA" online={c.auto_connected} />;
        })}
      </svg>
      {sensors.length === 0 && cameras.length === 0 && (
        <p className="text-xs text-ops-inkfaint text-center py-6">Sin equipos detectados todavía. Ejecuta un escaneo desde el panel de auto-descubrimiento.</p>
      )}
    </div>
  );
}
