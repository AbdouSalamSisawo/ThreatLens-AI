import { AlertTriangle, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
import type { Classification } from "../types/api";

export const CLASSIFICATION_META: Record<
  Classification,
  { label: string; text: string; border: string; bg: string; dot: string; icon: typeof ShieldCheck }
> = {
  likely_benign: {
    label: "Likely benign",
    text: "text-ok",
    border: "border-ok/30",
    bg: "bg-ok/10",
    dot: "bg-ok",
    icon: ShieldCheck,
  },
  suspicious: {
    label: "Suspicious",
    text: "text-warn",
    border: "border-warn/40",
    bg: "bg-warn/10",
    dot: "bg-warn",
    icon: ShieldQuestion,
  },
  high_risk: {
    label: "High risk",
    text: "text-danger",
    border: "border-danger/40",
    bg: "bg-danger/10",
    dot: "bg-danger",
    icon: ShieldAlert,
  },
};

export function StatusBadge({
  classification,
  size = "md",
}: {
  classification: Classification;
  size?: "sm" | "md";
}) {
  const meta = CLASSIFICATION_META[classification];
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-md border ${meta.border} ${meta.bg} ${meta.text} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1.5 text-sm"
      } font-medium`}
    >
      <Icon size={size === "sm" ? 13 : 16} aria-hidden />
      {meta.label}
      <span className="sr-only">classification</span>
    </span>
  );
}

export function SeverityDot({ severity }: { severity: string }) {
  const color =
    severity === "high"
      ? "bg-danger"
      : severity === "medium"
        ? "bg-warn"
        : severity === "low"
          ? "bg-info"
          : "bg-text-faint";
  return (
    <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${color}`} aria-hidden />
  );
}

export function UnertaintyNote({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <span className="inline-flex items-center gap-2 rounded-md border border-info/30 bg-info/10 px-3 py-1.5 text-xs text-info">
      <AlertTriangle size={13} aria-hidden />
      The score falls inside the model's documented uncertainty band — treat this
      result as inconclusive.
    </span>
  );
}
