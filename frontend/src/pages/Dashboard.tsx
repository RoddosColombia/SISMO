import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useSharedState } from "../hooks/useSharedState";
import { RadarCard, RadarItem } from "../components/shared/RadarCard";
import { GestionModal } from "../components/shared/GestionModal";
import { FiltroFecha, DateRange, loadRange } from "../components/FiltroFecha";
import { RefreshCw, TrendingUp, Users, AlertTriangle, BarChart2, Package, Bell, ShoppingBag, ArrowUp, ArrowDown } from "lucide-react";

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
interface CfoIndicadores {
  creditos_activos?: number; creditos_minimos?: number; recaudo_semanal_base?: number;
  gastos_fijos_semanales?: number; margen_semanal?: number; autosostenible?: boolean;
}
interface VentasKpis {
  total_motos?: number; meta_mensual?: number; pct_meta?: number;
  valor_facturado?: number; cuotas_iniciales_cobradas?: number; cuotas_iniciales_pendientes?: number;
  creditos_nuevos?: number;
}
interface PorModelo { referencia: string; unidades: number; pct: number; }
interface VentaDetalle {
  cliente_nombre: string; referencia: string; vin: string; plan?: string;
  valor_cuota?: number; estado_entrega?: string; fecha_venta?: string; loanbook_codigo?: string;
}
interface VentasData {
  mes?: string; mes_label?: string;
  kpis?: VentasKpis; por_modelo?: PorModelo[]; detalle?: VentaDetalle[];
  comparativo?: { mes_actual: { mes: string; ventas: number }; mes_anterior: { mes: string; ventas: number }; delta: number; tendencia: string };
}

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

