import React from "react";

interface Props {
  bucket: string;
  dpd_actual?: number;
  compact?: boolean;
}

const BUCKET_CONFIG: Record<string, { bg: string; text: string; border: string; label: string }> = {
  RECUPERACION: { bg: "bg-gray-900",    text: "text-white",       border: "border-gray-700",   label: "RECUPERACIÓN" },
  CRITICO:      { bg: "bg-red-900/60",  text: "text-red-300",     border: "border-red-700",    label: "CRÍTICO" },
  URGENTE:      { bg: "bg-orange-900/50", text: "text-orange-300", border: "border-orange-700", label: "URGENTE" },
  ACTIVO:       { bg: "bg-yellow-900/40", text: "text-yellow-300", border: "border-yellow-600", label: "ACTIVO" },
  HOY:          { bg: "bg-blue-900/40",  text: "text-blue-300",    border: "border-blue-600",   label: "HOY" },
  MAÑANA:       { bg: "bg-sky-900/40",   text: "text-sky-300",     border: "border-sky-600",    label: "MAÑANA" },
  AL_DIA:       { bg: "bg-emerald-900/30", text: "text-emerald-400", border: "border-emerald-700", label: "AL DÍA" },
  // Numeric bucket format (from DPD engine)
  "0":    { bg: "bg-slate-700/40",    text: "text-slate-300",  border: "border-slate-600",  label: "AL DÍA" },
  "1-7":  { bg: "bg-yellow-900/40",   text: "text-yellow-300", border: "border-yellow-600", label: "ACTIVO" },
  "8-14": { bg: "bg-orange-900/50",   text: "text-orange-300", border: "border-orange-700", label: "URGENTE" },
  "15-21":{ bg: "bg-red-900/60",      text: "text-red-300",    border: "border-red-700",    label: "CRÍTICO" },
  "22+":  { bg: "bg-gray-900",        text: "text-white",      border: "border-gray-700",   label: "RECUPERACIÓN" },
};

export function BucketBadge({ bucket, dpd_actual, compact = false }: Props) {
  const cfg = BUCKET_CONFIG[bucket] ?? { bg: "bg-slate-700", text: "text-slate-300", border: "border-slate-600", label: bucket };
  const dpd = dpd_actual !== undefined && dpd_actual >= 0 ? ` · ${dpd_actual}d` : "";
  return (
    <span
      data-testid={`bucket-badge-${bucket}`}
      className={`inline-flex items-center gap-1 border rounded-full font-semibold uppercase tracking-wide ${cfg.bg} ${cfg.text} ${cfg.border} ${compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"}`}
    >
      {cfg.label}{dpd}
    </span>
  );
}
