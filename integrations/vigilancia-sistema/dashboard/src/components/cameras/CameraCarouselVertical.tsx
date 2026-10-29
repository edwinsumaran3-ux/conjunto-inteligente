import { ChevronUp, ChevronDown } from "lucide-react";
import { useRef } from "react";
import type { CameraChannel } from "../../types/camera";
import CameraTile from "./CameraTile";

interface CameraCarouselVerticalProps {
  channels: CameraChannel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function CameraCarouselVertical({ channels, selectedId, onSelect }: CameraCarouselVerticalProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const scrollBy = (dy: number) => trackRef.current?.scrollBy({ top: dy, behavior: "smooth" });

  return (
    <div className="relative">
      <button onClick={() => scrollBy(-220)} className="absolute top-0 left-1/2 -translate-x-1/2 z-10 bg-ops-panel/80 rounded-full p-1.5 border border-ops-panel2">
        <ChevronUp className="w-4 h-4" />
      </button>
      <div ref={trackRef} className="flex flex-col gap-2 overflow-y-auto scroll-smooth py-8 px-1 max-h-[520px] snap-y snap-mandatory">
        {channels.map((ch) => (
          <div
            key={ch.channelId}
            onClick={() => onSelect(ch.channelId)}
            className={`w-48 shrink-0 snap-start cursor-pointer rounded-lg ${selectedId === ch.channelId ? "ring-2 ring-ops-accent" : ""}`}
          >
            <CameraTile channel={ch} compact />
          </div>
        ))}
      </div>
      <button onClick={() => scrollBy(220)} className="absolute bottom-0 left-1/2 -translate-x-1/2 z-10 bg-ops-panel/80 rounded-full p-1.5 border border-ops-panel2">
        <ChevronDown className="w-4 h-4" />
      </button>
    </div>
  );
}
