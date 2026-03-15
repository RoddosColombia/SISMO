import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useSharedState } from "../hooks/useSharedState";
import { RadarCard, RadarItem } from "../components/shared/RadarCard";
import { GestionModal } from "../components/shared/GestionModal";
import { RefreshCw, TrendingUp, Users, AlertTriangle, BarChart2, Package, Bell } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CfoSemaforo {
  caja?: string; cartera?: string; ventas?: string; roll_rate?: string; impuestos?: string;
}
interface RadarSemana {
  esperadas?: number; pagadas?: number; pendientes?: number; nuevas_moras?: number;
  valor_esperado?: number; valor_pagado?: number;
}
interface InventarioStats {
  disponibles?: number; vendidas?: number; entregadas?: number; total?: number;
}
interface CfoAlerta { id: string; dimension?: string; mensaje?: string; color?: string; urgencia?: number; }

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n?: number) {
  if (n === undefined || n === null) return "—";
  return `$${Math.round(n).toLocaleString("es-CO")}`;
}

function semaforoEmoji(color?: string) {
  if (color === "VERDE")    return "🟢";
  if (color === "AMARILLO") return "🟡";
  if (color === "ROJO")     return "🔴";
  return "⚪";
}

function semaforoBg(color?: string) {
  if (color === "VERDE")    return "border-emerald-700/60 bg-emerald-900/20";
  if (color === "AMARILLO") return "border-yellow-700/60 bg-yellow-900/20";
  if (color === "ROJO")     return "border-red-700/60 bg-red-900/20";
  return "border-slate-700 bg-slate-800/30";
}

const CFO_LABELS: Record<string, string> = {
  caja: "💰 Caja", cartera: "📊 Cartera", ventas: "💼 Ventas",
  roll_rate: "🔄 Roll Rate", impuestos: "🏛️ Impuestos",
};
const CFO_KEYS = ["caja", "cartera", "ventas", "roll_rate", "impuestos"];

