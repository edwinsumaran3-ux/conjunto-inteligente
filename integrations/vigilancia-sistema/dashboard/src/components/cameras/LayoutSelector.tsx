import { Grid2x2, Grid3x3, LayoutGrid, Rows3, Columns3 } from "lucide-react";
import type { GridLayout } from "../../types/camera";

const LAYOUTS: { value: GridLayout; icon: typeof Grid2x2 }[] = [
  { value: 1, icon: LayoutGrid },
  { value: 4, icon: Grid2x2 },
  { value: 9, icon: Grid3x3 },
  { value: 16, icon: Grid3x3 },
  { value: 24, icon: Grid3x3 },
];

interface LayoutSelectorProps {
  layout: GridLayout;
  onChange: (l: GridLayout) => void;
  orientation: "vertical" | "horizontal";
  onOrientationChange: (o: "vertical" | "horizontal") => void;
}

export default function LayoutSelector({ layout, onChange, orientation, onOrientationChange }: LayoutSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-ops-inkdim mr-1">Cámaras en pantalla</span>
      {LAYOUTS.map(({ value, icon: Icon }) => (
        <button
          key={value}
          onClick={() => onChange(value)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border ${
            layout === value ? "bg-ops-accent text-ops-bg border-ops-accent" : "bg-ops-panel text-ops-inkdim border-ops-panel2 hover:border-ops-linesoft"
          }`}
        >
          <Icon className="w-3.5 h-3.5" />
          {value}
        </button>
      ))}
      <div className="w-px h-5 bg-ops-panel2 mx-1" />
      <span className="text-xs text-ops-inkdim">Carrusel</span>
      <button
        onClick={() => onOrientationChange("horizontal")}
        className={`p-1.5 rounded-lg border ${orientation === "horizontal" ? "bg-ops-accent text-ops-bg border-ops-accent" : "bg-ops-panel text-ops-inkdim border-ops-panel2"}`}
        title="Carrusel horizontal"
      >
        <Columns3 className="w-4 h-4" />
      </button>
      <button
        onClick={() => onOrientationChange("vertical")}
        className={`p-1.5 rounded-lg border ${orientation === "vertical" ? "bg-ops-accent text-ops-bg border-ops-accent" : "bg-ops-panel text-ops-inkdim border-ops-panel2"}`}
        title="Carrusel vertical"
      >
        <Rows3 className="w-4 h-4" />
      </button>
    </div>
  );
}
