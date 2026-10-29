import type { LucideIcon } from "lucide-react";

interface FloatingActionButtonProps {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  active?: boolean;
  danger?: boolean;
  disabled?: boolean;
}

export default function FloatingActionButton({ icon: Icon, label, onClick, active, danger, disabled }: FloatingActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`w-11 h-11 rounded-full flex items-center justify-center shadow-lg backdrop-blur transition-colors
        ${disabled ? "opacity-40 cursor-not-allowed bg-ops-panel2/70" : ""}
        ${!disabled && danger ? "bg-ops-red/90 hover:bg-ops-red text-white" : ""}
        ${!disabled && !danger && active ? "bg-ops-accent text-ops-bg" : ""}
        ${!disabled && !danger && !active ? "bg-ops-panel2/80 hover:bg-ops-linesoft text-ops-ink" : ""}`}
    >
      <Icon className="w-5 h-5" />
    </button>
  );
}
