import type { Compatibility } from "../../types/device";

const STYLE: Record<Compatibility, string> = {
  NATIVE: "bg-ops-green/15 text-ops-green border-ops-green/30",
  COMPATIBLE: "bg-ops-accent/15 text-ops-accent border-ops-accent/30",
  LIMITED: "bg-ops-amber/15 text-ops-amber border-ops-amber/30",
  UNKNOWN: "bg-ops-linesoft/30 text-ops-inkdim border-ops-linesoft",
};

const LABEL: Record<Compatibility, string> = {
  NATIVE: "compatibilidad nativa", COMPATIBLE: "compatible", LIMITED: "compatibilidad limitada", UNKNOWN: "sin verificar",
};

export default function DeviceCompatibilityBadge({ compatibility }: { compatibility: Compatibility }) {
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${STYLE[compatibility]}`}>{LABEL[compatibility]}</span>;
}
