import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Target, Phone, MessageCircle, Loader2, RefreshCw, Search,
  AlertTriangle, Clock, ChevronRight, X,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "../components/ui/sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

// ── Types ─────────────────────────────────────────────────────────────────────

interface QueueItem {
  loanbook_id: string; codigo: string; cliente_nombre: string; cliente_telefono: string;
  cuota_numero: number; fecha_vencimiento: string; bucket: string; dpd_actual: number;
  total_a_pagar: number; mora: number; dias_para_protocolo: number; whatsapp_link: string;
  saldo_total: number; score_pct: number; score_letra: string;
}

interface SemanaStats {
  esperadas: number; pagadas: number; pendientes: number; nuevas_moras: number;
  valor_esperado: number; valor_cobrado: number; pct_cobranza: number;
  semana_inicio: string; semana_fin: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BUCKETS = ["RECUPERACION", "CRITICO", "URGENTE", "ACTIVO", "HOY", "MAÑANA", "AL DÍA"] as const;

const BUCKET_STYLE: Record<string, { bg: string; text: string; border: string; label: string }> = {
  RECUPERACION: { bg: "bg-red-900/30",    text: "text-red-400",    border: "border-red-800",    label: "RECUPERACIÓN" },
  CRITICO:      { bg: "bg-red-800/25",    text: "text-red-300",    border: "border-red-700",    label: "CRÍTICO" },
  URGENTE:      { bg: "bg-orange-900/25", text: "text-orange-400", border: "border-orange-700", label: "URGENTE" },
  ACTIVO:       { bg: "bg-yellow-900/20", text: "text-yellow-400", border: "border-yellow-700", label: "ACTIVO" },
  HOY:          { bg: "bg-blue-900/25",   text: "text-blue-400",   border: "border-blue-700",   label: "HOY" },
  "MAÑANA":     { bg: "bg-sky-900/20",    text: "text-sky-400",    border: "border-sky-700",    label: "MAÑANA" },
};

const SCORE_STYLE: Record<string, { bg: string; text: string }> = {
  A: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  B: { bg: "bg-blue-500/15",    text: "text-blue-400" },
  C: { bg: "bg-yellow-500/15",  text: "text-yellow-400" },
  F: { bg: "bg-red-500/15",     text: "text-red-400" },
};

const CANALES  = ["llamada", "whatsapp", "visita", "email"];
const RESULTADOS = [
  "contestó_pagará_hoy", "contestó_prometió_fecha", "contestó_no_pagará",
  "no_contestó", "número_equivocado", "respondió_pagará", "respondió_prometió_fecha",
  "visto_sin_respuesta", "no_entregado", "acuerdo_de_pago_firmado",
];

const fmt = (n: number) => `$${Math.round(n).toLocaleString("es-CO")}`;

// ── KPI Bar ───────────────────────────────────────────────────────────────────

function KpiBar({ semana, rollRate }: { semana: SemanaStats | null; rollRate: any }) {
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
        <p className={`text-xl font-bold mt-0.5 ${semana.nuevas_moras > 0 ? "text-orange-400" : "text-emerald-400"}`}>
          {semana.nuevas_moras}
        </p>
        <p className="text-[11px] text-slate-500">{semana.semana_inicio} → {semana.semana_fin}</p>
      </div>
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-3">
        <p className="text-[11px] text-slate-400 uppercase tracking-wide">Roll Rate</p>
        <p className={`text-xl font-bold mt-0.5 ${(rollRate?.roll_rate_pct || 0) > 15 ? "text-red-400" : "text-emerald-400"}`}>
          {rollRate?.roll_rate_pct?.toFixed(1) ?? "—"}%
        </p>
        <p className="text-[11px] text-slate-500">mora → mora agravada</p>
      </div>
    </div>
  );
}

// ── RadarCard ─────────────────────────────────────────────────────────────────

