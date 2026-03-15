import React from "react";

interface Props {
  dias_para_protocolo: number;
}

export function DiasProtocolo({ dias_para_protocolo }: Props) {
  if (dias_para_protocolo > 7) return null;
  if (dias_para_protocolo <= 3) {
    return (
      <span
        data-testid="dias-protocolo-critico"
        className="inline-flex items-center gap-1 text-red-400 text-xs font-bold animate-pulse"
      >
        🚨 {dias_para_protocolo} día{dias_para_protocolo !== 1 ? "s" : ""} para recuperación
      </span>
    );
  }
  return (
    <span
      data-testid="dias-protocolo-advertencia"
      className="inline-flex items-center gap-1 text-orange-400 text-xs font-medium"
    >
      ⚠️ {dias_para_protocolo} días para protocolo
    </span>
  );
}
