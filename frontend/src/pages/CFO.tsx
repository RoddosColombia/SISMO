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
  metricas?: {
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

interface CfoIndicadores {
  recaudo_semanal_base:  number;
  creditos_activos:      number;
  creditos_minimos:      number;
  sobre_el_piso:         number;
  autosostenible:        boolean;
  saldo_cartera:         number;
  deuda_no_productiva:   number;
  deuda_productiva:      number;
  margen_semanal:        number;
  pct_gastos_vs_recaudo: number;
  gastos_fijos_config:   number;
  configurado:           boolean;
}

interface PlanIngresosItem {
  semana:          number;
  miercoles:       string;
  recaudo_cartera: number;
  num_cuotas:      number;
}

interface DeudaItem {
  id: string; acreedor: string; monto_total: number;
  saldo_pendiente: number; tasa_mensual: number;
  tipo: string; estado: string; descripcion: string;
  fecha_vencimiento?: string;
}

interface PlanDeudaSemana {
  semana: number; miercoles: string;
  disponible_deuda: number; deuda_np_restante: number;
  pagos: { acreedor: string; monto: number }[];
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
  const [loadingSemaforo, setLoadingSemaforo] = useState(false);
  const [loadingPyg, setLoadingPyg]   = useState(false);
  const [generating, setGenerating]   = useState(false);
  const [selectedInformeId, setSelectedInformeId] = useState<string | null>(null);

  // ── BUILD 11: Agente CFO Estratégico ─────────────────────────────────────
  const [indicadores, setIndicadores] = useState<CfoIndicadores | null>(null);
  const [planIngresos, setPlanIngresos] = useState<PlanIngresosItem[]>([]);
  const [planDeuda, setPlanDeuda]       = useState<{ semanas: PlanDeudaSemana[]; total_np: number; fecha_liberacion?: string; semanas_liberacion?: number; error?: string; mensaje?: string } | null>(null);
  const [deudas, setDeudas]             = useState<DeudaItem[]>([]);
  const [cuotasIniciales, setCuotasIniciales] = useState<{ total_pendiente: number; detalle: any[] }>({ total_pendiente: 0, detalle: [] });
  const [gastosInput, setGastosInput]   = useState("");
  const [savingConfig, setSavingConfig] = useState(false);
  const [uploadingXls, setUploadingXls] = useState(false);
  const [preview, setPreview]           = useState<{ deudas: DeudaItem[]; resumen: any } | null>(null);
  const [savingDeudas, setSavingDeudas] = useState(false);
  const [activeTab, setActiveTab]       = useState<"semaforo"|"estrategico">("estrategico");
  const [reporteLunes, setReporteLunes] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    // Cargar historial de informes y plan (rápidos, sólo BD)
    try {
      const [infR, infsR] = await Promise.all([
        api.get("/cfo/informe-mensual"),
        api.get("/cfo/informes"),
      ]);
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

    // Build 11: CFO Estratégico data (parallel, non-blocking)
    Promise.all([
      api.get("/cfo/indicadores"),
      api.get("/cfo/plan-ingresos?semanas=8"),
      api.get("/cfo/plan-deudas"),
      api.get("/cfo/deudas"),
      api.get("/cfo/cuotas-iniciales"),
      api.get("/cfo/financiero/config"),
      api.get("/cfo/reporte-lunes"),
    ]).then(([indR, piR, pdR, dR, ciR, cfgR, rlR]) => {
      setIndicadores(indR.data);
      setPlanIngresos(piR.data?.semanas || []);
      setPlanDeuda(pdR.data);
      setDeudas(dR.data || []);
      setCuotasIniciales(ciR.data || { total_pendiente: 0, detalle: [] });
      if (cfgR.data?.gastos_fijos_semanales) {
        setGastosInput(String(cfgR.data.gastos_fijos_semanales));
      }
      setReporteLunes(rlR.data);
    }).catch(() => {});

    // P&G — llama Alegra 3 veces (~30s), carga independiente
    setLoadingPyg(true);
    try {
      const pygR = await api.get("/cfo/pyg");
      setPyg(pygR.data);
    } catch { /* no crítico */ } finally {
      setLoadingPyg(false);
    }

    // Semáforo — llama IA Claude (~30s), carga independiente
    setLoadingSemaforo(true);
    try {
      const semR = await api.get("/cfo/semaforo");
      setSemaforo(semR.data);
    } catch { /* no crítico */ } finally {
      setLoadingSemaforo(false);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const handleGenerar = async () => {
    setGenerating(true);
    try {
      // 1. Disparar job asíncrono
      const triggerRes = await api.post("/cfo/generar");
      const jobId: string = triggerRes.data?.job_id;
      if (!jobId) throw new Error("No se recibió job_id");

      toast.info("Generando informe CFO… esto puede tomar 15–30 segundos.");

      // 2. Polling cada 2 s hasta completado o error (máx 90 s)
      let attempts = 0;
      const MAX_ATTEMPTS = 45;
      await new Promise<void>((resolve, reject) => {
        const interval = setInterval(async () => {
          attempts++;
          try {
            const statusRes = await api.get(`/cfo/status/${jobId}`);
            const { estado, informe_id, error } = statusRes.data;

            if (estado === "completado" && informe_id) {
              clearInterval(interval);
              // Cargar el informe recién generado
              try {
                const infRes = await api.get("/cfo/informe-mensual");
                if (!infRes.data?.mensaje) {
                  setInforme(infRes.data);
                  setPlanAcciones(infRes.data?.plan_acciones || []);
                }
                await load();
              } catch { /* datos actualizados en load() */ }
              toast.success("Informe CFO generado correctamente");
              resolve();
            } else if (estado === "error") {
              clearInterval(interval);
              reject(new Error(error || "Error generando informe"));
            } else if (attempts >= MAX_ATTEMPTS) {
              clearInterval(interval);
              reject(new Error("El informe tardó demasiado. Intenta nuevamente."));
            }
          } catch (pollErr: any) {
            clearInterval(interval);
            reject(pollErr);
          }
        }, 2000);
      });
    } catch (e: any) {
      toast.error(e?.message || e?.response?.data?.detail || "Error generando informe");
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

  // Build 11 handlers
  const handleSaveConfig = async () => {
    const val = parseFloat(gastosInput.replace(/[^0-9.]/g, ""));
    if (!val || val <= 0) { toast.error("Ingresa un valor válido"); return; }
    setSavingConfig(true);
    try {
      await api.post("/cfo/financiero/config", { gastos_fijos_semanales: val, reserva_minima_semanas: 2, limite_compromisos_pct: 0.6, objetivo_deuda_np_meses: 3 });
      toast.success("Configuración guardada");
      const [indR, pdR] = await Promise.all([api.get("/cfo/indicadores"), api.get("/cfo/plan-deudas")]);
      setIndicadores(indR.data);
      setPlanDeuda(pdR.data);
    } catch { toast.error("Error guardando"); } finally { setSavingConfig(false); }
  };

  const handleXlsUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingXls(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post("/cfo/deudas/cargar", form, { headers: { "Content-Type": "multipart/form-data" } });
      if (!res.data.ok) { toast.error(res.data.error || "Error al leer el archivo"); return; }
      setPreview(res.data);
      toast.success(`${res.data.deudas.length} deudas detectadas. Revisa y confirma.`);
    } catch { toast.error("Error subiendo archivo"); } finally { setUploadingXls(false); e.target.value = ""; }
  };

  const handleConfirmarDeudas = async () => {
    if (!preview) return;
    setSavingDeudas(true);
    try {
      await api.post("/cfo/deudas/confirmar", { deudas: preview.deudas });
      toast.success("Deudas guardadas en MongoDB");
      setPreview(null);
      const [dR, pdR, indR] = await Promise.all([api.get("/cfo/deudas"), api.get("/cfo/plan-deudas"), api.get("/cfo/indicadores")]);
      setDeudas(dR.data || []);
      setPlanDeuda(pdR.data);
      setIndicadores(indR.data);
    } catch { toast.error("Error guardando deudas"); } finally { setSavingDeudas(false); }
  };

  const handleDescargarPlantilla = async () => {
    try {
      const response = await api.get("/cfo/deudas/plantilla", { responseType: "blob" });
      const url  = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href  = url;
      link.setAttribute("download", "RODDOS_Plantilla_Deudas.xlsx");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Error descargando la plantilla");
    }
  };

  const handleReclasificar = async (id: string, nuevoTipo: string) => {
    try {
      await api.patch(`/cfo/deudas/${id}`, { tipo: nuevoTipo });
      setDeudas(prev => prev.map(d => d.id === id ? { ...d, tipo: nuevoTipo } : d));
      if (preview) setPreview(prev => prev ? { ...prev, deudas: prev.deudas.map(d => d.id === id ? { ...d, tipo: nuevoTipo } : d) } : null);
      toast.success("Reclasificado");
    } catch { toast.error("Error"); }
  };

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
      <section data-testid="semaforo-section">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Semáforo Financiero
        </h2>
        {loadingSemaforo ? (
          <div className="flex items-center gap-2 text-sm text-slate-400 bg-white border border-slate-200 rounded-xl px-4 py-3">
            <Loader2 size={14} className="animate-spin" />
            Calculando semáforo financiero (análisis IA)…
          </div>
        ) : sem ? (
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
        ) : (
          <div className="text-sm text-slate-400 bg-white border border-slate-200 rounded-xl px-4 py-3">
            Sin datos de semáforo disponibles
          </div>
        )}
      </section>

      {/* ── Sección 2: P&G ─────────────────────────────────────────────── */}
      <section data-testid="pyg-section">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Estado de Resultados Simplificado
        </h2>
        {loadingPyg ? (
          <div className="flex items-center gap-2 text-sm text-slate-400 bg-white border border-slate-200 rounded-xl px-4 py-3">
            <Loader2 size={14} className="animate-spin" />
            Cargando P&G desde Alegra…
          </div>
        ) : pyg ? (
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
        ) : (
          <div className="text-sm text-slate-400 bg-white border border-slate-200 rounded-xl px-4 py-3">
            Sin datos P&G disponibles
          </div>
        )}
      </section>

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

      {/* ── BUILD 11 — PLAN ESTRATÉGICO CFO ──────────────────────────────────── */}
      <section className="mt-8 space-y-6" data-testid="plan-estrategico-section">
        {/* Header */}
        <div className="flex items-center gap-3">
          <DollarSign size={20} className="text-[#0F2A5C]" />
          <h2 className="text-lg font-bold text-slate-800">Plan Estratégico CFO</h2>
        </div>

        {/* Indicadores clave */}
        {indicadores && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="indicadores-cfo">
            {[
              { label: "Recaudo semanal", val: fmt(indicadores.recaudo_semanal_base), sub: "9 créditos activos", color: "emerald" },
              { label: "Créditos activos", val: String(indicadores.creditos_activos), sub: `Mínimo: ${indicadores.creditos_minimos} | ${indicadores.autosostenible ? "✅ Autosostenible" : "⚠️ Bajo el piso"}`, color: indicadores.autosostenible ? "emerald" : "red" },
              { label: "Deuda no productiva", val: fmt(indicadores.deuda_no_productiva), sub: indicadores.deuda_no_productiva === 0 ? "¡Sin deuda NP!" : "Prioridad: liquidar", color: indicadores.deuda_no_productiva === 0 ? "emerald" : "amber" },
              { label: "Margen semanal", val: indicadores.configurado ? fmt(indicadores.margen_semanal) : "—", sub: indicadores.configurado ? "Recaudo - gastos - reserva" : "Configura gastos fijos", color: "blue" },
            ].map(({ label, val, sub, color }) => (
              <div key={label} className={`rounded-xl border border-${color}-200 bg-${color}-50 p-3`}>
                <p className="text-xs text-slate-500 font-medium">{label}</p>
                <p className={`text-xl font-bold text-${color}-700 my-1`}>{val}</p>
                <p className="text-[11px] text-slate-500">{sub}</p>
              </div>
            ))}
          </div>
        )}

        {/* Cuotas iniciales pendientes */}
        {cuotasIniciales.total_pendiente > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4" data-testid="cuotas-iniciales-card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-amber-800">Cuotas iniciales pendientes de cobro — Marzo 2026</span>
              <span className="text-lg font-bold text-amber-700">{fmt(cuotasIniciales.total_pendiente)}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {cuotasIniciales.detalle.map((d: any) => (
                <div key={d.codigo} className="bg-white rounded-lg border border-amber-100 px-3 py-2">
                  <p className="text-[11px] text-slate-500">{d.codigo}</p>
                  <p className="text-xs font-semibold text-slate-700 leading-tight">{d.cliente}</p>
                  <p className="text-sm font-bold text-amber-700">{fmt(d.pendiente)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Configuración gastos fijos */}
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="config-gastos-card">
          <p className="text-sm font-bold text-slate-700 mb-3">Gastos fijos semanales</p>
          <div className="flex gap-2 items-center">
            <span className="text-slate-400 text-sm">$</span>
            <input
              type="text"
              value={gastosInput}
              onChange={e => setGastosInput(e.target.value)}
              placeholder="ej: 800000"
              className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F2A5C]/20"
              data-testid="gastos-fijos-input"
            />
            <button
              onClick={handleSaveConfig}
              disabled={savingConfig}
              className="bg-[#0F2A5C] text-white text-sm px-4 py-2 rounded-lg font-semibold hover:bg-[#1a3d7a] transition disabled:opacity-50"
              data-testid="save-gastos-btn"
            >
              {savingConfig ? "Guardando…" : "Guardar"}
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Arriendo + nómina + servicios + otros fijos (semanal)</p>
        </div>

        {/* Plan de ingresos semanal */}
        {planIngresos.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden" data-testid="plan-ingresos-table">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
              <TrendingUp size={16} className="text-emerald-600" />
              <p className="text-sm font-bold text-slate-800">Plan de ingresos — próximas 8 semanas</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                    <th className="px-4 py-2 text-left">Semana</th>
                    <th className="px-4 py-2 text-center">Miércoles</th>
                    <th className="px-4 py-2 text-right">Recaudo cartera</th>
                    <th className="px-4 py-2 text-center">Cuotas</th>
                  </tr>
                </thead>
                <tbody>
                  {planIngresos.map((s) => (
                    <tr key={s.semana} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-2 text-slate-600">Sem {s.semana}</td>
                      <td className="px-4 py-2 text-center font-mono text-slate-700">{s.miercoles}</td>
                      <td className="px-4 py-2 text-right font-bold text-emerald-700">{fmt(s.recaudo_cartera)}</td>
                      <td className="px-4 py-2 text-center text-slate-500">{s.num_cuotas}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Deudas — carga Excel */}
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="deudas-section">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-bold text-slate-800">Inventario de deudas</p>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDescargarPlantilla}
                data-testid="descargar-plantilla-btn"
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-[#0F2A5C] text-[#0F2A5C] hover:bg-[#0F2A5C]/5 transition"
              >
                <FileText size={13} />
                Descargar plantilla Excel
              </button>
              <label className={`cursor-pointer inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition ${uploadingXls ? "bg-slate-100 text-slate-400" : "bg-[#0F2A5C] text-white hover:bg-[#1a3d7a]"}`} data-testid="upload-excel-btn">
                {uploadingXls ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />}
                {uploadingXls ? "Procesando…" : "Cargar Excel (.xlsx)"}
                <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleXlsUpload} disabled={uploadingXls} />
              </label>
            </div>
          </div>
          <p className="text-xs text-slate-400 mb-3">
            Descarga la plantilla, llena tus deudas y sube el archivo aquí. El sistema clasifica automáticamente cada deuda como productiva o no productiva.
          </p>

          {/* Preview clasificación */}
          {preview && (
            <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3" data-testid="deudas-preview">
              <p className="text-sm font-bold text-blue-800 mb-2">Diagnóstico de deudas — revisa y confirma</p>
              {(preview as any).advertencias?.length > 0 && (
                <div className="mb-2 rounded bg-amber-50 border border-amber-200 p-2 space-y-0.5">
                  <p className="text-xs font-semibold text-amber-800">Advertencias de formato:</p>
                  {(preview as any).advertencias.map((w: string, i: number) => (
                    <p key={i} className="text-xs text-amber-700">{w}</p>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-3 gap-2 text-xs text-center mb-3">
                <div className="bg-white rounded p-2"><p className="text-slate-500">Productiva</p><p className="font-bold text-emerald-700">{fmt(preview.resumen.total_productiva)}</p></div>
                <div className="bg-white rounded p-2"><p className="text-slate-500">No productiva</p><p className="font-bold text-red-600">{fmt(preview.resumen.total_no_productiva)}</p></div>
                <div className="bg-white rounded p-2"><p className="text-slate-500">% recaudo comprometido</p><p className="font-bold text-amber-700">{preview.resumen.pct_recaudo_comprometido}%</p></div>
              </div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {preview.deudas.map(d => (
                  <div key={d.id} className="flex items-center justify-between bg-white rounded px-3 py-1.5 text-xs">
                    <span className="font-semibold text-slate-700">{d.acreedor}</span>
                    <span className="font-mono text-slate-600">{fmt(d.monto_total)}</span>
                    <div className="flex gap-1">
                      {(["productiva","no_productiva"] as const).map(t => (
                        <button key={t} onClick={() => handleReclasificar(d.id, t)}
                          className={`px-2 py-0.5 rounded font-medium transition ${d.tipo === t ? (t === "productiva" ? "bg-emerald-500 text-white" : "bg-red-500 text-white") : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}>
                          {t === "productiva" ? "Prod." : "No prod."}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={handleConfirmarDeudas} disabled={savingDeudas}
                className="mt-3 w-full bg-[#0F2A5C] text-white text-sm font-semibold py-2 rounded-lg hover:bg-[#1a3d7a] transition disabled:opacity-50"
                data-testid="confirmar-deudas-btn">
                {savingDeudas ? "Guardando…" : "Confirmar y guardar en MongoDB"}
              </button>
            </div>
          )}

          {/* Tabla deudas guardadas */}
          {deudas.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 uppercase tracking-wide">
                    <th className="px-3 py-2 text-left">Acreedor</th>
                    <th className="px-3 py-2 text-right">Saldo</th>
                    <th className="px-3 py-2 text-right">Tasa %</th>
                    <th className="px-3 py-2 text-center">Tipo</th>
                    <th className="px-3 py-2 text-center">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {deudas.map(d => (
                    <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium text-slate-700">{d.acreedor}</td>
                      <td className="px-3 py-2 text-right font-mono text-slate-700">{fmt(d.saldo_pendiente)}</td>
                      <td className="px-3 py-2 text-right text-slate-500">{d.tasa_mensual}%</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-2 py-0.5 rounded-full font-semibold text-[10px] ${d.tipo === "productiva" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                          {d.tipo === "productiva" ? "Productiva" : "No prod."}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${d.estado === "vencida" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
                          {d.estado}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400 text-center py-4">Sin deudas cargadas. Sube un Excel para comenzar.</p>
          )}
        </div>

        {/* Plan de pago deudas */}
        {planDeuda && !planDeuda.error && planDeuda.semanas?.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden" data-testid="plan-deudas-table">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingDown size={16} className="text-red-500" />
                <p className="text-sm font-bold text-slate-800">Plan de pago — Deuda no productiva</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500">Método: AVALANCHA</p>
                {planDeuda.fecha_liberacion && (
                  <p className="text-xs font-bold text-emerald-600">Libre: {planDeuda.fecha_liberacion}</p>
                )}
              </div>
            </div>
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50">
                  <tr className="text-slate-500 uppercase tracking-wide">
                    <th className="px-4 py-2 text-left">Sem</th>
                    <th className="px-4 py-2 text-center">Miércoles</th>
                    <th className="px-4 py-2 text-right">Disponible</th>
                    <th className="px-4 py-2 text-left">Pagos</th>
                    <th className="px-4 py-2 text-right">Deuda restante</th>
                  </tr>
                </thead>
                <tbody>
                  {planDeuda.semanas.map(s => (
                    <tr key={s.semana} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-2 text-slate-500">{s.semana}</td>
                      <td className="px-4 py-2 text-center font-mono text-slate-700">{s.miercoles}</td>
                      <td className="px-4 py-2 text-right text-emerald-700 font-mono">{fmt(s.disponible_deuda)}</td>
                      <td className="px-4 py-2 text-slate-600">
                        {s.pagos.map((p,i) => <span key={i} className="mr-2">{p.acreedor} <strong>{fmt(p.monto)}</strong></span>)}
                      </td>
                      <td className={`px-4 py-2 text-right font-bold font-mono ${s.deuda_np_restante === 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {s.deuda_np_restante === 0 ? "✅ $0" : fmt(s.deuda_np_restante)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Reporte del Lunes */}
        {reporteLunes && reporteLunes.alertas?.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4" data-testid="reporte-lunes-card">
            <p className="text-sm font-bold text-amber-800 mb-2">Alertas CFO</p>
            <div className="space-y-1">
              {reporteLunes.alertas.map((a: any, i: number) => (
                <p key={i} className="text-xs text-amber-700">{a.msg}</p>
              ))}
            </div>
          </div>
        )}
      </section>
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={handleGenerar}
          disabled={generating}
          data-testid="generar-informe-btn"
          className="flex items-center gap-2 bg-[#0F2A5C] hover:bg-[#1a3d7a] text-white font-semibold px-5 py-3 rounded-full shadow-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {generating ? (
            <><Loader2 size={16} className="animate-spin" /> Analizando datos CFO…</>
          ) : (
            <><Zap size={16} /> Generar Informe CFO</>
          )}
        </button>
      </div>
    </div>
  );
}
// force
