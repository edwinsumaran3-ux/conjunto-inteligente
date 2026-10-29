import EquipmentTopologyBoard from "../components/topology/EquipmentTopologyBoard";

export default function EquipmentTopologyView() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-4">
        <h2 className="font-semibold">Pizarra de flujo de equipos</h2>
        <p className="text-xs text-ops-inkdim mt-0.5">
          Escenario en tiempo real de cómo está cableada la instalación: gateway, sensores láser/IR y cámaras, con la
          malla de cascada (qué cámaras se reorientan cuando un sensor detecta interrupción).
        </p>
      </div>
      <EquipmentTopologyBoard />
    </div>
  );
}
