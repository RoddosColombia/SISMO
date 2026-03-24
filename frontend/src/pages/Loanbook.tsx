import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import {
  BookOpen, Plus, Search, ChevronRight, Calendar,
  CheckCircle, Clock, AlertTriangle, XCircle, Truck, DollarSign,
  Edit3, X, TrendingUp, Users, RefreshCw, Star, Bell, ClipboardList, FileDown,
} from "lucide-react";
import { toast } from "sonner";
import { FiltroFecha, DateRange, loadRange } from "../components/FiltroFecha";

const API = process.env.REACT_APP_BACKEND_URL;

const fmt   = (n: number | undefined) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
const fdate = (d: string | null | undefined): string => {
  if (!d) return "—";
  try { return format(parseISO(d), "dd/MMM/yy", { locale: es }); } catch { return d; }
};

// ─── Multiplicadores RODDOS (semanal base) ──────────────────────────────────
const MULTIPLICADORES: Record<string, number> = { semanal: 1.0, quincenal: 2.2, mensual: 4.4 };
const calcularValorCuota = (base: number, modo: string): number => {
  const m = MULTIPLICADORES[modo] || 1.0;
  return Math.round(base * m);
};

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface Cuota {
  numero: number;
  tipo: string;
  fecha_vencimiento: string;
  valor: number;
  estado: string;
  fecha_pago: string | null;
  valor_pagado?: number;
  comprobante?: string | null;
  notas?: string;
  canal_pago?: string;
  dpd_al_pagar?: number;
}

interface Loan {
  id: string;
  codigo: string;
  moto_descripcion?: string;
  moto_chasis?: string;
  motor?: string;
  cliente_nombre: string;
  cliente_nit?: string;
  tipo_identificacion?: string;
  cliente_telefono?: string;
  cliente_id?: string;
  plan: string;
  fecha_factura?: string;
  fecha_entrega?: string | null;
  fecha_entrega_programada?: string | null;
  fecha_primer_pago?: string | null;
  precio_venta?: number;
  cuota_inicial?: number;
  valor_cuota?: number;
  num_cuotas: number;
  cuotas: Cuota[];
  estado: string;
  num_cuotas_pagadas: number;
  num_cuotas_vencidas?: number;
  total_cobrado?: number;
  saldo_pendiente?: number;
  modo_pago?: string;
  placa?: string;
  datos_completos?: boolean;
  campos_pendientes?: string[];
  fuente_creacion?: string;
  // BUILD 3 — DPD y Score
  dpd_actual?: number;
  dpd_bucket?: string;
  score_pago?: string;
  estrella_nivel?: number;
  interes_mora_acumulado?: number;
  gestiones?: any[];
}

interface Stats {
  activo?: number;
  activos?: number;
  pendiente_entrega?: number;
  total_cartera_activa?: number;
  total_cobrado_historico?: number;
  cuotas_esta_semana?: number;
  valor_esta_semana?: number;
}

// ─── Constantes ───────────────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, string> = {
  Contado: "bg-emerald-100 text-emerald-700",
  P39S:    "bg-blue-100 text-blue-700",
  P52S:    "bg-violet-100 text-violet-700",
  P78S:    "bg-orange-100 text-orange-700",
};

const ESTADO_INFO: Record<string, { icon: React.ElementType; color: string; bg: string; label: string }> = {
  activo:            { icon: CheckCircle,   color: "text-green-600", bg: "bg-green-50",   label: "Activo" },
  mora:              { icon: AlertTriangle, color: "text-red-600",   bg: "bg-red-50",     label: "En Mora" },
  completado:        { icon: CheckCircle,   color: "text-slate-400", bg: "bg-slate-50",   label: "Completado" },
  pendiente_entrega: { icon: Truck,         color: "text-amber-600", bg: "bg-amber-50",   label: "Sin Entrega" },
  cancelado:         { icon: XCircle,       color: "text-slate-400", bg: "bg-slate-50",   label: "Cancelado" },
  recuperacion:      { icon: AlertTriangle, color: "text-purple-600",bg: "bg-purple-50",  label: "Recuperación" },
};

const BUCKET_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  "0":     { bg: "bg-green-100",  text: "text-green-700",  label: "Al día" },
  "1-7":   { bg: "bg-yellow-100", text: "text-yellow-700", label: "DPD 1-7" },
  "8-14":  { bg: "bg-orange-100", text: "text-orange-700", label: "DPD 8-14" },
  "15-21": { bg: "bg-red-100",    text: "text-red-700",    label: "DPD 15-21" },
  "22+":   { bg: "bg-red-900",    text: "text-red-100",    label: "DPD 22+" },
};

const SCORE_STYLE: Record<string, { color: string; stars: number }> = {
  "A+": { color: "text-emerald-700", stars: 5 },
  "A":  { color: "text-green-600",   stars: 4 },
  "B":  { color: "text-yellow-600",  stars: 3 },
  "C":  { color: "text-orange-600",  stars: 2 },
  "D":  { color: "text-red-600",     stars: 1 },
  "E":  { color: "text-red-900",     stars: 0 },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const StatCard: React.FC<{
  label: string; value: string | number; icon: React.ElementType;
  color?: string; sub?: string; subTestId?: string;
}> = ({ label, value, icon: Icon, color = "text-[#00A9E0]", sub, subTestId }) => (
  <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 flex items-start gap-4">
    <div className={`p-2.5 rounded-lg bg-slate-50 ${color}`}><Icon size={20} /></div>
    <div>
      <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold text-slate-800 mt-0.5">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5" data-testid={subTestId}>{sub}</p>}
    </div>
  </div>
);