function RadarCard({ item, onGestion, onClick }: {
  item: QueueItem;
  onGestion: (item: QueueItem) => void;
  onClick: (item: QueueItem) => void;
}) {
  const bs = BUCKET_STYLE[item.bucket] || BUCKET_STYLE.ACTIVO;
  const ss = SCORE_STYLE[item.score_letra] || SCORE_STYLE.C;
  const stars = item.score_letra === "A" ? "★★★" : item.score_letra === "B" ? "★★" : item.score_letra === "C" ? "★" : "";
  const isProtocol = item.dias_para_protocolo <= 3 && item.dpd_actual > 0;

  return (
    <div
      className={`relative bg-[#0D1E3A] border rounded-xl p-4 cursor-pointer hover:border-[#00C8FF]/40 transition-all group ${bs.border}`}
      onClick={() => onClick(item)}
      data-testid={`radar-card-${item.loanbook_id}`}
    >
      {/* Protocol alert */}
      {isProtocol && (
        <div className="absolute top-2 right-2">
          <AlertTriangle size={14} className="text-red-400 animate-pulse" />
        </div>
      )}

      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{item.cliente_nombre}</p>
          <p className="text-[11px] text-slate-400 font-mono">{item.codigo} · Cuota #{item.cuota_numero}</p>
        </div>
        <div className="flex gap-1.5 flex-shrink-0">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${bs.bg} ${bs.text} border ${bs.border}`}>
            {bs.label}
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${ss.bg} ${ss.text}`}>
            {stars && <span className="mr-0.5">{stars}</span>}{item.score_letra}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3 text-center">
        <div className="bg-[#091529] rounded-lg p-1.5">
          <p className="text-[10px] text-slate-500">Valor cuota</p>
          <p className="text-xs font-bold text-white">{fmt(item.total_a_pagar)}</p>
        </div>
        <div className="bg-[#091529] rounded-lg p-1.5">
          <p className="text-[10px] text-slate-500">Mora</p>
          <p className={`text-xs font-bold ${item.mora > 0 ? "text-orange-400" : "text-slate-400"}`}>{fmt(item.mora)}</p>
        </div>
        <div className="bg-[#091529] rounded-lg p-1.5">
          <p className="text-[10px] text-slate-500">DPD</p>
          <p className={`text-xs font-bold ${item.dpd_actual >= 15 ? "text-red-400" : item.dpd_actual >= 8 ? "text-orange-400" : "text-yellow-400"}`}>
            {item.dpd_actual > 0 ? `${item.dpd_actual}d` : item.dpd_actual === -1 ? "mañana" : "hoy"}
          </p>
        </div>
      </div>

      {isProtocol && (
        <div className="mb-3 text-[10px] text-red-400 flex items-center gap-1">
          <AlertTriangle size={10} /> {item.dias_para_protocolo === 0 ? "¡Protocolo activo hoy!" : `Protocolo en ${item.dias_para_protocolo}d`}
        </div>
      )}

      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
        <a
          href={item.whatsapp_link || "#"}
          target="_blank" rel="noreferrer"
          className="flex-1 flex items-center justify-center gap-1.5 text-[11px] font-medium bg-green-900/30 border border-green-800 text-green-400 rounded-lg py-1.5 hover:bg-green-800/40 transition-colors"
          data-testid={`wa-btn-${item.loanbook_id}`}
        >
          <MessageCircle size={12} /> WhatsApp
        </a>
        <button
          onClick={() => onGestion(item)}
          className="flex-1 flex items-center justify-center gap-1.5 text-[11px] font-medium bg-[#0F2A5C]/60 border border-[#1E3A5F] text-blue-300 rounded-lg py-1.5 hover:bg-[#0F2A5C] transition-colors"
          data-testid={`gestion-btn-${item.loanbook_id}`}
        >
          <Phone size={12} /> Registrar gestión
        </button>
      </div>
    </div>
  );
}

// ── GestionModal ──────────────────────────────────────────────────────────────

