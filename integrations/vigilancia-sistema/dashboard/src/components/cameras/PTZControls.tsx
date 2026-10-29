import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Crosshair } from "lucide-react";
import { useState } from "react";
import type { PTZVector } from "../../types/camera";

interface PTZControlsProps {
  capable: boolean;
  onChange?: (v: PTZVector) => void;
}

const STEP = 0.15;

export default function PTZControls({ capable, onChange }: PTZControlsProps) {
  const [vec, setVec] = useState<PTZVector>({ pan: 0, tilt: 0, zoom: 0 });

  const apply = (delta: Partial<PTZVector>) => {
    setVec((prev) => {
      const next: PTZVector = {
        pan: Math.max(-1, Math.min(1, prev.pan + (delta.pan ?? 0))),
        tilt: Math.max(-1, Math.min(1, prev.tilt + (delta.tilt ?? 0))),
        zoom: Math.max(0, Math.min(1, prev.zoom + (delta.zoom ?? 0))),
      };
      onChange?.(next);
      return next;
    });
  };

  const reset = () => { const v = { pan: 0, tilt: 0, zoom: 0 }; setVec(v); onChange?.(v); };

  if (!capable) {
    return <p className="text-xs text-ops-inkdim">Este equipo no reporta capacidad PTZ; solo zoom digital disponible por software.</p>;
  }

  return (
    <div className="flex items-center gap-4">
      <div className="grid grid-cols-3 gap-1 w-28">
        <div />
        <button onClick={() => apply({ tilt: STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ChevronUp className="w-4 h-4" /></button>
        <div />
        <button onClick={() => apply({ pan: -STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ChevronLeft className="w-4 h-4" /></button>
        <button onClick={reset} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><Crosshair className="w-4 h-4 text-ops-accent" /></button>
        <button onClick={() => apply({ pan: STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ChevronRight className="w-4 h-4" /></button>
        <div />
        <button onClick={() => apply({ tilt: -STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ChevronDown className="w-4 h-4" /></button>
        <div />
      </div>
      <div className="flex flex-col items-center gap-1">
        <button onClick={() => apply({ zoom: STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ZoomIn className="w-4 h-4" /></button>
        <span className="text-[10px] text-ops-inkdim">{Math.round(vec.zoom * 100)}%</span>
        <button onClick={() => apply({ zoom: -STEP })} className="p-1.5 bg-ops-panel2 rounded hover:bg-ops-linesoft"><ZoomOut className="w-4 h-4" /></button>
      </div>
    </div>
  );
}
