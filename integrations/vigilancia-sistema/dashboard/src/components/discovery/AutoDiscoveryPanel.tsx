import { useState } from "react";
import type { ChangeEvent } from "react";
import { RadioTower, Loader2, Plug, Camera, Cable } from "lucide-react";
import { useDeviceDiscovery } from "../../hooks/useDeviceDiscovery";
import DeviceCompatibilityBadge from "./DeviceCompatibilityBadge";

const CLASS_ICON: Record<string, typeof Camera> = { CAMERA: Camera, SENSOR_LASER: Cable, SENSOR_IR: Cable, UNKNOWN: Plug };

/**
 * La conexión a los equipos es automática: el operador solo aporta el
 * rango de direcciones a sondear (o una dirección puntual) y la zona; el
 * backend (`device_autodiscovery.py` en el edge-gateway) se encarga de
 * identificar marca/modelo/protocolo por firma y de conectar de inmediato
 * los equipos compatibles, construyendo su URL de stream sin intervención
 * manual adicional.
 */
export default function AutoDiscoveryPanel() {
  const { devices, scanning, error, scan } = useDeviceDiscovery();
  const [range, setRange] = useState("192.168.1.10-192.168.1.30");
  const [zone, setZone] = useState("perimetro-norte");

  const handleScan = () => {
    const addresses = expandRange(range);
    if (addresses.length) scan(addresses, zone);
  };

  return (
    <div className="rounded-xl border border-ops-panel2 bg-ops-bg/60 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ops-ink flex items-center gap-2"><RadioTower className="w-4 h-4 text-ops-accent" /> Auto-descubrimiento y conexión de equipos</h3>
        {error && <span className="text-[11px] text-ops-amber">{error}</span>}
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-ops-inkdim flex flex-col gap-1">
          Rango de direcciones
          <input value={range} onChange={(e: ChangeEvent<HTMLInputElement>) => setRange(e.target.value)} className="bg-ops-panel border border-ops-panel2 rounded-lg px-2 py-1.5 text-xs w-64" placeholder="192.168.1.10-192.168.1.30" />
        </label>
        <label className="text-xs text-ops-inkdim flex flex-col gap-1">
          Zona
          <input value={zone} onChange={(e: ChangeEvent<HTMLInputElement>) => setZone(e.target.value)} className="bg-ops-panel border border-ops-panel2 rounded-lg px-2 py-1.5 text-xs w-40" />
        </label>
        <button onClick={handleScan} disabled={scanning} className="px-3 py-1.5 rounded-lg bg-ops-accent text-ops-bg text-xs font-medium flex items-center gap-1.5 disabled:opacity-50">
          {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RadioTower className="w-3.5 h-3.5" />}
          {scanning ? "escaneando..." : "escanear y conectar"}
        </button>
      </div>

      <div className="space-y-1.5">
        {devices.length === 0 && <p className="text-xs text-ops-inkfaint py-4 text-center">Sin equipos detectados. Ejecuta un escaneo del punto de conexión.</p>}
        {devices.map((d) => {
          const Icon = CLASS_ICON[d.device_class] ?? Plug;
          return (
            <div key={d.device_id} className="flex items-center justify-between px-3 py-2 rounded-lg border border-ops-panel2 bg-ops-panel text-xs">
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4 text-ops-inkdim" />
                <div>
                  <p className="text-ops-ink">{d.vendor} <span className="text-ops-inkfaint">· {d.model}</span></p>
                  <p className="text-ops-inkfaint">{d.address} · {d.protocol} · zona {d.zone || "sin asignar"}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <DeviceCompatibilityBadge compatibility={d.compatibility} />
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${d.auto_connected ? "bg-ops-green/15 text-ops-green" : "bg-ops-linesoft/40 text-ops-inkdim"}`}>
                  {d.auto_connected ? "conectado automáticamente" : "sin conectar"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function expandRange(input: string): string[] {
  const trimmed = input.trim();
  const m = trimmed.match(/^(\d+\.\d+\.\d+\.)(\d+)-(\d+)$/);
  if (m) {
    const [, base, start, end] = m;
    const s = Number(start), e = Number(end);
    if (Number.isFinite(s) && Number.isFinite(e) && e >= s && e - s < 64) {
      return Array.from({ length: e - s + 1 }, (_, i) => `${base}${s + i}`);
    }
  }
  return trimmed.split(",").map((s) => s.trim()).filter(Boolean);
}
