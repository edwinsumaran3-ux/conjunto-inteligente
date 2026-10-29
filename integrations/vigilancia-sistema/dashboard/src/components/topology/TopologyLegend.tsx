const ITEMS: { label: string; color: string }[] = [
  { label: "Gateway", color: "#22d3ee" },
  { label: "Cámara", color: "#a78bfa" },
  { label: "Sensor láser", color: "#f87171" },
  { label: "Sensor IR", color: "#fb923c" },
  { label: "Sin identificar", color: "#64748b" },
];

export default function TopologyLegend() {
  return (
    <div className="flex flex-wrap gap-3 text-[11px] text-ops-inkdim">
      {ITEMS.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5 ml-2">
        <span className="w-2 h-2 rounded-full bg-ops-green" /> en línea
      </span>
    </div>
  );
}