function GestionModal({ item, onClose, onSubmit }: {
  item: QueueItem | null;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
}) {
  const [canal, setCanal] = useState("llamada");
  const [resultado, setResultado] = useState("");
  const [nota, setNota] = useState("");
  const [ptpFecha, setPtpFecha] = useState("");
  const [saving, setSaving] = useState(false);
  const needsPtp = resultado.includes("prometió") || resultado === "acuerdo_de_pago_firmado";

  const handleSubmit = async () => {
    if (!resultado) { toast.error("Selecciona un resultado"); return; }
    setSaving(true);
    try {
      await onSubmit({ canal, resultado, nota, ptp_fecha: needsPtp ? ptpFecha : undefined });
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={!!item} onOpenChange={onClose}>
      <DialogContent className="bg-[#0D1E3A] border-[#1E3A5F] text-white max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base text-white">
            Registrar gestión — {item?.cliente_nombre}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-1">
          <div>
            <Label className="text-xs text-slate-400 uppercase tracking-wide">Canal</Label>
            <div className="flex gap-2 mt-1.5 flex-wrap">
              {CANALES.map(c => (
                <button key={c} onClick={() => setCanal(c)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors capitalize ${canal === c ? "bg-blue-600 border-blue-500 text-white" : "bg-[#091529] border-[#1E3A5F] text-slate-400 hover:border-blue-700"}`}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label className="text-xs text-slate-400 uppercase tracking-wide">Resultado</Label>
            <select value={resultado} onChange={e => setResultado(e.target.value)}
              className="mt-1.5 w-full bg-[#091529] border border-[#1E3A5F] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              data-testid="resultado-select">
              <option value="">— Seleccionar resultado —</option>
              {RESULTADOS.map(r => (
                <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          {needsPtp && (
            <div>
              <Label className="text-xs text-slate-400 uppercase tracking-wide">Fecha promesa de pago (PTP)</Label>
              <Input type="date" value={ptpFecha} onChange={e => setPtpFecha(e.target.value)}
                className="mt-1.5 bg-[#091529] border-[#1E3A5F] text-white" data-testid="ptp-fecha-input" />
            </div>
          )}
          <div>
            <Label className="text-xs text-slate-400 uppercase tracking-wide">Nota (opcional)</Label>
            <textarea value={nota} onChange={e => setNota(e.target.value)} rows={2}
              placeholder="Detalles de la gestión..."
              className="mt-1.5 w-full bg-[#091529] border border-[#1E3A5F] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
              data-testid="nota-textarea" />
          </div>
          <div className="flex gap-2 pt-1">
            <Button variant="outline" onClick={onClose} className="flex-1 border-[#1E3A5F] text-slate-400">
              Cancelar
            </Button>
            <Button onClick={handleSubmit} disabled={saving || !resultado}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center gap-2"
              data-testid="gestion-submit-btn">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Phone size={14} />}
              Guardar gestión
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Radar() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [queue, setQueue]     = useState<QueueItem[]>([]);
  const [semana, setSemana]   = useState<SemanaStats | null>(null);
  const [rollRate, setRollRate] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [buscar, setBuscar]   = useState("");
  const [gestionItem, setGestionItem] = useState<QueueItem | null>(null);

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
    } catch (e) {
      toast.error("Error cargando la cola de cobranza");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const filteredQueue = useMemo(() => {
    let q = queue;
    if (activeFilter && activeFilter !== "AL DÍA") {
      q = q.filter(i => i.bucket === activeFilter);
    }
    if (buscar) {
      const b = buscar.toLowerCase();
      q = q.filter(i => i.cliente_nombre.toLowerCase().includes(b) || i.codigo.toLowerCase().includes(b));
    }
    return q;
  }, [queue, activeFilter, buscar]);

  const bucketCounts: Record<string, number> = useMemo(() => {
    const counts: Record<string, number> = {};
    queue.forEach(i => { counts[i.bucket] = (counts[i.bucket] || 0) + 1; });
    return counts;
  }, [queue]);

  const handleGestion = async (data: any) => {
    if (!gestionItem) return;
    try {
      await api.post(`/crm/${gestionItem.loanbook_id}/gestion`, data);
      toast.success("Gestión registrada correctamente");
      setGestionItem(null);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Error registrando la gestión");
      throw e;
    }
  };

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

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {BUCKETS.map(b => {
          const bs = BUCKET_STYLE[b] || { bg: "bg-[#0D1E3A]", text: "text-slate-400", border: "border-[#1E3A5F]", label: b };
          const isActive = activeFilter === b || (b === "AL DÍA" && !activeFilter);
          const count = b === "AL DÍA" ? queue.length : (bucketCounts[b] || 0);
          return (
            <button key={b}
              onClick={() => setActiveFilter(b === "AL DÍA" ? null : (activeFilter === b ? null : b))}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border transition-all ${isActive ? `${bs.bg} ${bs.text} ${bs.border}` : "bg-transparent border-[#1E3A5F] text-slate-500 hover:text-slate-300"}`}
              data-testid={`filter-${b.replace(/\s|Ñ/g, "-").toLowerCase()}`}>
              {b === "AL DÍA" ? b : (BUCKET_STYLE[b]?.label || b)}
              {count > 0 && <span className="bg-white/10 rounded-full px-1.5 py-0.5 text-[10px]">{count}</span>}
            </button>
          );
        })}

        {/* Search */}
        <div className="relative ml-auto">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input type="text" placeholder="Buscar cliente o código..."
            value={buscar} onChange={e => setBuscar(e.target.value)}
            className="bg-[#0D1E3A] border border-[#1E3A5F] text-white text-xs rounded-lg pl-7 pr-3 py-1.5 w-44 focus:outline-none focus:border-blue-500"
            data-testid="radar-search-input" />
        </div>
      </div>

      {/* Queue counter */}
      <p className="text-xs text-slate-500 mb-3">{filteredQueue.length} clientes en cola</p>

      {/* Cards grid */}
      {loading ? (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-40 bg-[#0D1E3A] rounded-xl animate-pulse" />
          ))}
        </div>
      ) : filteredQueue.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Target size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No hay clientes en esta categoría</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredQueue.map(item => (
            <RadarCard key={item.loanbook_id} item={item}
              onGestion={setGestionItem}
              onClick={() => navigate(`/crm/${item.loanbook_id}`)} />
          ))}
        </div>
      )}

      {/* Gestion Modal */}
      <GestionModal item={gestionItem} onClose={() => setGestionItem(null)} onSubmit={handleGestion} />
    </div>
  );
}