// ── Sostenibilidad Widget ──────────────────────────────────────────────────────
function SostenibilidadWidget({ indicadores }: { indicadores: CfoIndicadores }) {
  const activos   = indicadores.creditos_activos  ?? 0;
  const minimos   = indicadores.creditos_minimos  ?? 45;
  const recaudo   = indicadores.recaudo_semanal_base ?? 0;
  const deficit   = indicadores.margen_semanal    ?? 0;
  const pct       = Math.min(100, Math.round((activos / Math.max(1, minimos)) * 100));
  const META_DATE = new Date("2026-06-20T00:00:00");
  const diasRestantes = Math.max(0, Math.floor((META_DATE.getTime() - Date.now()) / 86_400_000));

  const colorClass = pct < 33
    ? { bar: "bg-red-500",    text: "text-red-400",    border: "border-red-900/50   bg-red-950/30"    }
    : pct < 66
    ? { bar: "bg-yellow-400", text: "text-yellow-300", border: "border-yellow-900/50 bg-yellow-950/30" }
    : { bar: "bg-emerald-500",text: "text-emerald-300",border: "border-emerald-900/50 bg-emerald-950/30"};

  const semIcon = pct < 33 ? "🔴" : pct < 66 ? "🟡" : "🟢";

  return (
    <div
      data-testid="sostenibilidad-widget"
      className={`rounded-xl border p-4 ${colorClass.border}`}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
          {semIcon} Sostenibilidad Operativa
        </p>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${pct < 33 ? "bg-red-900/50 text-red-300" : pct < 66 ? "bg-yellow-900/50 text-yellow-300" : "bg-emerald-900/50 text-emerald-300"}`}>
          {pct}%
        </span>
      </div>

      {/* Barra de progreso créditos */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>Créditos activos</span>
          <span className={`font-bold ${colorClass.text}`}>{activos} / {minimos}</span>
        </div>
        <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${colorClass.bar}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-slate-900/50 rounded-lg px-2 py-1.5">
          <p className="text-slate-500">Recaudo/sem</p>
          <p className="font-bold text-white">{fmt(recaudo)}</p>
        </div>
        <div className={`rounded-lg px-2 py-1.5 ${deficit < 0 ? "bg-red-950/40" : "bg-emerald-950/40"}`}>
          <p className="text-slate-500">Déficit/sem</p>
          <p className={`font-bold ${deficit < 0 ? "text-red-400" : "text-emerald-400"}`}>{fmt(deficit)}</p>
        </div>
        <div className="bg-slate-900/50 rounded-lg px-2 py-1.5">
          <p className="text-slate-500">Meta 90 días</p>
          <p className="font-bold text-amber-300">55–60 ventas</p>
        </div>
        <div className={`rounded-lg px-2 py-1.5 ${diasRestantes <= 14 ? "bg-red-950/40" : "bg-slate-900/50"}`}>
          <p className="text-slate-500">Días restantes</p>
          <p className={`font-bold ${diasRestantes <= 14 ? "text-red-400" : "text-white"}`} data-testid="dias-restantes">
            {diasRestantes} días
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Ventas Dashboard Section ──────────────────────────────────────────────────

function fmtCOP(n?: number) {
  if (n === undefined || n === null) return "—";
  return `$${Math.round(n).toLocaleString("es-CO")}`;
}

function estadoBadge(estado?: string) {
  if (estado === "Entregada") return "bg-emerald-100 text-emerald-700";
  if (estado === "Vendida")   return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-600";
}

const VentasDashboard: React.FC<{ api: any; filtro: DateRange }> = ({ api, filtro }) => {
  const [data, setData] = useState<VentasData>({});
  const [loading, setLoading] = useState(true);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [detalleFilter, setDetalleFilter] = useState("Todas");

  useEffect(() => {
    const mes = filtro.desde.slice(0, 7); // YYYY-MM
    setLoading(true);
    api.get("/ventas/dashboard", { params: { mes } })
      .then((r: any) => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filtro, api]);

  const kpis = data.kpis || {};
  const porModelo = data.por_modelo || [];
  const detalle = data.detalle || [];
  const comp = data.comparativo;
  const maxUnidades = Math.max(...porModelo.map(m => m.unidades), 1);

  const detalleFiltered = detalleFilter === "Todas" ? detalle
    : detalleFilter === "Entregadas" ? detalle.filter(d => d.estado_entrega === "Entregada")
    : detalle.filter(d => d.estado_entrega !== "Entregada");

  if (loading) return (
    <div className="flex items-center justify-center py-8 text-slate-500 text-sm">
      <RefreshCw size={14} className="animate-spin mr-2" /> Cargando ventas...
    </div>
  );

  return (
    <div className="space-y-3" data-testid="ventas-dashboard">
      {/* Cards grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Card 1 — Resumen mes */}
        <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4 space-y-3" data-testid="ventas-card-resumen">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Ventas {data.mes_label}</p>
              <div className="flex items-end gap-1.5 mt-1">
                <span className="text-3xl font-bold text-white" data-testid="ventas-total-motos">{kpis.total_motos ?? 0}</span>
                <span className="text-sm text-slate-400 mb-1">/ {kpis.meta_mensual ?? 45} meta</span>
              </div>
            </div>
            <span className={`text-xs font-bold px-2 py-1 rounded-full ${
              (kpis.pct_meta ?? 0) >= 66 ? "bg-emerald-900/50 text-emerald-300"
              : (kpis.pct_meta ?? 0) >= 33 ? "bg-yellow-900/50 text-yellow-300"
              : "bg-slate-800 text-slate-400"
            }`}>
              {kpis.pct_meta ?? 0}%
            </span>
          </div>
          {/* Progress bar */}
          <div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all duration-700"
                style={{ width: `${Math.min(100, kpis.pct_meta ?? 0)}%` }}
              />
            </div>
            <p className="text-[10px] text-slate-500 mt-1">{kpis.pct_meta ?? 0}% hacia la meta mensual</p>
          </div>
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-slate-900/50 rounded-lg px-2 py-1.5">
              <p className="text-slate-500">Valor facturado</p>
              <p className="font-bold text-white">{fmtCOP(kpis.valor_facturado)}</p>
            </div>
            <div className="bg-slate-900/50 rounded-lg px-2 py-1.5">
              <p className="text-slate-500">Cuotas iniciales</p>
              <p className="font-bold text-emerald-400">{fmtCOP(kpis.cuotas_iniciales_cobradas)} cobradas</p>
            </div>
          </div>
        </div>

        {/* Card 2 — Por modelo */}
        <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="ventas-card-modelos">
          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-3">Referencias vendidas</p>
          <div className="space-y-2.5">
            {porModelo.length === 0 && (
              <p className="text-xs text-slate-500 text-center py-4">Sin ventas en este período</p>
            )}
            {porModelo.map((m) => (
              <div key={m.referencia}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-300 truncate max-w-[60%]">{m.referencia}</span>
                  <span className="text-slate-400 font-semibold">{m.unidades} uds · {m.pct}%</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${(m.unidades / maxUnidades) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Card 4 — Comparativo */}
      {comp && (
        <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4" data-testid="ventas-card-comparativo">
          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-3">Comparativo mensual</p>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-[10px] text-slate-500">{comp.mes_anterior.mes}</p>
              <p className="text-2xl font-bold text-slate-400">{comp.mes_anterior.ventas}</p>
            </div>
            <div className="flex-1 flex flex-col items-center">
              <div className={`flex items-center gap-1 text-sm font-bold ${comp.delta > 0 ? "text-emerald-400" : comp.delta < 0 ? "text-red-400" : "text-slate-400"}`}>
                {comp.delta > 0 ? <ArrowUp size={14} /> : comp.delta < 0 ? <ArrowDown size={14} /> : null}
                {comp.delta > 0 ? `+${comp.delta}` : comp.delta}
              </div>
              <div className="w-full h-0.5 bg-slate-700 relative">
                <div className="absolute left-0 top-0 w-full h-full bg-gradient-to-r from-slate-600 to-blue-500" />
              </div>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-slate-500">{comp.mes_actual.mes}</p>
              <p className="text-2xl font-bold text-white">{comp.mes_actual.ventas}</p>
            </div>
          </div>
        </div>
      )}

      {/* Card 3 — Detalle de ventas (expandible) */}
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl" data-testid="ventas-card-detalle">
        <button
          onClick={() => setDetalleAbierto(o => !o)}
          className="w-full flex items-center justify-between px-4 py-3"
        >
          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
            Detalle ventas ({detalle.length})
          </p>
          <RefreshCw size={12} className={`text-slate-500 transition-transform ${detalleAbierto ? "rotate-180" : ""}`} />
        </button>
        {detalleAbierto && (
          <div className="px-4 pb-4 space-y-2">
            {/* Filter tabs */}
            <div className="flex gap-2 mb-2">
              {["Todas", "Entregadas", "Pendientes"].map(f => (
                <button key={f} onClick={() => setDetalleFilter(f)}
                  className={`text-[10px] px-2 py-1 rounded-full font-medium transition-colors ${
                    detalleFilter === f ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
                  }`}>
                  {f}
                </button>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-1.5 text-slate-400 font-medium">Cliente</th>
                    <th className="text-left py-1.5 text-slate-400 font-medium">Referencia</th>
                    <th className="text-left py-1.5 text-slate-400 font-medium hidden sm:table-cell">VIN</th>
                    <th className="text-left py-1.5 text-slate-400 font-medium">Plan</th>
                    <th className="text-right py-1.5 text-slate-400 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {detalleFiltered.length === 0 && (
                    <tr><td colSpan={5} className="py-4 text-center text-slate-500">Sin ventas</td></tr>
                  )}
                  {detalleFiltered.map((v, i) => (
                    <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="py-1.5 text-slate-300 max-w-[120px] truncate">{v.cliente_nombre}</td>
                      <td className="py-1.5 text-slate-400 max-w-[120px] truncate">{v.referencia}</td>
                      <td className="py-1.5 text-slate-500 font-mono text-[10px] hidden sm:table-cell">{v.vin?.slice(-6) || "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.plan || "—"}</td>
                      <td className="py-1.5 text-right">
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${estadoBadge(v.estado_entrega)}`}>
                          {v.estado_entrega || "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { api } = useAuth();
  const { data: ph, lastUpdated, refetch: refetchPH } = useSharedState(30_000);

  const [semaforo, setSemaforo]       = useState<CfoSemaforo>({});
  const [semana, setSemana]           = useState<RadarSemana>({});
  const [top5, setTop5]               = useState<RadarItem[]>([]);
  const [inventario, setInventario]   = useState<InventarioStats>({});
  const [alertas, setAlertas]         = useState<CfoAlerta[]>([]);
  const [indicadores, setIndicadores] = useState<CfoIndicadores>({});
  const [loadingInit, setLoadingInit] = useState(true);
  const [gestionItem, setGestionItem] = useState<RadarItem | null>(null);
  const [smokeStatus, setSmokeStatus] = useState<"ok"|"degradado"|"critico"|null>(null);
  const [ventasFiltro, setVentasFiltro] = useState<DateRange>(() => loadRange("dashboard_ventas"));

  const loadAll = useCallback(async () => {
    try {
      const [semRes, qRes, invRes, alertRes, indRes, smokeRes] = await Promise.allSettled([
        api.get("/radar/semana"),
        api.get("/radar/queue"),
        api.get("/inventario/stats"),
        api.get("/cfo/alertas"),
        api.get("/cfo/indicadores"),
        api.get("/health/smoke"),
      ]);
      if (semRes.status === "fulfilled")   setSemana(semRes.value.data);
      if (qRes.status === "fulfilled")     setTop5((qRes.value.data as RadarItem[]).slice(0, 5));
      if (invRes.status === "fulfilled")   setInventario(invRes.value.data);
      if (alertRes.status === "fulfilled") setAlertas((alertRes.value.data as CfoAlerta[]).filter(a => !a["resuelta"]));
      if (indRes.status === "fulfilled")   setIndicadores(indRes.value.data ?? {});
      if (smokeRes.status === "fulfilled") setSmokeStatus(smokeRes.value.data?.status ?? null);
    } catch { /* silent */ } finally { setLoadingInit(false); }

    try {
      const cfoRes = await api.get("/cfo/semaforo");
      setSemaforo(cfoRes.data);
    } catch { /* Alegra not configured or slow — show empty semaforo */ }
  }, [api]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleRefresh = () => { loadAll(); refetchPH(); };

  const cobradoPct = semana.valor_esperado
    ? Math.round((semana.valor_pagado ?? 0) / semana.valor_esperado * 100)
    : 0;
  const tasaMora    = ph?.tasa_mora ?? 0;
  const rollRateNum = ph?.activos
    ? `${Math.round((semana.nuevas_moras ?? 0) / ph.activos * 100)}%`
    : "—";

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
          className="flex items-center gap-2 text-xs text-slate-400 hover:text-white border border-[#1E3A5F] px-3 py-1.5 rounded-lg hover:bg-[#1E3A5F] transition-colors"
        >
          {smokeStatus && (
            <span
              data-testid="system-status-badge"
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                smokeStatus === "ok"       ? "bg-emerald-400" :
                smokeStatus === "degradado"? "bg-yellow-400 animate-pulse" :
                                             "bg-red-500 animate-pulse"
              }`}
              title={`Sistema: ${smokeStatus.toUpperCase()}`}
            />
          )}
          <RefreshCw className="w-3.5 h-3.5" /> Actualizar
        </button>
      </div>

      {/* Widget Sostenibilidad — siempre visible */}
      <SostenibilidadWidget indicadores={indicadores} />

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

      {/* Row 5 — Dashboard de Ventas */}
      <section data-testid="ventas-section">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <ShoppingBag className="w-4 h-4 text-blue-400" />
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Dashboard de Ventas</p>
          </div>
          <FiltroFecha
            moduleKey="dashboard_ventas"
            onChange={setVentasFiltro}
            compact
          />
        </div>
        <VentasDashboard api={api} filtro={ventasFiltro} />
      </section>

      {/* Row 6 — Alertas CFO */}
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
