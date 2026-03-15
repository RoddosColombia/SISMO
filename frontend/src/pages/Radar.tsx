import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Target, Loader2, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "../components/ui/sonner";
import { RadarCard, RadarItem } from "../components/shared/RadarCard";
import { GestionModal } from "../components/shared/GestionModal";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SemanaStats {
  esperadas: number; pagadas: number; pendientes: number; nuevas_moras: number;
  valor_esperado: number; valor_cobrado: number; pct_cobranza: number;
  semana_inicio: string; semana_fin: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BUCKETS = ["RECUPERACION", "CRITICO", "URGENTE", "ACTIVO", "HOY", "MAÑANA"] as const;

const BUCKET_FILTER_STYLE: Record<string, { text: string; border: string; activeBg: string; label: string }> = {
  RECUPERACION: { text: "text-gray-300",   border: "border-gray-700",   activeBg: "bg-gray-900",        label: "RECUPERACIÓN" },
  CRITICO:      { text: "text-red-300",    border: "border-red-700",    activeBg: "bg-red-900/50",      label: "CRÍTICO" },
  URGENTE:      { text: "text-orange-300", border: "border-orange-700", activeBg: "bg-orange-900/40",   label: "URGENTE" },
  ACTIVO:       { text: "text-yellow-300", border: "border-yellow-600", activeBg: "bg-yellow-900/30",   label: "ACTIVO" },
  HOY:          { text: "text-blue-300",   border: "border-blue-600",   activeBg: "bg-blue-900/40",     label: "HOY" },
  "MAÑANA":     { text: "text-sky-300",    border: "border-sky-600",    activeBg: "bg-sky-900/30",      label: "MAÑANA" },
};

const fmt = (n: number) => `$${Math.round(n).toLocaleString("es-CO")}`;

// ── KPI Bar ───────────────────────────────────────────────────────────────────

function KpiBar({ semana, rollRate }: { semana: SemanaStats | null; rollRate: { roll_rate_pct?: number } | null }) {
  if (!semana) return <div className="h-16 bg-[#0A1628] animate-pulse rounded-xl mb-4" />;
  const pct = semana.pct_cobranza;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="kpi-bar">
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-3">
        <p className="text-[11px] text-slate-400 uppercase tracking-wide">Cobrado semana</p>
        <p className="text-xl font-bold text-emerald-400 mt-0.5">{fmt(semana.valor_cobrado)}</p>
        <p className="text-[11px] text-slate-500">de {fmt(semana.valor_esperado)}</p>
      </div>
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-3">
        <p className="text-[11px] text-slate-400 uppercase tracking-wide">% Cobranza</p>
        <p className={`text-xl font-bold mt-0.5 ${pct >= 80 ? "text-emerald-400" : pct >= 50 ? "text-yellow-400" : "text-red-400"}`}>
          {pct}%
        </p>
        <p className="text-[11px] text-slate-500">{semana.pagadas}/{semana.esperadas} cuotas</p>
      </div>
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-3">
        <p className="text-[11px] text-slate-400 uppercase tracking-wide">Nuevas moras</p>
        <p className="text-xl font-bold text-orange-400 mt-0.5">{semana.nuevas_moras}</p>
        <p className="text-[11px] text-slate-500">{semana.pendientes} cuotas pendientes</p>
      </div>
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-3">
        <p className="text-[11px] text-slate-400 uppercase tracking-wide">Roll Rate</p>
        <p className={`text-xl font-bold mt-0.5 ${(rollRate?.roll_rate_pct ?? 0) > 15 ? "text-red-400" : "text-emerald-400"}`}>
          {rollRate?.roll_rate_pct?.toFixed(0) ?? "—"}%
        </p>
        <p className="text-[11px] text-slate-500">meta: &lt;15%</p>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Radar() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [queue, setQueue]       = useState<RadarItem[]>([]);
  const [semana, setSemana]     = useState<SemanaStats | null>(null);
  const [rollRate, setRollRate] = useState<{ roll_rate_pct?: number } | null>(null);
  const [loading, setLoading]   = useState(true);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [buscar, setBuscar]     = useState("");
  const [gestionItem, setGestionItem] = useState<RadarItem | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [qRes, sRes, rRes] = await Promise.all([
        api.get("/radar/queue"),
        api.get("/radar/semana"),
        api.get("/radar/roll-rate").catch(() => ({ data: null })),
      ]);
      setQueue(qRes.data || []);
      setSemana(sRes.data);
      setRollRate(rRes.data);
    } catch {
      toast.error("Error cargando la cola de cobranza");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const filteredQueue = useMemo(() => {
    let q = queue;
    if (activeFilter) q = q.filter(i => i.bucket === activeFilter);
    if (buscar) {
      const b = buscar.toLowerCase();
      q = q.filter(i => i.cliente_nombre.toLowerCase().includes(b));
    }
    return q;
  }, [queue, activeFilter, buscar]);

  const bucketCounts: Record<string, number> = useMemo(() => {
    const counts: Record<string, number> = {};
    queue.forEach(i => { counts[i.bucket] = (counts[i.bucket] || 0) + 1; });
    return counts;
  }, [queue]);

  return (
    <div className="min-h-screen bg-[#060E1E] text-white px-4 py-5 md:px-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#0F2A5C] border border-[#1E3A5F] flex items-center justify-center">
            <Target size={18} className="text-[#00C8FF]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">RADAR</h1>
            <p className="text-[11px] text-slate-400">Cola operativa de cobranza</p>
          </div>
        </div>
        <button onClick={fetchAll} disabled={loading}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-[#1E3A5F] rounded-lg px-3 py-1.5 transition-colors"
          data-testid="radar-refresh-btn">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Actualizar
        </button>
      </div>

      {/* KPI Bar */}
      <KpiBar semana={semana} rollRate={rollRate} />

      {/* Filters — horizontal scroll on mobile */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0 sm:flex-wrap">
        <button
          onClick={() => setActiveFilter(null)}
          className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-full border transition-all ${
            !activeFilter
              ? "bg-[#1E3A5F] border-blue-600 text-white"
              : "bg-transparent border-[#1E3A5F] text-slate-500 hover:text-slate-300"
          }`}
          data-testid="filter-todos">
          Todos ({queue.length})
        </button>
        {BUCKETS.map(b => {
          const bs = BUCKET_FILTER_STYLE[b];
          const isActive = activeFilter === b;
          const count = bucketCounts[b] || 0;
          if (count === 0) return null;
          return (
            <button key={b}
              onClick={() => setActiveFilter(isActive ? null : b)}
              className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-full border transition-all ${
                isActive ? `${bs.activeBg} ${bs.text} ${bs.border}` : `bg-transparent border-[#1E3A5F] ${bs.text} opacity-70 hover:opacity-100`
              }`}
              data-testid={`filter-${b.replace(/\s/g, "-").toLowerCase()}`}>
              {bs.label} ({count})
            </button>
          );
        })}

        {/* Search — grows to fill remaining space */}
        <div className="relative shrink-0 ml-auto min-w-[140px]">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input type="text" placeholder="Buscar..."
            value={buscar} onChange={e => setBuscar(e.target.value)}
            className="bg-[#0D1E3A] border border-[#1E3A5F] text-white text-xs rounded-lg pl-7 pr-3 py-1.5 w-full focus:outline-none focus:border-blue-500"
            data-testid="radar-search-input" />
        </div>
      </div>

      <p className="text-xs text-slate-500 mb-3">{filteredQueue.length} clientes en cola</p>

      {/* Mobile-first cards grid: 1 col → 2 col sm → 3 col lg */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => <div key={i} className="h-48 bg-[#0D1E3A] rounded-xl animate-pulse" />)}
        </div>
      ) : filteredQueue.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Target size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No hay clientes en esta categoría</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredQueue.map(item => (
            <RadarCard
              key={item.loanbook_id}
              item={item}
              onGestion={setGestionItem}
              compact={false}
            />
          ))}
        </div>
      )}

      {/* Shared GestionModal */}
      {gestionItem && (
        <GestionModal
          loanbook_id={gestionItem.loanbook_id}
          cliente_nombre={gestionItem.cliente_nombre}
          onClose={() => setGestionItem(null)}
          onSave={() => { toast.success("Gestión registrada"); fetchAll(); }}
        />
      )}
    </div>
  );
}
