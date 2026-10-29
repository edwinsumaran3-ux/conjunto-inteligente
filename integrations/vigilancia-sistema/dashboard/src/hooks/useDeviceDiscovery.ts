import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { DiscoveredDevice } from "../types/device";

export function useDeviceDiscovery() {
  const [devices, setDevices] = useState<DiscoveredDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await api.discoveryDevices();
      setDevices(d as DiscoveredDevice[]);
      setError(null);
    } catch {
      setError("edge-gateway no disponible");
    }
  }, []);

  const scan = useCallback(async (addresses: string[], zone: string) => {
    setScanning(true);
    try {
      await api.discoveryScan(addresses, zone);
      await refresh();
    } catch {
      setError("no se pudo completar el escaneo");
    } finally {
      setScanning(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  return { devices, scanning, error, scan, refresh };
}
