import AutoDiscoveryPanel from "../components/discovery/AutoDiscoveryPanel";

export default function DeviceDiscoveryView() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-4">
        <h2 className="font-semibold">Auto-descubrimiento de equipos</h2>
        <p className="text-xs text-ops-inkdim mt-0.5">
          La conexión a los equipos es automática: se sondea el punto de conexión, se detecta marca/modelo/protocolo
          por firma y los equipos compatibles quedan conectados de inmediato, sin pasos manuales adicionales.
        </p>
      </div>
      <AutoDiscoveryPanel />
    </div>
  );
}
