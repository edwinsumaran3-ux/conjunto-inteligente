import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DiscoveredDevice, EdgeDevice, MeshTopology } from "../types/device";

export interface TopologySnapshot {
  edgeDevices: EdgeDevice[];
  discovered: DiscoveredDevice[];
  mesh: MeshTopology;
  online: boolean;
}

export function useEquipmentTopology(pollMs = 4000): TopologySnapshot {
  const [state, setState] = useState<TopologySnapshot>({ edgeDevices: [], discovered: [], mesh: {}, online: false });

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [edgeDevices, discovered, mesh] = await Promise.all([api.edgeDevices(), api.discoveryDevices(), api.meshTopology()]);
        if (!cancelled) setState({ edgeDevices: edgeDevices as EdgeDevice[], discovered: discovered as DiscoveredDevice[], mesh, online: true });
      } catch {
        if (!cancelled) setState((s) => ({ ...s, online: false }));
      }
    };
    tick();
    const t = setInterval(tick, pollMs);
    return () => { cancelled = true; clearInterval(t); };
  }, [pollMs]);

  return state;
}
