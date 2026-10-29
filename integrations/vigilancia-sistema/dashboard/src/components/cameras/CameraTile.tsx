import { useState } from "react";
import { AlertTriangle, WifiOff, Signal } from "lucide-react";
import type { CameraChannel, RecordingClip, Snapshot } from "../../types/camera";
import { useCameraStream } from "../../hooks/useCameraStream";
import { useMediaCapture } from "../../hooks/useMediaCapture";
import CameraFloatingToolbar from "./CameraFloatingToolbar";
import PTZControls from "./PTZControls";

interface CameraTileProps {
  channel: CameraChannel;
  compact?: boolean;
  onSnapshot?: (s: Snapshot) => void;
  onClip?: (c: RecordingClip) => void;
}

const STATUS_COLOR: Record<CameraChannel["status"], string> = {
  ONLINE: "bg-ops-green", OFFLINE: "bg-ops-inkfaint", DEGRADED: "bg-ops-amber", CONNECTING: "bg-ops-accent animate-pulse",
};

export default function CameraTile({ channel, compact, onSnapshot, onClip }: CameraTileProps) {
  const { videoRef, canvasRef, stats } = useCameraStream(channel);
  const { captureSnapshot, isRecordingVideo, startVideoRecording, stopVideoRecording, isRecordingAudio, startAudioRecording, stopAudioRecording } = useMediaCapture(channel.channelId, videoRef);
  const [expanded, setExpanded] = useState(false);

  const empty = channel.status === "OFFLINE" && !channel.streamUrl && channel.channelId.startsWith("empty-slot");

  const handleCapture = () => { const s = captureSnapshot(); if (s) onSnapshot?.(s); };
  const handleToggleVideo = async () => {
    if (isRecordingVideo) { const c = await stopVideoRecording(); if (c) onClip?.(c); }
    else startVideoRecording();
  };
  const handleToggleAudio = async () => {
    if (isRecordingAudio) { const c = await stopAudioRecording(); if (c) onClip?.(c); }
    else await startAudioRecording();
  };

  return (
    <div className={`relative rounded-xl overflow-hidden border ${channel.hasActiveAlert ? "border-ops-red" : "border-ops-panel2"} bg-black group ${expanded ? "fixed inset-4 z-50" : "aspect-video"}`}>
      <canvas ref={canvasRef} className="hidden" />
      {empty ? (
        <div className="w-full h-full flex flex-col items-center justify-center text-ops-inkfaint gap-1">
          <WifiOff className="w-6 h-6" />
          <span className="text-[11px]">Slot {channel.slot} · sin equipo conectado</span>
        </div>
      ) : (
        <video ref={videoRef} className="w-full h-full object-cover" playsInline />
      )}

      <div className="absolute top-1.5 left-1.5 flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-black/60 text-[10px] text-ops-ink">
        <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLOR[channel.status]}`} />
        CH{channel.slot} {channel.vendor ? `· ${channel.vendor}` : ""}
      </div>
      {channel.hasActiveAlert && (
        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-ops-red text-[10px] text-white flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> alerta
        </div>
      )}
      {!empty && !compact && (
        <div className="absolute bottom-1.5 left-1.5 flex items-center gap-2 px-1.5 py-0.5 rounded bg-black/60 text-[10px] text-ops-ink">
          <Signal className="w-3 h-3" /> {stats.fps} fps · {stats.bitrateKbps} kbps · {stats.latencyMs} ms
        </div>
      )}

      {!empty && (
        <CameraFloatingToolbar
          onCapture={handleCapture}
          isRecordingVideo={isRecordingVideo} onToggleVideo={handleToggleVideo}
          isRecordingAudio={isRecordingAudio} onToggleAudio={handleToggleAudio}
          expanded={expanded} onToggleExpand={() => setExpanded((e) => !e)}
        />
      )}

      {expanded && !empty && (
        <div className="absolute bottom-2 left-2 bg-ops-bg/80 rounded-lg p-2">
          <PTZControls capable={channel.ptzCapable} />
        </div>
      )}
    </div>
  );
}
