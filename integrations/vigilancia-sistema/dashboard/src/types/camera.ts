export type GridLayout = 1 | 4 | 9 | 16 | 24;

export interface CameraChannel {
  channelId: string;
  slot: number;
  zone: string;
  streamUrl: string | null;
  protocol: "RTSP" | "ONVIF" | "HLS" | "DEMO";
  ptzCapable: boolean;
  audioCapable: boolean;
  vendor?: string;
  model?: string;
  fps: number;
  bitrateKbps: number;
  latencyMs: number;
  status: "ONLINE" | "OFFLINE" | "DEGRADED" | "CONNECTING";
  hasActiveAlert: boolean;
}

export interface PTZVector {
  pan: number;   // -1..1
  tilt: number;  // -1..1
  zoom: number;  // 0..1 (0 = sin zoom, 1 = zoom máximo)
}

export interface Snapshot {
  id: string;
  channelId: string;
  dataUrl: string;
  takenAt: number;
}

export interface RecordingClip {
  id: string;
  channelId: string;
  blobUrl: string;
  kind: "video" | "audio";
  durationMs: number;
  createdAt: number;
}
