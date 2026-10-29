interface TopologyNodeProps {
  x: number;
  y: number;
  label: string;
  sublabel?: string;
  kind: "GATEWAY" | "CAMERA" | "SENSOR_LASER" | "SENSOR_IR" | "UNKNOWN";
  online: boolean;
  onClick?: () => void;
}

const KIND_COLOR: Record<TopologyNodeProps["kind"], string> = {
  GATEWAY: "#22d3ee", CAMERA: "#a78bfa", SENSOR_LASER: "#f87171", SENSOR_IR: "#fb923c", UNKNOWN: "#64748b",
};

export default function TopologyNode({ x, y, label, sublabel, kind, online, onClick }: TopologyNodeProps) {
  const color = KIND_COLOR[kind];
  return (
    <g transform={`translate(${x},${y})`} onClick={onClick} className={onClick ? "cursor-pointer" : ""}>
      <circle r={16} fill="#0f172a" stroke={color} strokeWidth={2} opacity={online ? 1 : 0.35} />
      <circle r={16} fill={color} opacity={online ? 0.15 : 0.05} />
      {online && <circle r={3} cy={-16} fill="#34d399" />}
      <text y={30} textAnchor="middle" fontSize="10" fill="#cbd5e1">{label}</text>
      {sublabel && <text y={42} textAnchor="middle" fontSize="8" fill="#64748b">{sublabel}</text>}
    </g>
  );
}
