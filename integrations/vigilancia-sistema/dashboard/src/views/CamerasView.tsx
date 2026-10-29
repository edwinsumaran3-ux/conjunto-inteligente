import { useState } from "react";
import { Camera as CameraIcon, Film, Mic as MicIcon } from "lucide-react";
import { useStore } from "../store/useStore";
import { useCameraChannels } from "../hooks/useCameraChannels";
import CameraGrid from "../components/cameras/CameraGrid";
import LayoutSelector from "../components/cameras/LayoutSelector";
import CameraCarouselHorizontal from "../components/cameras/CameraCarouselHorizontal";
import CameraCarouselVertical from "../components/cameras/CameraCarouselVertical";
import SnapshotGallery from "../components/media/SnapshotGallery";
import VideoEditorPanel from "../components/media/VideoEditorPanel";
import AudioRecorderPanel from "../components/media/AudioRecorderPanel";
import type { RecordingClip, Snapshot } from "../types/camera";

type MediaTab = "snapshots" | "video" | "audio";

export default function CamerasView() {
  const gridLayout = useStore((s) => s.gridLayout);
  const setGridLayout = useStore((s) => s.setGridLayout);
  const selectedChannelId = useStore((s) => s.selectedChannelId);
  const selectChannel = useStore((s) => s.selectChannel);
  const orientation = useStore((s) => s.carouselOrientation);
  const setOrientation = useStore((s) => s.setCarouselOrientation);

  const channels = useCameraChannels(gridLayout);
  const allChannels = useCameraChannels(24);

  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [clips, setClips] = useState<RecordingClip[]>([]);
  const [mediaTab, setMediaTab] = useState<MediaTab>("snapshots");

  const handleSnapshot = (s: Snapshot) => setSnapshots((prev) => [s, ...prev].slice(0, 60));
  const handleClip = (c: RecordingClip) => setClips((prev) => [c, ...prev].slice(0, 30));
  const handleDeleteClip = (id: string) => setClips((prev) => prev.filter((c) => c.id !== id));

  const Carousel = orientation === "horizontal" ? CameraCarouselHorizontal : CameraCarouselVertical;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-semibold">Monitor de cámaras</h2>
          <p className="text-xs text-ops-inkdim mt-0.5">1 a 24 canales · streams ONVIF/RTSP/HLS auto-conectados por el edge-gateway, o feed demo mientras no haya equipo asociado a un slot.</p>
        </div>
        <LayoutSelector layout={gridLayout} onChange={setGridLayout} orientation={orientation} onOrientationChange={setOrientation} />
      </div>

      <CameraGrid channels={channels} layout={gridLayout} onSnapshot={handleSnapshot} onClip={handleClip} />

      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-3">
        <p className="text-xs text-ops-inkdim mb-2">Todos los canales (1–24)</p>
        <Carousel channels={allChannels} selectedId={selectedChannelId} onSelect={selectChannel} />
      </div>

      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-4">
        <div className="flex gap-1 mb-3">
          {([
            { id: "snapshots", label: "Capturas", icon: CameraIcon, count: snapshots.length },
            { id: "video", label: "Grabaciones de video", icon: Film, count: clips.filter((c) => c.kind === "video").length },
            { id: "audio", label: "Grabaciones de audio", icon: MicIcon, count: clips.filter((c) => c.kind === "audio").length },
          ] as const).map((t) => (
            <button
              key={t.id}
              onClick={() => setMediaTab(t.id)}
              className={`px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 ${mediaTab === t.id ? "bg-ops-panel2 text-ops-accent" : "text-ops-inkdim"}`}
            >
              <t.icon className="w-3.5 h-3.5" /> {t.label} <span className="text-ops-inkfaint">({t.count})</span>
            </button>
          ))}
        </div>
        {mediaTab === "snapshots" && <SnapshotGallery snapshots={snapshots} />}
        {mediaTab === "video" && <VideoEditorPanel clips={clips} onDelete={handleDeleteClip} />}
        {mediaTab === "audio" && <AudioRecorderPanel clips={clips} onDelete={handleDeleteClip} />}
      </div>
    </div>
  );
}
