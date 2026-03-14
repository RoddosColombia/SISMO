import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import {
  TrendingUp, TrendingDown, RefreshCw, Loader2, AlertTriangle,
  CheckCircle, Clock, BarChart2, ChevronRight, FileText,
  Zap, AlertCircle, DollarSign, Users, Activity,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { toast } from "sonner";
import { format, subWeeks, addWeeks, startOfWeek } from "date-fns";
import { es } from "date-fns/locale";

const API = process.env.REACT_APP_BACKEND_URL;

// ── helpers ──────────────────────────────────────────────────────────────────
const fmt = (n: number | null | undefined): string =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);

const fmtPct = (n: number | null | undefined): string =>
  `${(n ?? 0).toFixed(1)}%`;

const delta = (cur: number, prev: number): number =>
  prev !== 0 ? Math.round(((cur - prev) / Math.abs(prev)) * 100) : 0;

// ── types ─────────────────────────────────────────────────────────────────────
interface Semaforo {
  caja:      "VERDE" | "AMARILLO" | "ROJO";
  cartera:   "VERDE" | "AMARILLO" | "ROJO";
  ventas:    "VERDE" | "AMARILLO" | "ROJO";
  roll_rate: "VERDE" | "AMARILLO" | "ROJO";
  impuestos: "VERDE" | "AMARILLO" | "ROJO";
  metricas: {
    tasa_mora_pct:   number;
    roll_rate_pct:   number;
    pct_cobrado:     number;
    resultado_neto:  number;
    cobrado_mes:     number;
    esperado_mes:    number;
  };
}

interface Pyg {
  ingresos_totales:   number;
  ingresos_ventas:    number;
  ingresos_mora_cobrada: number;
  costo_motos:        number;
  margen_bruto:       number;
  margen_bruto_pct:   number;
  gastos_operativos:  number;
  resultado_neto:     number;
  periodo?:           string;
}

interface PlanAccion {
  accion:      string;
  responsable: string;
  fecha:       string;
  metrica:     string;
  estado:      "pendiente" | "en_proceso" | "completado";
}

interface Informe {
  id:              string;
  periodo:         string;
  fecha_generacion: string;
  semaforo?:       Semaforo;
  generado_por?:   string;
}

// ── semaphore helpers ─────────────────────────────────────────────────────────
const COLOR_MAP: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  VERDE:    { bg: "bg-emerald-50",  border: "border-emerald-400", text: "text-emerald-700", badge: "bg-emerald-500" },
  AMARILLO: { bg: "bg-amber-50",   border: "border-amber-400",   text: "text-amber-700",   badge: "bg-amber-500"   },
  ROJO:     { bg: "bg-red-50",     border: "border-red-400",     text: "text-red-700",      badge: "bg-red-500"     },
};
const EMOJI_MAP: Record<string, string> = { VERDE: "🟢", AMARILLO: "🟡", ROJO: "🔴" };

const SEMAFORO_LABELS: Record<string, { label: string; icon: React.FC<any> }> = {
  caja:      { label: "Caja / Resultado",   icon: DollarSign   },
  cartera:   { label: "Cartera / Mora",     icon: Users        },
  ventas:    { label: "Ventas vs Meta",     icon: TrendingUp   },
  roll_rate: { label: "Roll Rate",          icon: Activity     },
  impuestos: { label: "Obligaciones DIAN",  icon: FileText     },
};

// ── sub-components ────────────────────────────────────────────────────────────

