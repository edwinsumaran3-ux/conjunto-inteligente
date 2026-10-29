import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef } from "react";
import type { CameraChannel } from "../../types/camera";
import CameraTile from "./CameraTile";

interface CameraCarouselHorizontalProps {
  channels: CameraChannel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function CameraCarouselHorizontal({ channels, selectedId, onSelect }: CameraCarouselHorizontalProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const scrollBy = (dx: number) => trackRef.current?.scrollBy({ left: dx, behavior: "smooth" });

  return (
    <div className="relative">
      <button onClick={() => scrollBy(-300)} className="absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-ops-panel/80 rounded-full p-1.5 border border-ops-panel2">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <div ref={trackRef} className="flex gap-2 overflow-x-auto scroll-smooth px-8 py-1 snap-x snap-mandatory">
        {channels.map((ch) => (
          <div
            key={ch.channelId}
            onClick={() => onSelect(ch.channelId)}
            className={`w-40 shrink-0 snap-start cursor-pointer rounded-lg ${selectedId === ch.channelId ? "ring-2 ring-ops-accent" : ""}`}
          >
            <CameraTile channel={ch} compact />
          </div>
        ))}
      </div>
      <button onClick={() => scrollBy(300)} className="absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-ops-panel/80 rounded-full p-1.5 border border-ops-panel2">
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
