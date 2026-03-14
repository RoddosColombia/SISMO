import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Users, Search, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { Input } from "../components/ui/input";

const BUCKET_STYLE: Record<string, { bg: string; text: string; border: string; label: string }> = {
  RECUPERACION: { bg: "bg-red-900/20",    text: "text-red-400",    border: "border-red-800",    label: "RECUPERACIÓN" },
  CRITICO:      { bg: "bg-red-800/15",    text: "text-red-300",    border: "border-red-700",    label: "CRÍTICO" },
  URGENTE:      { bg: "bg-orange-900/20", text: "text-orange-400", border: "border-orange-700", label: "URGENTE" },
  ACTIVO:       { bg: "bg-yellow-900/15", text: "text-yellow-400", border: "border-yellow-700", label: "ACTIVO" },
  HOY:          { bg: "bg-blue-900/20",   text: "text-blue-400",   border: "border-blue-700",   label: "HOY" },
  AL_DIA:       { bg: "bg-emerald-900/15",text: "text-emerald-400",border: "border-emerald-700",label: "AL DÍA" },
};

const SCORE_STYLE: Record<string, { bg: string; text: string }> = {
  A: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  B: { bg: "bg-blue-500/15",    text: "text-blue-400" },
  C: { bg: "bg-yellow-500/15",  text: "text-yellow-400" },
  F: { bg: "bg-red-500/15",     text: "text-red-400" },
};

const BUCKET_FILTERS = ["", "RECUPERACION", "CRITICO", "URGENTE", "ACTIVO", "HOY", "AL_DIA"];
const SCORE_FILTERS  = ["", "A", "B", "C", "F"];

const fmt = (n: number) => `$${Math.round(n).toLocaleString("es-CO")}`;

export default function CRMList() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [clientes, setClientes] = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [buscar, setBuscar]     = useState("");
  const [bucket, setBucket]     = useState("");
  const [score, setScore]       = useState("");
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null);

  const fetchClientes = useCallback(async (q: string, b: string, s: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("buscar", q);
      if (b) params.set("bucket", b);
      if (s) params.set("score", s);
      const res = await api.get(`/crm?${params.toString()}`);
      setClientes(res.data || []);
    } catch {
      setClientes([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchClientes("", "", ""); }, [fetchClientes]);

  const handleBuscar = (val: string) => {
    setBuscar(val);
    if (debounceTimer) clearTimeout(debounceTimer);
    const t = setTimeout(() => fetchClientes(val, bucket, score), 350);
    setDebounceTimer(t);
  };

  const handleBucket = (val: string) => { setBucket(val); fetchClientes(buscar, val, score); };
  const handleScore  = (val: string) => { setScore(val);  fetchClientes(buscar, bucket, val); };

  return (
    <div className="min-h-screen bg-[#060E1E] text-white px-4 py-5 md:px-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 rounded-xl bg-[#0F2A5C] border border-[#1E3A5F] flex items-center justify-center">
          <Users size={18} className="text-[#00C8FF]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">CRM</h1>
          <p className="text-[11px] text-slate-400">Base de clientes RODDOS</p>
        </div>
        <button onClick={() => fetchClientes(buscar, bucket, score)} disabled={loading}
          className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-[#1E3A5F] rounded-lg px-3 py-1.5 transition-colors">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative flex-1 min-w-44">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <Input value={buscar} onChange={e => handleBuscar(e.target.value)}
            placeholder="Buscar por nombre, cédula o teléfono..."
            className="pl-7 bg-[#0D1E3A] border-[#1E3A5F] text-white text-sm"
            data-testid="crm-search-input" />
        </div>
        <select value={bucket} onChange={e => handleBucket(e.target.value)}
          className="bg-[#0D1E3A] border border-[#1E3A5F] text-white text-sm rounded-lg px-3 py-2 focus:outline-none"
          data-testid="crm-bucket-filter">
          <option value="">Todos los buckets</option>
          {BUCKET_FILTERS.slice(1).map(b => (
            <option key={b} value={b}>{BUCKET_STYLE[b]?.label || b}</option>
          ))}
        </select>
        <select value={score} onChange={e => handleScore(e.target.value)}
          className="bg-[#0D1E3A] border border-[#1E3A5F] text-white text-sm rounded-lg px-3 py-2 focus:outline-none"
          data-testid="crm-score-filter">
          <option value="">Todos los scores</option>
          {SCORE_FILTERS.slice(1).map(s => <option key={s} value={s}>Score {s}</option>)}
        </select>
      </div>

      <p className="text-xs text-slate-500 mb-3">{clientes.length} clientes</p>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 size={24} className="animate-spin text-[#00C8FF]" /></div>
      ) : clientes.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Users size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No se encontraron clientes</p>
        </div>
      ) : (
        <div className="space-y-2">
          {clientes.map(c => {
            const bs = BUCKET_STYLE[c.bucket] || BUCKET_STYLE.AL_DIA;
            const ss = SCORE_STYLE[c.score_letra] || SCORE_STYLE.C;
            const stars = c.score_letra === "A" ? "★★★" : c.score_letra === "B" ? "★★" : c.score_letra === "C" ? "★" : "";
            return (
              <div key={c.loanbook_id}
                onClick={() => navigate(`/crm/${c.loanbook_id}`)}
                className="flex items-center gap-3 bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl px-4 py-3 cursor-pointer hover:border-[#00C8FF]/30 transition-all group"
                data-testid={`crm-client-${c.loanbook_id}`}>
                <div className="w-8 h-8 rounded-full bg-[#0F2A5C] border border-[#1E3A5F] flex items-center justify-center text-xs font-bold text-[#00C8FF] flex-shrink-0">
                  {(c.cliente_nombre || "?")[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{c.cliente_nombre}</p>
                  <p className="text-[11px] text-slate-400">{c.moto || c.plan} · {c.cliente_telefono}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${bs.bg} ${bs.text} border ${bs.border}`}>{bs.label}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${ss.bg} ${ss.text}`}>{stars}{c.score_letra}</span>
                  {c.dpd_actual > 0 && (
                    <span className="text-[10px] text-slate-400">{c.dpd_actual}d</span>
                  )}
                  <ChevronRight size={14} className="text-slate-600 group-hover:text-slate-400 transition-colors" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
