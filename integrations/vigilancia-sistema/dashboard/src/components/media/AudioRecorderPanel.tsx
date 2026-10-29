import { Download, Trash2, Mic } from "lucide-react";
import type { RecordingClip } from "../../types/camera";

interface AudioRecorderPanelProps {
  clips: RecordingClip[];
  onDelete: (id: string) => void;
}

export default function AudioRecorderPanel({ clips, onDelete }: AudioRecorderPanelProps) {
  const audioClips = clips.filter((c) => c.kind === "audio");

  if (audioClips.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-ops-inkfaint gap-2">
        <Mic className="w-5 h-5" />
        <p className="text-xs">Sin grabaciones de audio. Usa el botón de micrófono sobre cualquier cámara.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {audioClips.map((c) => (
        <div key={c.id} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-ops-panel2 bg-ops-panel">
          <span className="text-xs text-ops-inkdim w-28 shrink-0">{c.channelId}</span>
          <audio src={c.blobUrl} controls className="h-8 flex-1" />
          <span className="text-[10px] text-ops-inkdim w-12 text-right">{(c.durationMs / 1000).toFixed(1)}s</span>
          <a href={c.blobUrl} download={`audio-${c.id}.webm`} className="text-ops-accent"><Download className="w-4 h-4" /></a>
          <button onClick={() => onDelete(c.id)} className="text-ops-red hover:text-ops-red"><Trash2 className="w-4 h-4" /></button>
        </div>
      ))}
    </div>
  );
}