const DPDBadge: React.FC<{ bucket?: string; dpd?: number }> = ({ bucket = "0", dpd = 0 }) => {
  const s = BUCKET_STYLE[bucket] ?? BUCKET_STYLE["0"];
  return (
    <span
      data-testid="dpd-badge"
      className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${s.bg} ${s.text}`}
    >
      {s.label}{dpd > 0 ? ` (${dpd}d)` : ""}
    </span>
  );
};

const ScoreBadge: React.FC<{ score?: string; estrellas?: number }> = ({ score = "A+", estrellas = 5 }) => {
  const s = SCORE_STYLE[score] ?? SCORE_STYLE["A+"];
  return (
    <div className="flex items-center gap-0.5" data-testid="score-badge">
      <span className={`text-xs font-bold ${s.color}`}>{score}</span>
      <span className="text-yellow-400 text-xs leading-none ml-0.5">
        {"★".repeat(s.stars)}{"☆".repeat(5 - s.stars)}
      </span>
    </div>
  );
};

// ─── Entrega Modal ────────────────────────────────────────────────────────────

const EntregaModal: React.FC<{
  loan: Loan; onClose: () => void; onSuccess: () => void;
}> = ({ loan, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [fecha, setFecha] = useState(loan.fecha_entrega_programada || today);
  const [plan, setPlan] = useState(loan.plan || "P52S");
  const [cuotaInicial, setCuotaInicial] = useState(String(loan.cuota_inicial || ""));
  const [valorCuota, setValorCuota] = useState(String(loan.valor_cuota || ""));
  const [cedula, setCedula] = useState(loan.cliente_nit || "");
  const [precioVenta, setPrecioVenta] = useState(String(loan.precio_venta || ""));
  const [modoPago, setModoPago] = useState(loan.modo_pago || "semanal");
  const [vinConfirm, setVinConfirm] = useState(loan.moto_chasis || "");
  const [motorNum, setMotorNum] = useState(loan.motor || "");
  const [placa, setPlaca] = useState(loan.placa || "");

  const incomplete = !loan.datos_completos && loan.datos_completos !== undefined;
  const isContado = modoPago === "contado";

  // Calculate preview of first payment date (Wednesday rule)
  const calcFirstWednesday = (fechaStr: string) => {
    if (!fechaStr || isContado) return null;
    const d = new Date(fechaStr + "T12:00:00");
    d.setDate(d.getDate() + 7);
    const wd = d.getDay(); // 0=Sun, 1=Mon, ..., 3=Wed, 6=Sat
    if (wd === 3) return d;
    if (wd < 3) { d.setDate(d.getDate() + (3 - wd)); return d; }
    d.setDate(d.getDate() + (10 - wd)); return d;
  };
  const primerMiercoles = calcFirstWednesday(fecha);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fecha) { toast.error("Selecciona una fecha de entrega"); return; }
    if (incomplete && !plan) { toast.error("Selecciona el plan de crédito"); return; }
    if (!loan.motor && !motorNum && !isContado) { toast.error("Número de motor es obligatorio"); return; }
    setLoading(true);
    try {
      const body: any = { fecha_entrega: fecha, modo_pago: modoPago };
      if (vinConfirm && vinConfirm !== loan.moto_chasis) body.moto_chasis = vinConfirm;
      if (motorNum) body.motor = motorNum;
      if (placa) body.placa = placa;
      if (incomplete) {
        if (plan) body.plan = plan;
        if (cuotaInicial) body.cuota_inicial = parseFloat(cuotaInicial);
        if (valorCuota) body.valor_cuota = parseFloat(valorCuota);
        if (cedula) body.cliente_nit = cedula;
        if (precioVenta) body.precio_venta = parseFloat(precioVenta);
      }
      const res = await axios.put(`${API}/api/loanbook/${loan.id}/entrega`, body,
        { headers: { Authorization: `Bearer ${token}` } });
      const primeraCuota = res.data?.primera_cuota_fecha;
      const msg = isContado
        ? "Entrega registrada — Pago de contado"
        : `Entrega registrada${primeraCuota ? ` — Primera cuota: ${fdate(primeraCuota)}` : ""}`;
      toast.success(msg, { duration: 5000 });
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error registrando entrega");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <Truck size={18} className="text-amber-500" />
            <div>
              <h3 className="font-bold text-slate-800">Registrar Entrega</h3>
              <p className="text-xs text-slate-500">{loan.codigo} — {loan.cliente_nombre}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Moto info + VIN/Motor/Placa confirmation */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 space-y-2">
            <p className="text-xs font-semibold text-amber-800">{loan.moto_descripcion || "TVS"}</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] font-medium text-amber-700 mb-0.5">VIN / Chasis</label>
                <input value={vinConfirm} onChange={e => setVinConfirm(e.target.value)}
                  placeholder="VIN" className="w-full border border-amber-300 rounded-lg px-2 py-1 text-xs font-mono bg-white" />
              </div>
              <div>
                <label className="block text-[10px] font-medium text-amber-700 mb-0.5">
                  Motor {!loan.motor && <span className="text-red-500">*</span>}
                </label>
                <input value={motorNum} onChange={e => setMotorNum(e.target.value)}
                  placeholder="Número motor" required={!loan.motor && !isContado}
                  className="w-full border border-amber-300 rounded-lg px-2 py-1 text-xs font-mono bg-white" />
              </div>
              <div className="col-span-2">
                <label className="block text-[10px] font-medium text-amber-700 mb-0.5">Placa (opcional)</label>
                <input value={placa} onChange={e => setPlaca(e.target.value)}
                  placeholder="ABC-123" className="w-full border border-amber-300 rounded-lg px-2 py-1 text-xs font-mono bg-white" />
              </div>
            </div>
          </div>

          {/* Complete missing data if needed */}
          {incomplete && (
            <div className="space-y-3 border border-slate-200 rounded-xl p-3 bg-slate-50">
              <p className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
                <ClipboardList size={13} className="text-blue-500" />
                Completar datos del crédito
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Plan de crédito *</label>
                  <select value={plan} onChange={e => setPlan(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
                    <option value="">Seleccionar</option>
                    <option value="P26S">P26S (26 sem)</option>
                    <option value="P39S">P39S (39 sem)</option>
                    <option value="P52S">P52S (52 sem)</option>
                    <option value="P78S">P78S (78 sem)</option>
                    <option value="Contado">Contado</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Cédula</label>
                  <input value={cedula} onChange={e => setCedula(e.target.value)}
                    placeholder="1234567890" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Cuota inicial</label>
                  <input type="number" value={cuotaInicial} onChange={e => setCuotaInicial(e.target.value)}
                    placeholder="0" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Cuota semanal</label>
                  <input type="number" value={valorCuota} onChange={e => setValorCuota(e.target.value)}
                    placeholder="0" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-slate-500 mb-1">Precio venta total</label>
                  <input type="number" value={precioVenta} onChange={e => setPrecioVenta(e.target.value)}
                    placeholder="0" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
                </div>
              </div>
            </div>
          )}

          {/* Modo de pago */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Modo de pago *</label>
            <select value={modoPago} onChange={e => setModoPago(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-400">
              <option value="semanal">Semanal (cada 7 días — miércoles)</option>
              <option value="quincenal">Quincenal (cada 14 días — miércoles)</option>
              <option value="mensual">Mensual (cada 28 días — miércoles)</option>
              <option value="contado">Contado (pago único — sin cuotas)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Fecha de entrega *
            </label>
            <input type="date" value={fecha} onChange={e => setFecha(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-400" />
            {fecha && !isContado && primerMiercoles && (
              <p className="text-xs text-emerald-600 mt-1 font-medium">
                Primera cuota: {primerMiercoles.toLocaleDateString("es-CO", { weekday: "long", year: "numeric", month: "2-digit", day: "2-digit" })} (miércoles)
              </p>
            )}
            {isContado && (
              <p className="text-xs text-blue-500 mt-1">Pago de contado — no se generarán cuotas</p>
            )}
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50">
              Cancelar
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              {loading ? "Procesando..." : "Confirmar entrega"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Pending Delivery Banner ──────────────────────────────────────────────────

const PendientesBanner: React.FC<{
  loans: Loan[];
  onEntrega: (loan: Loan) => void;
}> = ({ loans, onEntrega }) => {
  const pendientes = loans.filter(l => l.estado === "pendiente_entrega");
  if (pendientes.length === 0) return null;

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 shadow-sm" data-testid="pendientes-banner" id="pendientes-entrega-banner">
      <div className="flex items-center gap-2 mb-3">
        <Bell size={16} className="text-amber-600" />
        <h3 className="font-bold text-amber-800 text-sm">
          PENDIENTES DE ENTREGA: {pendientes.length}
        </h3>
      </div>
      <div className="space-y-3">
        {pendientes.map(loan => {
          const isManana = loan.fecha_entrega_programada === new Date(Date.now() + 86400000).toISOString().slice(0, 10);
          const isHoy    = loan.fecha_entrega_programada === today;
          const esVencida = loan.fecha_entrega_programada && loan.fecha_entrega_programada < today;
          const incomplete = !loan.datos_completos && loan.datos_completos !== undefined;

          return (
            <div key={loan.id}
              className={`bg-white rounded-xl border p-3 flex flex-col sm:flex-row sm:items-center gap-3 ${esVencida ? "border-red-200" : "border-amber-200"}`}
              data-testid={`pendiente-entrega-${loan.id}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-800 text-sm">{loan.cliente_nombre}</span>
                  {incomplete && (
                    <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-semibold">Datos incompletos</span>
                  )}
                  {isManana && (
                    <span className="text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-semibold">Entrega mañana</span>
                  )}
                  {isHoy && (
                    <span className="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded-full font-semibold">Entrega hoy</span>
                  )}
                  {esVencida && (
                    <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-semibold">Vencida</span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{loan.moto_descripcion || "TVS"}</p>
                {loan.moto_chasis && (
                  <p className="text-[11px] font-mono text-slate-400">VIN: {loan.moto_chasis}</p>
                )}
                {loan.fecha_entrega_programada && (
                  <p className="text-[11px] text-slate-400">
                    Entrega programada: {fdate(loan.fecha_entrega_programada)}
                  </p>
                )}
                {loan.fecha_factura && !loan.fecha_entrega_programada && (
                  <p className="text-[11px] text-slate-400">
                    Facturado: {fdate(loan.fecha_factura)}
                  </p>
                )}
              </div>
              <button
                onClick={() => onEntrega(loan)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 text-white rounded-lg text-xs font-semibold hover:bg-amber-600 whitespace-nowrap"
                data-testid={`btn-registrar-entrega-${loan.id}`}>
                <CheckCircle size={12} />
                {incomplete ? "Completar y entregar" : "Registrar entrega"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── Payment Modal ────────────────────────────────────────────────────────────

const PagoModal: React.FC<{
  loan: Loan; cuota: Cuota; onClose: () => void; onSuccess: () => void;
}> = ({ loan, cuota, onClose, onSuccess }) => {
  const { token } = useAuth();
  const saldoCuota = cuota.valor - ((cuota as any).valor_pagado || 0);
  const [tipoPago, setTipoPago] = useState<"total" | "parcial">("total");
  const [form, setForm] = useState({
    valor_pagado: saldoCuota, metodo_pago: "efectivo", notas: "",
    factura_numero: (loan as any).factura_numero || "",
  });
  const [loading, setLoading] = useState(false);
  const [facturaWarning, setFacturaWarning] = useState("");

  // Reset valor_pagado when switching tipo
  const handleTipoChange = (tipo: "total" | "parcial") => {
    setTipoPago(tipo);
    setForm(f => ({ ...f, valor_pagado: tipo === "total" ? saldoCuota : 0 }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(String(form.valor_pagado));
    if (!val || val <= 0) { toast.error("Ingresa un valor válido"); return; }
    if (val > saldoCuota) { toast.error(`El valor no puede superar el saldo de ${fmt(saldoCuota)}`); return; }
    setLoading(true);
    try {
      await axios.post(`${API}/api/loanbook/${loan.id}/pago`,
        { cuota_numero: cuota.numero, ...form, valor_pagado: val },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const msg = val >= saldoCuota
        ? `Cuota ${cuota.numero} pagada completamente`
        : `Abono de ${fmt(val)} registrado — Saldo restante: ${fmt(saldoCuota - val)}`;
      toast.success(msg);
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error registrando el pago");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b">
          <div>
            <h3 className="font-bold text-slate-800">Registrar Pago</h3>
            <p className="text-sm text-slate-500">{loan.codigo} — Cuota {cuota.numero} de {loan.num_cuotas}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="bg-amber-50 rounded-lg p-3 text-sm">
            <p className="font-medium text-amber-800">Cliente: {loan.cliente_nombre}</p>
            <p className="text-amber-700">Vencimiento: {fdate(cuota.fecha_vencimiento)} · Valor: {fmt(cuota.valor)}</p>
            {(cuota as any).valor_pagado > 0 && (
              <p className="text-amber-600 mt-1">Abonado: {fmt((cuota as any).valor_pagado)} · Saldo: {fmt(saldoCuota)}</p>
            )}
          </div>

          {/* Toggle pago total / parcial */}
          <div className="flex gap-2">
            <button type="button" onClick={() => handleTipoChange("total")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                tipoPago === "total" ? "bg-[#00A9E0] text-white border-[#00A9E0]" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
              }`}>
              Pago total
            </button>
            <button type="button" onClick={() => handleTipoChange("parcial")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                tipoPago === "parcial" ? "bg-amber-500 text-white border-amber-500" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
              }`}>
              Pago parcial
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Valor recibido</label>
            <input type="number" value={form.valor_pagado || ""}
              onChange={e => setForm(f => ({ ...f, valor_pagado: parseFloat(e.target.value) || 0 }))}
              placeholder={tipoPago === "total" ? String(saldoCuota) : "Valor del abono"}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#00A9E0] focus:border-transparent" required />
            {tipoPago === "parcial" && form.valor_pagado > 0 && form.valor_pagado < saldoCuota && (
              <p className="text-xs text-amber-600 mt-1">Saldo restante: {fmt(saldoCuota - form.valor_pagado)}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Método de pago</label>
            <select value={form.metodo_pago} onChange={e => setForm(f => ({ ...f, metodo_pago: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#00A9E0]">
              <option value="efectivo">Efectivo</option>
              <option value="transferencia_bancolombia">Transferencia Bancolombia</option>
              <option value="transferencia_bbva">Transferencia BBVA</option>
              <option value="transferencia_davivienda">Transferencia Davivienda</option>
              <option value="transferencia_bogota">Transferencia Banco Bogotá</option>
              <option value="nequi">Nequi</option>
              <option value="daviplata">Daviplata</option>
            </select>
          </div>
          {/* Factura Alegra — show if loanbook has no factura_alegra_id */}
          {!(loan as any).factura_alegra_id && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">N° Factura Alegra (opcional)</label>
              <input type="text" value={form.factura_numero}
                onChange={e => { setForm(f => ({ ...f, factura_numero: e.target.value })); setFacturaWarning(""); }}
                placeholder="Ej: FV-001 (se vincula automáticamente)"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              {facturaWarning && <p className="text-xs text-amber-600 mt-1">{facturaWarning}</p>}
            </div>
          )}
          {(loan as any).factura_alegra_id && (
            <p className="text-xs text-green-600">Factura Alegra vinculada: {(loan as any).factura_numero || (loan as any).factura_alegra_id}</p>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Notas (opcional)</label>
            <input type="text" value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
              placeholder="Observaciones del pago"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50">Cancelar</button>
            <button type="submit" disabled={loading}
              className={`flex-1 px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 ${
                tipoPago === "total" ? "bg-[#00A9E0] hover:bg-[#0090c0]" : "bg-amber-500 hover:bg-amber-600"
              }`}>
              {loading ? "Procesando..." : tipoPago === "total" ? "Confirmar Pago Total" : "Registrar Abono"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Edit Loan Modal ─────────────────────────────────────────────────────────

const EditLoanModal: React.FC<{
  loan: Loan; onClose: () => void; onSuccess: () => void;
}> = ({ loan, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [form, setForm] = useState({
    cliente_nombre: loan.cliente_nombre || "",
    cliente_nit: loan.cliente_nit || "",
    tipo_identificacion: loan.tipo_identificacion || "CC",
    cliente_telefono: loan.cliente_telefono || "",
    moto_descripcion: loan.moto_descripcion || "",
    moto_chasis: loan.moto_chasis || "",
    motor: loan.motor || "",
    placa: loan.placa || "",
    plan: loan.plan || "P39S",
    modo_pago: loan.modo_pago || "semanal",
    valor_cuota: String(loan.valor_cuota || ""),
    fecha_factura: loan.fecha_factura || "",
  });

  const handleSave = async () => {
    setLoading(true);
    try {
      // Only send fields that changed
      const body: any = {};
      if (form.cliente_nombre !== (loan.cliente_nombre || "")) body.cliente_nombre = form.cliente_nombre;
      if (form.cliente_nit !== (loan.cliente_nit || "")) body.cliente_nit = form.cliente_nit;
      if (form.tipo_identificacion !== (loan.tipo_identificacion || "CC")) body.tipo_identificacion = form.tipo_identificacion;
      if (form.cliente_telefono !== (loan.cliente_telefono || "")) body.cliente_telefono = form.cliente_telefono;
      if (form.moto_descripcion !== (loan.moto_descripcion || "")) body.moto_descripcion = form.moto_descripcion;
      if (form.moto_chasis !== (loan.moto_chasis || "")) body.moto_chasis = form.moto_chasis;
      if (form.motor !== (loan.motor || "")) body.motor = form.motor;
      if (form.placa !== (loan.placa || "")) body.placa = form.placa;
      if (form.plan !== (loan.plan || "")) body.plan = form.plan;
      if (form.modo_pago !== (loan.modo_pago || "")) body.modo_pago = form.modo_pago;
      if (form.valor_cuota !== String(loan.valor_cuota || "")) body.valor_cuota = parseFloat(form.valor_cuota);
      if (form.fecha_factura !== (loan.fecha_factura || "")) body.fecha_factura = form.fecha_factura;

      if (Object.keys(body).length === 0) { toast.info("No hay cambios"); onClose(); return; }

      await axios.put(`${API}/api/loanbook/${loan.id}`, body,
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Loanbook actualizado");
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error actualizando loanbook");
    } finally { setLoading(false); setShowConfirm(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b sticky top-0 bg-white z-10">
          <div>
            <h3 className="font-bold text-slate-800">Editar Loanbook</h3>
            <p className="text-xs text-slate-500">{loan.codigo}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          {/* Cliente */}
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Cliente</p>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Nombre *</label>
            <input value={form.cliente_nombre} onChange={e => setForm(f => ({ ...f, cliente_nombre: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Tipo ID</label>
              <select value={form.tipo_identificacion} onChange={e => setForm(f => ({ ...f, tipo_identificacion: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="CC">CC</option>
                <option value="CE">CE</option>
                <option value="PPT">PPT</option>
                <option value="PP">PP</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">NIT / Cédula</label>
              <input value={form.cliente_nit} onChange={e => setForm(f => ({ ...f, cliente_nit: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Teléfono</label>
              <input value={form.cliente_telefono} onChange={e => setForm(f => ({ ...f, cliente_telefono: e.target.value }))}
                placeholder="+573001234567" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          {/* Moto */}
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-2">Moto</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Descripción</label>
              <input value={form.moto_descripcion} onChange={e => setForm(f => ({ ...f, moto_descripcion: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Chasis / VIN</label>
              <input value={form.moto_chasis} onChange={e => setForm(f => ({ ...f, moto_chasis: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Motor</label>
              <input value={form.motor} onChange={e => setForm(f => ({ ...f, motor: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Placa</label>
              <input value={form.placa} onChange={e => setForm(f => ({ ...f, placa: e.target.value }))}
                placeholder="ABC-123" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          {/* Plan / Pago */}
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-2">Plan y pago</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Plan</label>
              <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="P39S">P39S</option>
                <option value="P52S">P52S</option>
                <option value="P78S">P78S</option>
                <option value="Contado">Contado</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Modo de pago</label>
              <select value={form.modo_pago} onChange={e => {
                  const modo = e.target.value;
                  setForm(f => {
                    // Reverse to semanal base, then apply new multiplier
                    const curMult = MULTIPLICADORES[f.modo_pago] || 1;
                    const curVal = parseFloat(f.valor_cuota) || (loan.valor_cuota || 0);
                    const semanalBase = curMult !== 0 ? Math.round(curVal / curMult) : curVal;
                    const newCuota = modo !== "contado" && semanalBase > 0
                      ? String(calcularValorCuota(semanalBase, modo))
                      : f.valor_cuota;
                    return { ...f, modo_pago: modo, valor_cuota: newCuota };
                  });
                }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="semanal">Semanal</option>
                <option value="quincenal">Quincenal</option>
                <option value="mensual">Mensual</option>
                <option value="contado">Contado</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Valor cuota</label>
              <input type="number" value={form.valor_cuota} onChange={e => setForm(f => ({ ...f, valor_cuota: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Fecha factura</label>
              <input type="date" value={form.fecha_factura} onChange={e => setForm(f => ({ ...f, fecha_factura: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-3">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50">
              Cancelar
            </button>
            {!showConfirm ? (
              <button type="button" onClick={() => setShowConfirm(true)}
                className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0]">
                Guardar cambios
              </button>
            ) : (
              <button type="button" onClick={handleSave} disabled={loading}
                className="flex-1 px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50">
                {loading ? "Guardando..." : "Confirmar cambios"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Loan Detail Panel ────────────────────────────────────────────────────────

const LoanDetail: React.FC<{
  loan: Loan; onClose: () => void; onRefresh: () => void;
}> = ({ loan, onClose, onRefresh }) => {
  const { token } = useAuth();
  const [selectedCuota, setSelectedCuota] = useState<Cuota | null>(null);
  const [editCuota, setEditCuota] = useState<number | null>(null);
  const [editVal, setEditVal] = useState("");
  const [entregaDate, setEntregaDate] = useState("");
  const [showEntrega, setShowEntrega] = useState(false);
  const [loadingEntrega, setLoadingEntrega] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const cuotas = loan.cuotas || [];
  const pct    = loan.num_cuotas > 0
    ? Math.round((loan.num_cuotas_pagadas / (loan.num_cuotas + 1)) * 100)
    : 0;

  const handleEntrega = async () => {
    if (!entregaDate) return;
    setLoadingEntrega(true);
    try {
      await axios.put(`${API}/api/loanbook/${loan.id}/entrega`, { fecha_entrega: entregaDate },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Fecha de entrega registrada. Cronograma generado.");
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error registrando entrega");
    } finally { setLoadingEntrega(false); setShowEntrega(false); }
  };

  const [recalcLoading, setRecalcLoading] = useState(false);
  const handleRecalcular = async () => {
    setRecalcLoading(true);
    try {
      const res = await axios.post(`${API}/api/loanbook/${loan.id}/recalcular`, {},
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(res.data?.message || "Cuotas recalculadas");
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error recalculando");
    } finally { setRecalcLoading(false); }
  };

  const handleEditCuota = async (cuota: Cuota) => {
    const newVal = parseFloat(editVal);
    if (isNaN(newVal) || newVal <= 0) { toast.error("Valor inválido"); return; }
    try {
      await axios.put(`${API}/api/loanbook/${loan.id}/cuota/${cuota.numero}`, { valor: newVal },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Cuota actualizada");
      setEditCuota(null);
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error editando cuota");
    }
  };

  const estadoIcon: Record<string, string> = {
    pagada: "✅", pendiente: "⏳", vencida: "🔴", parcial: "🟡",
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-40 flex justify-end">
      <div className="bg-white w-full max-w-xl h-full overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#0A1628] to-[#1a2f4e] text-white p-5 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[#00A9E0] font-bold text-lg">{loan.codigo}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PLAN_COLORS[loan.plan] || "bg-slate-200 text-slate-700"}`}>{loan.plan}</span>
            </div>
            <p className="text-white font-semibold">{loan.cliente_nombre}</p>
            <p className="text-slate-300 text-sm">{loan.moto_descripcion || "Moto"}</p>
            {/* DPD + Score en el header del panel */}
            {loan.dpd_actual !== undefined && (
              <div className="flex items-center gap-2 mt-2">
                <DPDBadge bucket={loan.dpd_bucket} dpd={loan.dpd_actual} />
                <ScoreBadge score={loan.score_pago} estrellas={loan.estrella_nivel} />
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <button onClick={handleRecalcular} disabled={recalcLoading}
              className="text-slate-300 hover:text-green-400 disabled:opacity-50" title="Recalcular cuotas">
              <RefreshCw size={16} className={recalcLoading ? "animate-spin" : ""} />
            </button>
            <button onClick={() => setShowEdit(true)} className="text-slate-300 hover:text-[#00A9E0]" title="Editar">
              <ClipboardList size={18} />
            </button>
            <button onClick={onClose} className="text-slate-300 hover:text-white"><X size={22} /></button>
          </div>
        </div>

        {/* Progress */}
        <div className="px-5 pt-4 pb-2 border-b">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span>Progreso: {loan.num_cuotas_pagadas} / {loan.num_cuotas + 1} cuotas</span>
            <span className="font-semibold text-[#00A9E0]">{pct}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div className="bg-[#00A9E0] h-2.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            <div className="text-center"><p className="text-xs text-slate-400">Total venta</p><p className="font-bold text-slate-800 text-sm">{fmt(loan.precio_venta)}</p></div>
            <div className="text-center"><p className="text-xs text-slate-400">Cobrado</p><p className="font-bold text-green-600 text-sm">{fmt(loan.total_cobrado)}</p></div>
            <div className="text-center"><p className="text-xs text-slate-400">Saldo</p><p className="font-bold text-red-500 text-sm">{fmt(loan.saldo_pendiente)}</p></div>
          </div>
          {loan.interes_mora_acumulado && loan.interes_mora_acumulado > 0 && (
            <p className="text-xs text-red-500 mt-2 text-center">
              Interés mora acumulado: {fmt(loan.interes_mora_acumulado)} (15% EA)
            </p>
          )}
        </div>

        {/* Delivery */}
        {loan.plan !== "Contado" && (
          <div className="px-5 py-3 border-b bg-slate-50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Fecha de entrega</p>
                <p className="font-semibold text-slate-800">
                  {loan.fecha_entrega
                    ? fdate(loan.fecha_entrega)
                    : <span className="text-amber-600">Sin registrar</span>}
                </p>
                {loan.fecha_primer_pago && <p className="text-xs text-slate-400">Primer pago: {fdate(loan.fecha_primer_pago)}</p>}
              </div>
              {!loan.fecha_entrega && (
                <button onClick={() => setShowEntrega(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 text-white rounded-lg text-xs font-medium hover:bg-amber-600">
                  <Truck size={13} /> Registrar entrega
                </button>
              )}
            </div>
            {showEntrega && (
              <div className="mt-3 flex gap-2">
                <input type="date" value={entregaDate} onChange={e => setEntregaDate(e.target.value)}
                  className="flex-1 border border-slate-300 rounded-lg px-3 py-1.5 text-sm" />
                <button onClick={handleEntrega} disabled={loadingEntrega}
                  className="px-3 py-1.5 bg-[#00A9E0] text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {loadingEntrega ? "..." : "Confirmar"}
                </button>
                <button onClick={() => setShowEntrega(false)}
                  className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm text-slate-600">X</button>
              </div>
            )}
          </div>
        )}

        {/* Installment Timeline */}
        <div className="flex-1 px-5 py-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Cronograma de cuotas</p>
          <div className="space-y-1.5">
            {cuotas.map((c) => (
              <div key={c.numero} className={`rounded-lg border p-3 flex items-center gap-3 transition-all
                ${c.estado === "pagada" ? "bg-green-50 border-green-200"
                  : c.estado === "vencida" ? "bg-red-50 border-red-200"
                  : "bg-white border-slate-200"}`}>
                <span className="text-base w-5">{estadoIcon[c.estado] || "⏳"}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-600">
                      {c.tipo === "inicial" ? "Cuota inicial" : `Cuota ${c.numero}`}
                    </span>
                    <span className="text-xs text-slate-400">· {fdate(c.fecha_vencimiento)}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {editCuota === c.numero ? (
                      <div className="flex gap-1">
                        <input type="number" value={editVal} onChange={e => setEditVal(e.target.value)}
                          className="w-28 border border-[#00A9E0] rounded px-2 py-0.5 text-xs" autoFocus />
                        <button onClick={() => handleEditCuota(c)} className="text-xs text-[#00A9E0] font-semibold">OK</button>
                        <button onClick={() => setEditCuota(null)} className="text-xs text-slate-400">×</button>
                      </div>
                    ) : (
                      <>
                        <span className="text-sm font-bold text-slate-800">{fmt(c.valor)}</span>
                        {c.estado !== "pagada" && (
                          <button onClick={() => { setEditCuota(c.numero); setEditVal(String(c.valor)); }}
                            className="text-slate-300 hover:text-[#00A9E0] transition-colors"><Edit3 size={11} /></button>
                        )}
                      </>
                    )}
                    {c.fecha_pago && <span className="text-xs text-green-600">Pagado {fdate(c.fecha_pago)}</span>}
                    {c.comprobante && <span className="text-xs text-slate-400">{c.comprobante}</span>}
                    {c.dpd_al_pagar && c.dpd_al_pagar > 0 && (
                      <span className="text-xs text-red-400">DPD {c.dpd_al_pagar}d</span>
                    )}
                  </div>
                </div>
                {c.estado !== "pagada" && c.fecha_vencimiento && (
                  <button onClick={() => setSelectedCuota(c)}
                    className="px-2.5 py-1 text-xs font-medium bg-[#00A9E0] text-white rounded-lg hover:bg-[#0090c0] whitespace-nowrap">
                    Registrar
                  </button>
                )}
              </div>
            ))}
            {cuotas.length === 0 && (
              <p className="text-center text-slate-400 text-sm py-8">
                Registre la fecha de entrega para generar el cronograma de cuotas
              </p>
            )}
          </div>
        </div>
      </div>
      {/* Gestiones section */}
      {loan.gestiones && loan.gestiones.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">
            Gestiones de cobranza ({loan.gestiones.length})
          </h3>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {[...loan.gestiones].reverse().map((g: any, i: number) => (
              <div key={i} className="text-xs flex items-start gap-2 py-1.5 border-b border-slate-100 last:border-0">
                <span className="text-slate-400 shrink-0 mt-0.5">{g.fecha ? g.fecha.slice(0, 10) : "—"}</span>
                <span className="font-medium text-slate-700">{(g.resultado || "").replace(/_/g, " ")}</span>
                {g.nota && <span className="text-slate-500 truncate">· {g.nota}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
      {selectedCuota && (
        <PagoModal loan={loan} cuota={selectedCuota} onClose={() => setSelectedCuota(null)}
          onSuccess={() => { setSelectedCuota(null); onRefresh(); }} />
      )}
      {showEdit && (
        <EditLoanModal loan={loan} onClose={() => setShowEdit(false)}
          onSuccess={() => { setShowEdit(false); onRefresh(); }} />
      )}
    </div>
  );
};

// ─── Create Loan Modal ────────────────────────────────────────────────────────

const CreateLoanModal: React.FC<{ onClose: () => void; onSuccess: () => void }> = ({ onClose, onSuccess }) => {
  const { token } = useAuth();
  const [form, setForm] = useState({
    cliente_nombre: "", cliente_nit: "", tipo_identificacion: "CC",
    moto_descripcion: "", moto_chasis: "", placa: "",
    plan: "P39S", fecha_factura: "",
    precio_venta: "", cuota_inicial: "", valor_cuota: "", modo_pago: "semanal",
    num_cuotas: "39",
  });
  const [retoma, setRetoma] = useState({ activo: false, marca_modelo: "", vin: "", placa: "", valor: "" });
  const [loading, setLoading] = useState(false);
  const [catalogo, setCatalogo] = useState<any[]>([]);

  // Fetch plan catalog from MongoDB on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/api/loanbook/catalogo-planes`,
          { headers: { Authorization: `Bearer ${token}` } });
        if (Array.isArray(res.data)) setCatalogo(res.data);
      } catch { /* manual entry */ }
    })();
  }, [token]);

  // Helper: get cuotas count from catalog
  const getCuotasFromCatalog = (plan: string, modo: string) => {
    const p = catalogo.find(c => c.plan === plan);
    if (!p) return "";
    return String(p[`cuotas_${modo}`] ?? p.cuotas_semanal ?? "");
  };

  // Auto-fill num_cuotas when plan or catalogo changes
  useEffect(() => {
    if (catalogo.length > 0) {
      setForm(f => ({
        ...f,
        num_cuotas: getCuotasFromCatalog(f.plan, f.modo_pago) || f.num_cuotas,
        modo_pago: f.plan === "Contado" ? "contado" : f.modo_pago,
      }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.plan, catalogo]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const isC = form.plan === "Contado" || form.modo_pago === "contado";
      const body: any = {
        cliente_nombre: form.cliente_nombre,
        cliente_nit: form.cliente_nit,
        tipo_identificacion: form.tipo_identificacion,
        moto_descripcion: form.moto_descripcion,
        moto_chasis: form.moto_chasis,
        plan: form.plan,
        fecha_factura: form.fecha_factura,
        precio_venta: parseFloat(form.precio_venta),
        cuota_inicial: parseFloat(form.cuota_inicial) || 0,
        valor_cuota: isC ? 0 : parseFloat(form.valor_cuota),
        modo_pago: form.modo_pago,
      };
      if (form.placa) body.placa = form.placa;
      if (retoma.activo && parseFloat(retoma.valor) > 0) {
        body.tiene_retoma = true;
        body.retoma_marca_modelo = retoma.marca_modelo;
        body.retoma_vin = retoma.vin || null;
        body.retoma_placa = retoma.placa || null;
        body.retoma_valor = parseFloat(retoma.valor);
      }
      await axios.post(`${API}/api/loanbook`, body,
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Plan de pago creado exitosamente");
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error creando el plan");
    } finally { setLoading(false); }
  };

  const isContado = form.plan === "Contado" || form.modo_pago === "contado";

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b sticky top-0 bg-white z-10">
          <h3 className="font-bold text-slate-800">Nuevo Plan de Pago</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Código auto-generado */}
          <p className="text-xs text-slate-400">Código: se asigna automáticamente (LB-2026-XXXX)</p>

          {/* Nombre del cliente */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Nombre del cliente *</label>
            <input required value={form.cliente_nombre} onChange={e => setForm(f => ({ ...f, cliente_nombre: e.target.value }))}
              placeholder="Carlos García" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>

          {/* Tipo ID + NIT/Cédula */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Tipo ID</label>
              <select value={form.tipo_identificacion} onChange={e => setForm(f => ({ ...f, tipo_identificacion: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="CC">CC</option>
                <option value="CE">CE</option>
                <option value="PPT">PPT</option>
                <option value="PP">PP</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">NIT / Cédula *</label>
              <input required value={form.cliente_nit} onChange={e => setForm(f => ({ ...f, cliente_nit: e.target.value }))}
                placeholder="1234567890" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          {/* Moto + Chasis + Placa */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Moto *</label>
              <input required value={form.moto_descripcion} onChange={e => setForm(f => ({ ...f, moto_descripcion: e.target.value }))}
                placeholder="TVS Raider 125" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Chasis / VIN *</label>
              <input required value={form.moto_chasis} onChange={e => setForm(f => ({ ...f, moto_chasis: e.target.value }))}
                placeholder="9FL25AF3XVDB95057" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Placa (opcional)</label>
            <input value={form.placa} onChange={e => setForm(f => ({ ...f, placa: e.target.value }))}
              placeholder="ABC-123" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>

          {/* Fecha factura */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Fecha factura *</label>
            <input required type="date" value={form.fecha_factura} onChange={e => setForm(f => ({ ...f, fecha_factura: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>

          {/* Plan + Modo de pago */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Plan *</label>
              <select value={form.plan} onChange={e => {
                  const plan = e.target.value;
                  setForm(f => ({
                    ...f,
                    plan,
                    modo_pago: plan === "Contado" ? "contado" : f.modo_pago === "contado" ? "semanal" : f.modo_pago,
                  }));
                }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="P39S">P39S</option>
                <option value="P52S">P52S</option>
                <option value="P78S">P78S</option>
                <option value="Contado">Contado</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Modo de pago *</label>
              <select value={form.modo_pago} disabled={form.plan === "Contado"}
                onChange={e => {
                  const modo = e.target.value;
                  setForm(f => {
                    const curMult = MULTIPLICADORES[f.modo_pago] || 1;
                    const curVal = parseFloat(f.valor_cuota) || 0;
                    const semanalBase = curMult !== 0 ? Math.round(curVal / curMult) : curVal;
                    const newCuota = modo !== "contado" && semanalBase > 0
                      ? String(calcularValorCuota(semanalBase, modo)) : f.valor_cuota;
                    const numCuotas = getCuotasFromCatalog(f.plan, modo) || f.num_cuotas;
                    return { ...f, modo_pago: modo, valor_cuota: newCuota, num_cuotas: numCuotas };
                  });
                }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm disabled:bg-slate-100">
                <option value="semanal">Semanal</option>
                <option value="quincenal">Quincenal</option>
                <option value="mensual">Mensual</option>
                <option value="contado">Contado</option>
              </select>
            </div>
          </div>

          {/* Precio venta + Cuota inicial + Valor cuota */}
          <div className={`grid ${isContado ? "grid-cols-2" : "grid-cols-3"} gap-3`}>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Precio venta *</label>
              <input required type="number" value={form.precio_venta} onChange={e => setForm(f => ({ ...f, precio_venta: e.target.value }))}
                placeholder="7800000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Cuota inicial</label>
              <input type="number" value={form.cuota_inicial} onChange={e => setForm(f => ({ ...f, cuota_inicial: e.target.value }))}
                placeholder="0" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            {!isContado && (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Valor cuota *</label>
                <input required type="number" value={form.valor_cuota} onChange={e => setForm(f => ({ ...f, valor_cuota: e.target.value }))}
                  placeholder="210000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              </div>
            )}
          </div>
          {!isContado && form.num_cuotas && (
            <p className="text-xs text-slate-500">
              {form.num_cuotas} cuotas de {fmt(parseFloat(form.valor_cuota) || 0)} ({form.modo_pago})
            </p>
          )}

          {/* Retoma */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <button type="button" onClick={() => setRetoma(r => ({ ...r, activo: !r.activo }))}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 hover:bg-slate-100 transition-colors">
              <span className="text-xs font-semibold text-slate-600">Retoma (moto usada como parte de pago)</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${retoma.activo ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"}`}>
                {retoma.activo ? "Activo" : "No"}
              </span>
            </button>
            {retoma.activo && (
              <div className="p-4 space-y-3 border-t">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Marca / Modelo retoma *</label>
                  <input value={retoma.marca_modelo} onChange={e => setRetoma(r => ({ ...r, marca_modelo: e.target.value }))}
                    placeholder="Honda XR150 2020" required
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">VIN (opcional)</label>
                    <input value={retoma.vin} onChange={e => setRetoma(r => ({ ...r, vin: e.target.value }))}
                      placeholder="Chasis moto retoma"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Placa (opcional)</label>
                    <input value={retoma.placa} onChange={e => setRetoma(r => ({ ...r, placa: e.target.value }))}
                      placeholder="ABC-123" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Valor retoma $ *</label>
                  <input type="number" value={retoma.valor} onChange={e => setRetoma(r => ({ ...r, valor: e.target.value }))}
                    placeholder="1000000" required className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
                </div>
                {retoma.valor && (parseFloat(form.cuota_inicial) > 0 || parseFloat(retoma.valor) > 0) && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-xs">
                    <p className="font-semibold text-green-800">Desglose cuota inicial:</p>
                    <p className="text-green-700">Retoma: {fmt(parseFloat(retoma.valor))} + Efectivo: {fmt(Math.max(0, (parseFloat(form.cuota_inicial) || 0) - parseFloat(retoma.valor)))} = Cuota inicial: {fmt(parseFloat(form.cuota_inicial) || 0)}</p>
                    {parseFloat(retoma.valor) >= (parseFloat(form.cuota_inicial) || 0) && (
                      <p className="text-green-600 font-semibold mt-1">Cuota inicial cubierta por retoma</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Botón crear */}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium">Cancelar</button>
            <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0] disabled:opacity-50">
              {loading ? "Creando..." : "Crear Plan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Loanbook() {
  const { token } = useAuth();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);
  const [selectedLoan, setSelectedLoan] = useState<Loan | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [entregaLoan, setEntregaLoan] = useState<Loan | null>(null);
  const [filters, setFilters] = useState({ estado: "", plan: "", search: "" });
  const [sortBy, setSortBy]   = useState<string>("");
  const [filtroFecha, setFiltroFecha] = useState<DateRange>(() => loadRange("loanbook"));

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [loansRes, statsRes] = await Promise.all([
        axios.get(`${API}/api/loanbook`, {
          headers: { Authorization: `Bearer ${token}` },
          params: {
            estado:  filters.estado  || undefined,
            plan:    filters.plan    || undefined,
            cliente: filters.search  || undefined,
          },
        }),
        axios.get(`${API}/api/loanbook/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setLoans(loansRes.data || []);
      setStats(statsRes.data || {});
    } catch {
      toast.error("Error cargando Loanbook");
    } finally { setLoading(false); }
  }, [token, filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // HOTFIX 21.1 FIX #3: Excel export for loanbook data
  const handleExportarExcel = async () => {
    try {
      const res = await fetch(`${API}/api/reports/excel`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ reportType: "loanbooks", filters: {} }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err?.detail || `Error ${res.status} al descargar Excel`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "RODDOS_Loanbooks.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error(`Error de red: ${e?.message || "desconocido"}`);
    }
  };

  const refreshLoan = async (loanId: string) => {
    try {
      const res = await axios.get(`${API}/api/loanbook/${loanId}`, { headers: { Authorization: `Bearer ${token}` } });
      setLoans(prev => prev.map(l => l.id === loanId ? res.data : l));
      if (selectedLoan?.id === loanId) setSelectedLoan(res.data);
    } catch { /* silent */ }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00A9E0] to-[#0078b0] flex items-center justify-center">
            <BookOpen size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Loanbook</h1>
            <p className="text-sm text-slate-500">Gestión de planes de pago — motos Auteco</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchData} className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500" data-testid="refresh-btn">
            <RefreshCw size={16} />
          </button>
          <button onClick={handleExportarExcel} data-testid="export-excel-loanbook-btn"
            className="flex items-center gap-1.5 text-xs border border-emerald-500 text-emerald-700 px-3 py-2 rounded-lg font-semibold hover:bg-emerald-50 transition">
            <FileDown size={14} /> Excel
          </button>
          <button onClick={() => setShowCreate(true)} data-testid="new-plan-btn"
            className="flex items-center gap-2 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0]">
            <Plus size={16} /> Nuevo Plan
          </button>
        </div>
      </div>

      {/* Pending Delivery Banner */}
      <PendientesBanner
        loans={loans}
        onEntrega={(loan) => setEntregaLoan(loan)}
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Créditos activos"    value={(stats.activo || stats.activos) || 0} icon={Users} sub={`${stats.pendiente_entrega || 0} sin entrega`} subTestId="kpi-sin-entrega" />
        <StatCard label="Cartera activa"      value={fmt(stats.total_cartera_activa)} icon={DollarSign} color="text-red-500" sub="saldo pendiente" />
        <StatCard label="Total cobrado"       value={fmt(stats.total_cobrado_historico)} icon={TrendingUp} color="text-green-600" />
        <StatCard label="Cuotas esta semana"  value={`${stats.cuotas_esta_semana || 0}`} icon={Calendar} color="text-amber-500" sub={fmt(stats.valor_esta_semana)} />
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 flex-1 min-w-52 border border-slate-300 rounded-lg px-3 py-2">
          <Search size={14} className="text-slate-400" />
          <input value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
            placeholder="Buscar cliente..." className="flex-1 text-sm outline-none bg-transparent"
            data-testid="search-input" />
        </div>
        <select value={filters.plan} onChange={e => setFilters(f => ({ ...f, plan: e.target.value }))}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm min-w-36" data-testid="filter-plan">
          <option value="">Todos los planes</option>
          <option value="Contado">Contado</option>
          <option value="P26S">P26S</option>
          <option value="P39S">P39S</option>
          <option value="P52S">P52S</option>
          <option value="P78S">P78S</option>
        </select>
        <select value={filters.estado} onChange={e => setFilters(f => ({ ...f, estado: e.target.value }))}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm min-w-36" data-testid="filter-estado">
          <option value="">Todos los estados</option>
          <option value="activo">Activos</option>
          <option value="mora">En mora</option>
          <option value="pendiente_entrega">Sin entrega</option>
          <option value="completado">Completados</option>
        </select>
        <FiltroFecha moduleKey="loanbook" onChange={setFiltroFecha} compact />
        {(filters.estado || filters.plan || filters.search) && (
          <button onClick={() => setFilters({ estado: "", plan: "", search: "" })}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1">
            <X size={12} /> Limpiar
          </button>
        )}
        <span className="text-sm text-slate-400 ml-auto">{loans.length} resultado{loans.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Código</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Cliente</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide hidden lg:table-cell">Moto</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Plan</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide hidden md:table-cell">Entrega</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Progreso</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Estado</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide hidden xl:table-cell cursor-pointer hover:text-slate-300"
                onClick={() => setSortBy(s => s === "dpd_asc" ? "dpd_desc" : "dpd_asc")}>
                DPD {sortBy === "dpd_asc" ? "↑" : sortBy === "dpd_desc" ? "↓" : ""}
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide hidden xl:table-cell cursor-pointer hover:text-slate-300"
                onClick={() => setSortBy(s => s === "score_asc" ? "score_desc" : "score_asc")}>
                Score {sortBy === "score_asc" ? "↑" : sortBy === "score_desc" ? "↓" : ""}
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide hidden xl:table-cell">Mora</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={10} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
            ) : loans.length === 0 ? (
              <tr><td colSpan={10} className="px-4 py-12 text-center text-slate-400">No hay planes de pago registrados</td></tr>
            ) : [...loans].sort((a, b) => {
              if (sortBy === "dpd_asc")    return (a.dpd_actual ?? 0) - (b.dpd_actual ?? 0);
              if (sortBy === "dpd_desc")   return (b.dpd_actual ?? 0) - (a.dpd_actual ?? 0);
              if (sortBy === "score_asc")  return (a.score_pago ?? "A+").localeCompare(b.score_pago ?? "A+");
              if (sortBy === "score_desc") return (b.score_pago ?? "A+").localeCompare(a.score_pago ?? "A+");
              return 0;
            }).map(loan => {
              const total    = loan.num_cuotas + 1;
              const pct      = total > 0 ? Math.round((loan.num_cuotas_pagadas / total) * 100) : 0;
              const info     = ESTADO_INFO[loan.estado] ?? ESTADO_INFO.activo;
              const StateIcon = info.icon;
              return (
                <tr
                  key={loan.id}
                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedLoan(loan)}
                  data-testid={`loan-row-${loan.id}`}
                >
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs font-semibold text-[#00A9E0]">{loan.codigo}</span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800 text-sm">{loan.cliente_nombre}</p>
                    <p className="text-xs text-slate-400">{loan.cliente_nit}</p>
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <p className="text-xs text-slate-500 max-w-36 truncate">{loan.moto_descripcion || "—"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${PLAN_COLORS[loan.plan] || "bg-slate-100 text-slate-600"}`}>{loan.plan}</span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-xs text-slate-500">
                    {loan.fecha_entrega ? fdate(loan.fecha_entrega) : <span className="text-amber-500">Sin registrar</span>}
                  </td>
                  <td className="px-4 py-3 min-w-36">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-slate-100 rounded-full h-1.5">
                        <div className="bg-[#00A9E0] h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-slate-500 w-12">{loan.num_cuotas_pagadas}/{total}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${info.bg} ${info.color}`}>
                      <StateIcon size={11} />{info.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden xl:table-cell">
                    <DPDBadge bucket={loan.dpd_bucket} dpd={loan.dpd_actual} />
                  </td>
                  <td className="px-4 py-3 hidden xl:table-cell">
                    <ScoreBadge score={loan.score_pago} estrellas={loan.estrella_nivel} />
                  </td>
                  <td className="px-4 py-3 hidden xl:table-cell">
                    {(loan.interes_mora_acumulado ?? 0) > 0 ? (
                      <span className="text-xs font-semibold text-red-500">
                        {fmt(loan.interes_mora_acumulado ?? 0)}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight size={16} className="text-slate-300" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedLoan && (
        <LoanDetail
          loan={selectedLoan}
          onClose={() => setSelectedLoan(null)}
          onRefresh={() => refreshLoan(selectedLoan.id)}
        />
      )}
      {showCreate && (
        <CreateLoanModal
          onClose={() => setShowCreate(false)}
          onSuccess={() => { setShowCreate(false); fetchData(); }}
        />
      )}
      {entregaLoan && (
        <EntregaModal
          loan={entregaLoan}
          onClose={() => setEntregaLoan(null)}
          onSuccess={() => { setEntregaLoan(null); fetchData(); }}
        />
      )}
    </div>
  );
}
