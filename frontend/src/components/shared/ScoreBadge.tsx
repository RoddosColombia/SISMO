import React from "react";

interface Props {
  score: string;
  estrella_nivel: number;
  compact?: boolean;
}

const SCORE_CONFIG: Record<string, { bg: string; text: string; border: string }> = {
  "A+": { bg: "bg-amber-500/20",   text: "text-amber-300",   border: "border-amber-500" },
  "A":  { bg: "bg-emerald-500/20", text: "text-emerald-300", border: "border-emerald-500" },
  "B":  { bg: "bg-yellow-500/20",  text: "text-yellow-300",  border: "border-yellow-500" },
  "C":  { bg: "bg-orange-500/20",  text: "text-orange-300",  border: "border-orange-500" },
  "D":  { bg: "bg-red-500/20",     text: "text-red-300",     border: "border-red-500" },
  "E":  { bg: "bg-gray-800",       text: "text-gray-400",    border: "border-gray-600" },
  "F":  { bg: "bg-gray-800",       text: "text-gray-400",    border: "border-gray-600" },
};

export function ScoreBadge({ score, estrella_nivel, compact = false }: Props) {
  const cfg = SCORE_CONFIG[score] ?? SCORE_CONFIG["B"];
  const stars = Math.max(0, Math.min(5, estrella_nivel));
  return (
    <span
      data-testid={`score-badge-${score}`}
      className={`inline-flex items-center gap-1 border rounded-full font-semibold ${cfg.bg} ${cfg.text} ${cfg.border} ${compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"}`}
    >
      {"⭐".repeat(stars)}{stars === 0 ? "☆" : ""} {score}
    </span>
  );
}