// ── Component ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { api } = useAuth();
  const { data: ph, lastUpdated, refetch: refetchPH } = useSharedState(30_000);

  const [semaforo, setSemaforo]   = useState<CfoSemaforo>({});
  const [semana, setSemana]       = useState<RadarSemana>({});
  const [top5, setTop5]           = useState<RadarItem[]>([]);
  const [inventario, setInventario] = useState<InventarioStats>({});
  const [alertas, setAlertas]     = useState<CfoAlerta[]>([]);
  const [loadingInit, setLoadingInit] = useState(true);
  const [gestionItem, setGestionItem] = useState<RadarItem | null>(null);

  const loadAll = useCallback(async () => {
    try {
      // Fast endpoints first — MongoDB only, set loading=false immediately after
      const [semRes, qRes, invRes, alertRes] = await Promise.allSettled([
        api.get("/radar/semana"),
        api.get("/radar/queue"),
        api.get("/inventario/stats"),
        api.get("/cfo/alertas"),
      ]);
      if (semRes.status === "fulfilled")   setSemana(semRes.value.data);
      if (qRes.status === "fulfilled")     setTop5((qRes.value.data as RadarItem[]).slice(0, 5));
      if (invRes.status === "fulfilled")   setInventario(invRes.value.data);
      if (alertRes.status === "fulfilled") setAlertas((alertRes.value.data as CfoAlerta[]).filter(a => !a["resuelta"]));
    } catch { /* silent */ } finally { setLoadingInit(false); }

    // Slow endpoint (Alegra API) — loads independently, doesn't block render
    try {
      const cfoRes = await api.get("/cfo/semaforo");
      setSemaforo(cfoRes.data);
    } catch { /* Alegra not configured or slow — show empty semaforo */ }
  }, [api]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleRefresh = () => { loadAll(); refetchPH(); };

  // KPI computations
  const cobradoPct = semana.valor_esperado
    ? Math.round((semana.valor_pagado ?? 0) / semana.valor_esperado * 100)
    : 0;
  const tasaMora    = ph?.tasa_mora ?? 0;
  const rollRateNum = semaforo.roll_rate === "ROJO" ? "Alto" : semaforo.roll_rate === "AMARILLO" ? "Medio" : "OK";

  if (loadingInit) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Cargando dashboard…
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard Ejecutivo</h1>
          {lastUpdated && (
            <p className="text-xs text-slate-500 mt-0.5">
              Actualizado: {lastUpdated.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}
              <span className="ml-1 text-slate-600">· auto-refresh 30s</span>
            </p>
          )}
        </div>
        <button
          onClick={handleRefresh}
          data-testid="dashboard-refresh-btn"
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-[#1E3A5F] px-3 py-1.5 rounded-lg hover:bg-[#1E3A5F] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Actualizar
        </button>
      </div>

      {/* Row 1 — Semáforo CFO */}
      <section data-testid="cfo-semaforo-section">
        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Semáforo CFO</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {CFO_KEYS.map(key => {
            const color = (semaforo as Record<string, string>)[key];
            return (
              <div key={key} data-testid={`semaforo-${key}`}
                className={`border rounded-xl px-3 py-2.5 flex items-center gap-2 ${semaforoBg(color)}`}>
                <span className="text-lg leading-none">{semaforoEmoji(color)}</span>
                <div>
                  <p className="text-[11px] text-slate-400 leading-tight">{CFO_LABELS[key]?.slice(2)}</p>
                  <p className="text-xs font-semibold text-white">{color ?? "N/D"}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Row 2 — KPIs de la semana */}
      <section data-testid="kpi-semana-section">
        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">KPIs de la semana</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Cobrado */}
          <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="kpi-cobrado">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span className="text-xs text-slate-400">Cobrado</span>
            </div>
            <p className="text-xl font-bold text-white">{cobradoPct}%</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {fmt(semana.valor_pagado)} de {fmt(semana.valor_esperado)}
            </p>
          </div>
          {/* Activos */}
          <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="kpi-activos">
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-4 h-4 text-blue-400" />
              <span className="text-xs text-slate-400">Créditos activos</span>
            </div>
            <p className="text-xl font-bold text-white">{ph?.activos ?? "—"}</p>
            <p className="text-xs text-slate-500 mt-0.5">{fmt(ph?.cartera_activa)} en cartera</p>
          </div>
          {/* En mora */}
          <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="kpi-mora">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-orange-400" />
              <span className="text-xs text-slate-400">En mora</span>
            </div>
            <p className="text-xl font-bold text-white">{ph?.en_mora ?? "—"}</p>
            <p className="text-xs text-slate-500 mt-0.5">{tasaMora.toFixed(1)}% de la cartera</p>
          </div>
          {/* Roll rate */}
          <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="kpi-rollrate">
            <div className="flex items-center gap-2 mb-2">
              <BarChart2 className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-slate-400">Roll Rate</span>
            </div>
            <p className="text-xl font-bold text-white">{rollRateNum}</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {semana.nuevas_moras ?? 0} nuevas moras · meta &lt;15%
            </p>
          </div>
        </div>
      </section>

      {/* Row 3 — Top 5 RADAR */}
      {top5.length > 0 && (
        <section data-testid="top5-radar-section">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Top 5 RADAR — más urgentes</p>
            <a href="/radar" className="text-xs text-blue-400 hover:text-blue-300">Ver todos →</a>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {top5.map(item => (
              <RadarCard key={item.loanbook_id} item={item} onGestion={setGestionItem} compact />
            ))}
          </div>
        </section>
      )}

      {/* Row 4 — Inventario */}
      <section data-testid="inventario-section">
        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Inventario de Motos</p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Disponibles", value: inventario.disponibles, color: "text-emerald-400", icon: <Package className="w-4 h-4 text-emerald-400" /> },
            { label: "Vendidas",    value: inventario.vendidas,    color: "text-blue-400",    icon: <Package className="w-4 h-4 text-blue-400" /> },
            { label: "Entregadas",  value: inventario.entregadas ?? inventario.total, color: "text-slate-300", icon: <Package className="w-4 h-4 text-slate-400" /> },
          ].map(stat => (
            <div key={stat.label} className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4 text-center" data-testid={`inv-${stat.label.toLowerCase()}`}>
              <div className="flex justify-center mb-1">{stat.icon}</div>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.value ?? "—"}</p>
              <p className="text-xs text-slate-500 mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Row 5 — Alertas CFO */}
      {alertas.length > 0 && (
        <section data-testid="alertas-cfo-section">
          <div className="flex items-center gap-2 mb-2">
            <Bell className="w-4 h-4 text-red-400" />
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Alertas CFO activas</p>
            <span className="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold">{alertas.length}</span>
          </div>
          <div className="space-y-2">
            {alertas.slice(0, 5).map((a, i) => (
              <div key={a.id ?? i}
                className={`border rounded-lg px-3 py-2.5 flex items-start gap-2 ${semaforoBg(a.color)}`}
                data-testid={`alerta-cfo-${i}`}>
                <span>{semaforoEmoji(a.color)}</span>
                <div>
                  <p className="text-xs font-semibold text-white capitalize">{a.dimension?.replace(/_/g, " ")}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{a.mensaje}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Gestion modal */}
      {gestionItem && (
        <GestionModal
          loanbook_id={gestionItem.loanbook_id}
          cliente_nombre={gestionItem.cliente_nombre}
          onClose={() => setGestionItem(null)}
          onSave={() => { setGestionItem(null); loadAll(); }}
        />
      )}
    </div>
  );
}