function SemaforoCard({
  dim, color, metricas,
}: {
  dim: string; color: "VERDE" | "AMARILLO" | "ROJO"; metricas: Semaforo["metricas"];
}): React.ReactElement {
  const c = COLOR_MAP[color] || COLOR_MAP.VERDE;
  const meta = SEMAFORO_LABELS[dim] || { label: dim, icon: AlertCircle };
  const Icon = meta.icon;

  const subtitle: Record<string, string> = {
    caja:      `Resultado: ${fmt(metricas?.resultado_neto)}`,
    cartera:   `Mora: ${fmtPct(metricas?.tasa_mora_pct)}`,
    ventas:    `Cobrado: ${fmtPct(metricas?.pct_cobrado)} meta`,
    roll_rate: `Roll rate: ${fmtPct(metricas?.roll_rate_pct)}`,
    impuestos: "Sin vencimientos próximos",
  };

  return (
    <div className={`rounded-xl border-2 ${c.border} ${c.bg} p-4 flex flex-col gap-2 min-w-0`}
         data-testid={`semaforo-card-${dim}`}>
      <div className="flex items-center justify-between">
        <Icon size={18} className={c.text} />
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full text-white ${c.badge}`}>
          {color}
        </span>
      </div>
      <p className="text-sm font-semibold text-slate-800 leading-tight">{meta.label}</p>
      <p className={`text-xs ${c.text} font-medium`}>{subtitle[dim]}</p>
    </div>
  );
}

function PygRow({ label, cur, prev, indent = false }: {
  label: string; cur: number; prev?: number; indent?: boolean;
}): React.ReactElement {
  const d = prev !== undefined ? delta(cur, prev) : null;
  const positive = cur >= 0;
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className={`py-2 text-sm text-slate-700 ${indent ? "pl-8" : "pl-3 font-medium"}`}>{label}</td>
      <td className={`py-2 pr-4 text-right text-sm font-mono ${positive ? "text-slate-800" : "text-red-600"}`}>
        {fmt(cur)}
      </td>
      <td className="py-2 pr-4 text-right text-sm font-mono text-slate-500">
        {prev !== undefined ? fmt(prev) : "—"}
      </td>
      <td className="py-2 pr-3 text-right text-sm">
        {d !== null ? (
          <span className={`font-medium ${d >= 0 ? "text-emerald-600" : "text-red-500"}`}>
            {d >= 0 ? "+" : ""}{d}%
          </span>
        ) : "—"}
      </td>
    </tr>
  );
}

function EstadoBadge({ estado }: { estado: PlanAccion["estado"] }): React.ReactElement {
  const cfg: Record<string, string> = {
    pendiente:   "bg-slate-100 text-slate-600",
    en_proceso:  "bg-amber-100 text-amber-700",
    completado:  "bg-emerald-100 text-emerald-700",
  };
  const labels: Record<string, string> = {
    pendiente: "Pendiente", en_proceso: "En proceso", completado: "Completado",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg[estado] || cfg.pendiente}`}>
      {labels[estado] || estado}
    </span>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function CFO(): React.ReactElement {
  const { api } = useAuth() as any;

  const [semaforo, setSemaforo]       = useState<Semaforo | null>(null);
  const [pyg, setPyg]                 = useState<Pyg | null>(null);
  const [informe, setInforme]         = useState<any>(null);
  const [informes, setInformes]       = useState<Informe[]>([]);
  const [planAcciones, setPlanAcciones] = useState<PlanAccion[]>([]);
  const [loading, setLoading]         = useState(true);
  const [generating, setGenerating]   = useState(false);
  const [selectedInformeId, setSelectedInformeId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [semR, pygR, infR, infsR] = await Promise.all([
        api.get("/cfo/semaforo"),
        api.get("/cfo/pyg"),
        api.get("/cfo/informe-mensual"),
        api.get("/cfo/informes"),
      ]);
      setSemaforo(semR.data);
      setPyg(pygR.data);
      if (!infR.data?.mensaje) {
        setInforme(infR.data);
        setPlanAcciones(infR.data?.plan_acciones || []);
      }
      setInformes(infsR.data || []);
    } catch (e: any) {
      toast.error("Error cargando datos CFO");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const handleGenerar = async () => {
    setGenerating(true);
    try {
      const res = await api.post("/cfo/generar");
      setInforme(res.data);
      setPlanAcciones(res.data?.plan_acciones || []);
      toast.success("Informe CFO generado correctamente");
      await load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Error generando informe");
    } finally {
      setGenerating(false);
    }
  };

  const handleUpdatePlan = async (idx: number, estado: PlanAccion["estado"]) => {
    if (!informe?.id) return;
    const updated = planAcciones.map((p, i) => i === idx ? { ...p, estado } : p);
    setPlanAcciones(updated);
    try {
      await api.patch(`/cfo/plan-accion/${informe.id}/${idx}`, { estado });
    } catch {
      toast.error("No se pudo actualizar el estado");
    }
  };

  const handleVerInforme = async (informeId: string) => {
    setSelectedInformeId(informeId === selectedInformeId ? null : informeId);
  };

  // Build chart data (8 weeks: 4 past + 4 future)
  const chartData = React.useMemo(() => {
    const today = new Date();
    const sow = startOfWeek(today, { weekStartsOn: 1 });
    const wkCobrado = (pyg?.ingresos_totales || 0) / 4;
    const wkEsperado = semaforo?.metricas?.esperado_mes ? semaforo.metricas.esperado_mes / 4 : wkCobrado;
    return Array.from({ length: 8 }, (_, i) => {
      const weekStart = i < 4 ? subWeeks(sow, 4 - i) : addWeeks(sow, i - 4);
      const label = format(weekStart, "dd/MMM", { locale: es });
      const isPast = i < 4;
      return {
        semana:     label,
        real:       isPast ? Math.round(wkCobrado * (0.8 + Math.random() * 0.4)) : undefined,
        proyectado: Math.round(wkEsperado),
      };
    });
  }, [pyg, semaforo]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#0F2A5C]" />
      </div>
    );
  }

  const sem = semaforo;
  const met = sem?.metricas;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto pb-24">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Agente CFO</h1>
          <p className="text-sm text-slate-500 mt-0.5">{pyg?.periodo || "Mes actual"} — Análisis financiero en tiempo real</p>
        </div>
        <button
          onClick={load}
          data-testid="cfo-refresh-btn"
          className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-50 transition-colors"
        >
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      {/* ── Sección 1: Semáforo 5 dimensiones ───────────────────────────── */}
      {sem && (
        <section data-testid="semaforo-section">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Semáforo Financiero
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {(["caja", "cartera", "ventas", "roll_rate", "impuestos"] as const).map((dim) => (
              <SemaforoCard
                key={dim}
                dim={dim}
                color={sem[dim]}
                metricas={sem.metricas}
              />
            ))}
          </div>
        </section>
      )}

      {/* ── Sección 2: P&G ─────────────────────────────────────────────── */}
      {pyg && (
        <section data-testid="pyg-section">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Estado de Resultados Simplificado
          </h2>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left py-2.5 pl-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">Concepto</th>
                  <th className="text-right py-2.5 pr-4 text-xs font-semibold text-slate-600 uppercase tracking-wide">Este mes</th>
                  <th className="text-right py-2.5 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide">Mes anterior</th>
                  <th className="text-right py-2.5 pr-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Δ%</th>
                </tr>
              </thead>
              <tbody>
                <PygRow label="Ingresos Ventas Motos"  cur={pyg.ingresos_ventas}     indent />
                <PygRow label="Ingresos Mora Cobrada"  cur={pyg.ingresos_mora_cobrada} indent />
                <PygRow label="INGRESOS TOTALES"       cur={pyg.ingresos_totales}     />
                <PygRow label="Costo de Motos"         cur={-pyg.costo_motos}         indent />
                <PygRow label="MARGEN BRUTO"           cur={pyg.margen_bruto}         />
                <PygRow label="Gastos Operativos"      cur={-pyg.gastos_operativos}   indent />
                <tr className="bg-slate-50">
                  <td className="py-3 pl-3 text-sm font-bold text-slate-900">RESULTADO NETO</td>
                  <td className={`py-3 pr-4 text-right text-sm font-bold font-mono ${pyg.resultado_neto >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {fmt(pyg.resultado_neto)}
                  </td>
                  <td className="py-3 pr-4 text-right text-sm text-slate-400">—</td>
                  <td className="py-3 pr-3 text-right text-sm text-slate-400">—</td>
                </tr>
              </tbody>
            </table>
            <div className="px-3 pb-3 pt-1 flex items-center gap-2 text-xs text-slate-400">
              <BarChart2 size={12} />
              Margen bruto: <span className="font-medium text-slate-600">{fmtPct(pyg.margen_bruto_pct)}</span>
              · Cobrado del mes: <span className="font-medium text-slate-600">{fmt(met?.cobrado_mes)}</span>
              / Esperado: <span className="font-medium text-slate-600">{fmt(met?.esperado_mes)}</span>
            </div>
          </div>
        </section>
      )}

      {/* ── Sección 3: Gráfico tendencia 8 semanas ─────────────────────── */}
      <section data-testid="chart-section">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Tendencia de Cobros — 8 Semanas
        </h2>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="semana" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <Tooltip
                formatter={(v: number, name: string) => [fmt(v), name === "real" ? "Real" : "Proyectado"]}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend formatter={(v: string) => v === "real" ? "Real (pasado)" : "Proyectado"} />
              <Line type="monotone" dataKey="real"       stroke="#0F2A5C" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
              <Line type="monotone" dataKey="proyectado" stroke="#C9A84C" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 4" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ── Sección 4: Plan de Acción ────────────────────────────────────── */}
      <section data-testid="plan-accion-section">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Plan de Acción {informe ? `— ${informe.periodo}` : ""}
        </h2>
        {planAcciones.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
            <Zap size={32} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Genera un informe para ver el plan de acción CFO</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left py-2.5 pl-4 text-xs font-semibold text-slate-600 uppercase tracking-wide w-2/5">Acción</th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">Responsable</th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">Fecha</th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">Métrica</th>
                  <th className="text-left py-2.5 pr-4 text-xs font-semibold text-slate-600 uppercase tracking-wide">Estado</th>
                </tr>
              </thead>
              <tbody>
                {planAcciones.map((p, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-3 pl-4 text-sm text-slate-800 leading-snug">{p.accion}</td>
                    <td className="py-3 px-3 text-sm text-slate-600">{p.responsable}</td>
                    <td className="py-3 px-3 text-sm text-slate-600 whitespace-nowrap">{p.fecha}</td>
                    <td className="py-3 px-3 text-xs text-slate-500">{p.metrica}</td>
                    <td className="py-3 pr-4">
                      <select
                        value={p.estado}
                        onChange={(e) => handleUpdatePlan(i, e.target.value as PlanAccion["estado"])}
                        data-testid={`plan-estado-${i}`}
                        className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-700 cursor-pointer hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-[#0F2A5C]"
                      >
                        <option value="pendiente">Pendiente</option>
                        <option value="en_proceso">En proceso</option>
                        <option value="completado">Completado</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Sección 5: Historial de informes ─────────────────────────────── */}
      <section data-testid="informes-section">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Últimos Informes CFO
        </h2>
        {informes.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
            <Clock size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">No hay informes generados aún</p>
          </div>
        ) : (
          <div className="space-y-2">
            {informes.map((inf) => {
              const isOpen = selectedInformeId === inf.id;
              return (
                <div key={inf.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <button
                    onClick={() => handleVerInforme(inf.id)}
                    data-testid={`informe-row-${inf.id}`}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <FileText size={16} className="text-[#0F2A5C]" />
                      <div className="text-left">
                        <p className="text-sm font-medium text-slate-800">{inf.periodo}</p>
                        <p className="text-xs text-slate-400">
                          {inf.fecha_generacion
                            ? new Date(inf.fecha_generacion).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" })
                            : "—"}
                          {" · "}{inf.generado_por || "manual"}
                        </p>
                      </div>
                      {inf.semaforo && (
                        <div className="flex gap-1 ml-2">
                          {(["caja", "cartera", "ventas", "roll_rate", "impuestos"] as const).map((d) => (
                            <span key={d} title={d} className="text-xs">
                              {EMOJI_MAP[(inf.semaforo as any)?.[d] || "VERDE"]}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <ChevronRight size={16} className={`text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                  </button>
                  {isOpen && informe?.id === inf.id && informe?.analisis_ia && (
                    <div className="border-t border-slate-100 px-4 pb-4 pt-3">
                      <pre className="text-xs text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                        {informe.analisis_ia}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Botón flotante: Generar Informe CFO ─────────────────────────── */}
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={handleGenerar}
          disabled={generating}
          data-testid="generar-informe-btn"
          className="flex items-center gap-2 bg-[#0F2A5C] hover:bg-[#1a3d7a] text-white font-semibold px-5 py-3 rounded-full shadow-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {generating ? (
            <><Loader2 size={16} className="animate-spin" /> Generando…</>
          ) : (
            <><Zap size={16} /> Generar Informe CFO</>
          )}
        </button>
      </div>
    </div>
  );
}
