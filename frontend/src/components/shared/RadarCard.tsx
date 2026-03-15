import React from "react";
import { BucketBadge } from "./BucketBadge";
import { ScoreBadge } from "./ScoreBadge";
import { DiasProtocolo } from "./DiasProtocolo";
import { WhatsAppButton } from "./WhatsAppButton";

export interface RadarItem {
  loanbook_id: string;
  cliente_nombre: string;
  cliente_telefono: string;
  bucket: string;
  dpd_actual: number;
  total_a_pagar: number;
  dias_para_protocolo: number;
  whatsapp_link: string;
  score_letra: string;
  score_pago?: string;
  estrella_nivel: number;
  ultima_gestion_fecha?: string | null;
  ultima_gestion_resultado?: string | null;
  cuota_numero: number;
  mora?: number;
}

interface Props {
  item: RadarItem;
  onGestion: (item: RadarItem) => void;
  compact?: boolean;
}

function fmt(n: number) {
  return `$${Math.round(n).toLocaleString("es-CO")}`;
}

function fmtFecha(iso?: string | null) {
  if (!iso || iso.length < 10) return null;
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

function resultadoLabel(r?: string | null) {
  if (!r) return null;
  return r.replace(/_/g, " ");
}

export function RadarCard({ item, onGestion, compact = false }: Props) {
  const score = item.score_pago || item.score_letra;
  const nombreCorto = item.cliente_nombre.split(" ")[0];
  const ultimaFecha = fmtFecha(item.ultima_gestion_fecha);
  const ultimaRes   = resultadoLabel(item.ultima_gestion_resultado);

  return (
    <div
      data-testid={`radar-card-${item.loanbook_id}`}
      className={`bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4 flex flex-col gap-3 hover:border-blue-600/50 transition-colors ${compact ? "text-sm" : ""}`}
    >
      {/* Top row: name + badges */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-white truncate" data-testid={`radar-nombre-${item.loanbook_id}`}>
            {item.cliente_nombre}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">Cuota #{item.cuota_numero}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <BucketBadge bucket={item.bucket} dpd_actual={item.dpd_actual >= 0 ? item.dpd_actual : undefined} compact />
          <ScoreBadge score={score} estrella_nivel={item.estrella_nivel} compact />
        </div>
      </div>

      {/* Financials */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">Total a pagar</span>
        <span className="font-bold text-white">{fmt(item.total_a_pagar)}</span>
      </div>
      {(item.mora || 0) > 0 && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Interés mora</span>
          <span className="text-red-400">+{fmt(item.mora || 0)}</span>
        </div>
      )}

      {/* DiasProtocolo warning */}
      {item.dias_para_protocolo <= 7 && <DiasProtocolo dias_para_protocolo={item.dias_para_protocolo} />}

      {/* Last contact — BUILD 8 Ajuste 3 */}
      {ultimaFecha && (
        <div className="flex items-center gap-1.5 text-xs text-slate-500 border-t border-[#1E3A5F] pt-2">
          <span className="text-slate-600">Último contacto:</span>
          <span className="text-slate-400">{ultimaFecha}</span>
          {ultimaRes && <span className="text-slate-500 truncate">· {ultimaRes}</span>}
        </div>
      )}
      {!ultimaFecha && (
        <div className="text-xs text-slate-600 border-t border-[#1E3A5F] pt-2">
          Sin gestiones registradas
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-1">
        <WhatsAppButton
          telefono={item.cliente_telefono}
          nombre={nombreCorto}
          size={compact ? "sm" : "md"}
          className="flex-1"
          data-testid={`radar-wa-btn-${item.loanbook_id}`}
        />
        <button
          onClick={() => onGestion(item)}
          data-testid={`radar-gestion-btn-${item.loanbook_id}`}
          className={`flex-1 border border-blue-700 text-blue-300 rounded-lg font-medium hover:bg-blue-900/30 transition-colors ${compact ? "text-xs py-1 px-2" : "text-sm py-1.5 px-3"}`}
        >
          Gestión
        </button>
      </div>
    </div>
  );
}
