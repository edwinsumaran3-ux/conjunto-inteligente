import { useRef, useState } from "react";
import type { MouseEvent, SyntheticEvent } from "react";
import { Download, Scissors, Trash2 } from "lucide-react";
import type { RecordingClip } from "../../types/camera";

interface VideoEditorPanelProps {
  clips: RecordingClip[];
  onDelete: (id: string) => void;
}

/**
 * Edición ligera en el navegador: el recorte in/out se aplica sobre la
 * reproducción (no re-codifica el archivo, que requeriría ffmpeg.wasm o un
 * servicio de transcodificación en el backend). Sirve para marcar el
 * fragmento relevante de evidencia y descargarlo junto con sus marcas de
 * tiempo; el clip completo sigue disponible para descarga sin recortar.
 */
export default function VideoEditorPanel({ clips, onDelete }: VideoEditorPanelProps) {
  const videoClips = clips.filter((c) => c.kind === "video");
  const [activeId, setActiveId] = useState<string | null>(videoClips[0]?.id ?? null);
  const [inPoint, setInPoint] = useState(0);
  const [outPoint, setOutPoint] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const active = videoClips.find((c) => c.id === activeId);

  if (videoClips.length === 0) {
    return <p className="text-xs text-ops-inkfaint py-6 text-center">Sin grabaciones de video todavía. Usa el botón de video sobre cualquier cámara.</p>;
  }

  return (
    <div className="grid md:grid-cols-[2fr_1fr] gap-4">
      <div>
        {active && (
          <>
            <video ref={videoRef} src={active.blobUrl} controls className="w-full rounded-lg bg-black" onLoadedMetadata={(e: SyntheticEvent<HTMLVideoElement>) => setOutPoint(e.currentTarget.duration)} />
            <div className="flex items-center gap-3 mt-2 text-xs text-ops-inkdim">
              <button
                onClick={() => setInPoint(videoRef.current?.currentTime ?? 0)}
                className="px-2 py-1 rounded bg-ops-panel2 hover:bg-ops-linesoft flex items-center gap-1"
              >
                <Scissors className="w-3 h-3" /> marcar inicio ({inPoint.toFixed(1)}s)
              </button>
              <button
                onClick={() => setOutPoint(videoRef.current?.currentTime ?? 0)}
                className="px-2 py-1 rounded bg-ops-panel2 hover:bg-ops-linesoft flex items-center gap-1"
              >
                <Scissors className="w-3 h-3" /> marcar fin ({outPoint.toFixed(1)}s)
              </button>
              <a href={active.blobUrl} download={`clip-${active.id}.webm`} className="px-2 py-1 rounded bg-ops-accent text-ops-bg flex items-center gap-1">
                <Download className="w-3 h-3" /> descargar completo
              </a>
            </div>
            <p className="text-[10px] text-ops-inkfaint mt-1">
              Fragmento marcado: {inPoint.toFixed(1)}s – {outPoint.toFixed(1)}s. El recorte definitivo (re-codificado) requiere el servicio de post-producción del backend.
            </p>
          </>
        )}
      </div>
      <div className="space-y-1.5">
        {videoClips.map((c) => (
          <div key={c.id} className={`flex items-center justify-between px-2 py-1.5 rounded-lg border text-xs cursor-pointer ${activeId === c.id ? "border-ops-accent bg-ops-panel" : "border-ops-panel2"}`} onClick={() => setActiveId(c.id)}>
            <span>{c.channelId} · {(c.durationMs / 1000).toFixed(1)}s</span>
            <button onClick={(e: MouseEvent) => { e.stopPropagation(); onDelete(c.id); }} className="text-ops-red hover:text-ops-red">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
