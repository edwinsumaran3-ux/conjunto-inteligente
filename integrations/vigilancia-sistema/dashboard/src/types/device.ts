export type DeviceClass = "CAMERA" | "SENSOR_IR" | "SENSOR_LASER" | "GATEWAY" | "UNKNOWN";
export type Compatibility = "NATIVE" | "COMPATIBLE" | "LIMITED" | "UNKNOWN";

export interface DiscoveredDevice {
  device_id: string;
  device_class: DeviceClass;
  vendor: string;
  model: string;
  protocol: string;
  address: string;
  compatibility: Compatibility;
  zone: string;
  auto_connected: boolean;
  stream_url: string | null;
  last_seen: number;
}

export interface MeshTopology {
  [sensorId: string]: string[]; // sensor_id -> camera_ids vecinas
}

export interface EdgeDevice {
  device_id: string;
  last_seen: number;
  healthy: boolean;
  missed_heartbeats: number;
  fw_version: string;
  zone: string;
  metadata: Record<string, unknown>;
}
