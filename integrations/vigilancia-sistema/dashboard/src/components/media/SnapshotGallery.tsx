import { Download, ImageOff } from "lucide-react";
import type { Snapshot } from "../../types/camera";

interface SnapshotGalleryProps {
  snapshots: Snapshot[];
}

export default function SnapshotGallery({ snapshots }: SnapshotGalleryProps) {
  if (snapshots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-ops-inkfaint gap-2">
        <ImageOff className="w-6 h-6" />
        <p className="text-xs">Sin capturas todavía. Usa el botón de cámara sobre cualquier tile.</p>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {snapshots.map((s) => (
        <div key={s.id} className="relative rounded-lg overflow-hidden border border-ops-panel2 group">
          <img src={s.dataUrl} alt={`captura ${s.channelId}`} className="w-full aspect-video object-cover" />
          <div className="absolute bottom-0 inset-x-0 bg-black/70 text-[10px] px-1.5 py-1 flex items-center justify-between">
            <span>{new Date(s.takenAt).toLocaleTimeString()}</span>
            <a href={s.dataUrl} download={`captura-${s.channelId}-${s.takenAt}.png`} className="text-ops-accent">
              <Download className="w-3 h-3" />
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}
