import { useMemo } from "react";
import { useDeviceDiscovery } from "./useDeviceDiscovery";
import type { CameraChannel, GridLayout } from "../types/camera";

/**
 * Construye la lista de canales que alimenta el grid de cámaras: las
 * cámaras ya auto-descubiertas y conectadas ocupan los primeros slots, y
 * el resto hasta completar el layout elegido (1/4/9/16/24) aparece como
 * "sin equipo" — así el operador ve de inmediato cuántos puntos de
 * conexión están libres y cuáles ya tienen hardware asociado.
 */
export function useCameraChannels(layout: GridLayout): CameraChannel[] {
  const { devices } = useDeviceDiscovery();

  return useMemo(() => {
    const cameras = devices.filter((d) => d.device_class === "CAMERA");
    const channels: CameraChannel[] = [];
    for (let slot = 1; slot <= layout; slot++) {
      const found = cameras[slot - 1];
      if (found) {
        channels.push({
          channelId: found.device_id,
          slot,
          zone: found.zone || "sin zona",
          streamUrl: found.stream_url,
          protocol: found.protocol === "ONVIF" ? "RTSP" : (found.protocol as CameraChannel["protocol"]) || "DEMO",
          ptzCapable: found.compatibility === "NATIVE",
          audioCapable: found.compatibility !== "LIMITED",
          vendor: found.vendor,
          model: found.model,
          fps: 0, bitrateKbps: 0, latencyMs: 0,
          status: found.auto_connected ? "ONLINE" : "CONNECTING",
          hasActiveAlert: false,
        });
      } else {
        channels.push({
          channelId: `empty-slot-${slot}`, slot, zone: "", streamUrl: null, protocol: "DEMO",
          ptzCapable: false, audioCapable: false, fps: 0, bitrateKbps: 0, latencyMs: 0,
          status: "OFFLINE", hasActiveAlert: false,
        });
      }
    }
    return channels;
  }, [devices, layout]);
}
