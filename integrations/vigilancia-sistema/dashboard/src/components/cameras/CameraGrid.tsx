import type { CameraChannel, GridLayout, RecordingClip, Snapshot } from "../../types/camera";
import CameraTile from "./CameraTile";

const COLS: Record<GridLayout, string> = {
  1: "grid-cols-1",
  4: "grid-cols-2",
  9: "grid-cols-3",
  16: "grid-cols-4",
  24: "grid-cols-4 sm:grid-cols-6",
};

interface CameraGridProps {
  channels: CameraChannel[];
  layout: GridLayout;
  onSnapshot?: (s: Snapshot) => void;
  onClip?: (c: RecordingClip) => void;
}

export default function CameraGrid({ channels, layout, onSnapshot, onClip }: CameraGridProps) {
  return (
    <div className={`grid ${COLS[layout]} gap-2`}>
      {channels.slice(0, layout).map((ch) => (
        <CameraTile key={ch.channelId} channel={ch} compact={layout >= 16} onSnapshot={onSnapshot} onClip={onClip} />
      ))}
    </div>
  );
}
