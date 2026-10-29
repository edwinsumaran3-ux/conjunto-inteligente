import { Camera, Video, Square, Mic, Maximize2, Minimize2 } from "lucide-react";
import FloatingActionButton from "../shared/FloatingActionButton";

interface CameraFloatingToolbarProps {
  onCapture: () => void;
  isRecordingVideo: boolean;
  onToggleVideo: () => void;
  isRecordingAudio: boolean;
  onToggleAudio: () => void;
  expanded: boolean;
  onToggleExpand: () => void;
}

export default function CameraFloatingToolbar({
  onCapture, isRecordingVideo, onToggleVideo, isRecordingAudio, onToggleAudio, expanded, onToggleExpand,
}: CameraFloatingToolbarProps) {
  return (
    <div className="absolute bottom-2 right-2 flex gap-2 z-10">
      <FloatingActionButton icon={Camera} label="Capturar imagen" onClick={onCapture} />
      <FloatingActionButton icon={isRecordingVideo ? Square : Video} label={isRecordingVideo ? "Detener grabación de video" : "Grabar video"} onClick={onToggleVideo} active={isRecordingVideo} danger={isRecordingVideo} />
      <FloatingActionButton icon={isRecordingAudio ? Square : Mic} label={isRecordingAudio ? "Detener grabación de audio" : "Grabar audio"} onClick={onToggleAudio} active={isRecordingAudio} danger={isRecordingAudio} />
      <FloatingActionButton icon={expanded ? Minimize2 : Maximize2} label={expanded ? "Salir de pantalla completa" : "Ampliar"} onClick={onToggleExpand} />
    </div>
  );
}
