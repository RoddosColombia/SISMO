import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import {
  format, parseISO, addWeeks, subWeeks, startOfWeek,
  differenceInCalendarDays,
} from "date-fns";
import { es } from "date-fns/locale";
import {
  Wallet, Phone, MessageCircle, RefreshCw, X, ChevronLeft, ChevronRight,
  Calendar, BarChart3, Users, AlertTriangle, Clock, CheckCircle, Download,
  MapPin, Search, TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import jsPDF from "jspdf";

const API = process.env.REACT_APP_BACKEND_URL;

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (n) =>
  new Intl.NumberFormat("es-CO", {
    style: "currency", currency: "COP", maximumFractionDigits: 0,
  }).format(n || 0);

const fdate = (d) => {
  try { return format(parseISO(d), "dd MMM", { locale: es }); }
  catch { return d || "—"; }
};

const daysOverdue = (fv) => {
  try {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const due = parseISO(fv); due.setHours(0, 0, 0, 0);
    return differenceInCalendarDays(today, due);
  } catch { return 0; }
};

const formatPhone = (phone) => {
  if (!phone) return null;
  const cleaned = phone.replace(/\D/g, "");
  if (!cleaned) return null;
  if (cleaned.startsWith("57")) return cleaned;
  if (cleaned.startsWith("3")) return `57${cleaned}`;
  return `57${cleaned}`;
};

const buildWaText = (c) =>
  encodeURIComponent(
    `Hola ${c.cliente_nombre}, le recordamos que tiene una cuota pendiente de ${fmt(c.valor)} ` +
    `del crédito ${c.codigo} con RODDOS S.A.S. ` +
    `Cuota ${c.cuota_numero}/${c.total_cuotas} — vencimiento ${c.fecha_vencimiento}. ` +
    `Por favor comuníquese con nosotros para regularizar. Gracias.`
  );

// ─── Receipt Generator ────────────────────────────────────────────────────────
function generateReceipt(cuota) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: [80, 120] });
  doc.setFontSize(9); doc.setFont("helvetica", "bold");
  doc.text("RODDOS S.A.S.", 40, 8, { align: "center" });
  doc.setFont("helvetica", "normal"); doc.setFontSize(7);
  doc.text("Concesionario Auteco", 40, 12, { align: "center" });
  doc.setLineWidth(0.3); doc.line(4, 15, 76, 15);
  doc.setFont("helvetica", "bold"); doc.setFontSize(8);
  doc.text("COMPROBANTE DE PAGO", 40, 20, { align: "center" });
  if (cuota.comprobante) doc.text(cuota.comprobante, 40, 25, { align: "center" });
  doc.line(4, 28, 76, 28);
  doc.setFont("helvetica", "normal"); doc.setFontSize(7);
  const rows = [
    ["Cliente:", cuota.cliente_nombre || ""],
    ["Plan:", cuota.plan || ""],
    ["Código:", cuota.codigo || ""],
    ["Cuota N°:", `${cuota.cuota_numero}/${cuota.total_cuotas}`],
    ["Vencimiento:", cuota.fecha_vencimiento || ""],
    ["Fecha pago:", cuota.fecha_pago || new Date().toISOString().slice(0, 10)],
    ["Método:", cuota.metodo_pago || "efectivo"],
  ];
  let y = 33;
  for (const [k, v] of rows) {
    doc.setFont("helvetica", "bold"); doc.text(k, 5, y);
    doc.setFont("helvetica", "normal"); doc.text(String(v).slice(0, 35), 28, y);
    y += 5;
  }
  doc.line(4, y, 76, y); y += 5;
  doc.setFont("helvetica", "bold"); doc.setFontSize(10);
  doc.text(fmt(cuota.valor_pagado || cuota.valor), 40, y + 4, { align: "center" });
  doc.setFontSize(7); doc.setFont("helvetica", "normal");
  doc.text("Gracias por su pago puntual — RODDOS", 40, y + 11, { align: "center" });
  doc.save(`${cuota.comprobante || "recibo"}.pdf`);
}

// ─── Payment Bottom Sheet ─────────────────────────────────────────────────────
const PagoBottomSheet = ({ cuota, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [valor, setValor] = useState(cuota.valor);
  const [metodo, setMetodo] = useState("efectivo");
  const [notas, setNotas] = useState("");
  const [loading, setLoading] = useState(false);

  const dias = daysOverdue(cuota.fecha_vencimiento);
  const urgencyLabel = dias > 0
    ? `Vencida hace ${dias} día${dias !== 1 ? "s" : ""}`
    : dias === 0 ? "Vence hoy" : "Próxima";
  const urgencyColor = dias > 0 ? "text-red-500" : dias === 0 ? "text-amber-500" : "text-blue-500";

  const handlePay = async () => {
    const amount = parseFloat(valor);
    if (!amount || amount <= 0) { toast.error("Ingresa un valor válido"); return; }
    setLoading(true);
    try {
      const res = await axios.post(
        `${API}/api/loanbook/${cuota.loanbook_id}/pago`,
        { cuota_numero: cuota.cuota_numero, valor_pagado: amount, metodo_pago: metodo, notas },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Cobro registrado — ${cuota.cliente_nombre}`);
      if (res.data?.comprobante) {
        const rec = {
          ...cuota,
          comprobante: res.data.comprobante,
          valor_pagado: amount,
          metodo_pago: metodo,
          fecha_pago: new Date().toISOString().slice(0, 10),
        };
        generateReceipt(rec);
      }
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando el cobro");
    } finally { setLoading(false); }
  };

  const METODOS = [
    { id: "efectivo", label: "Efectivo", emoji: "💵" },
    { id: "nequi", label: "Nequi", emoji: "📱" },
    { id: "transferencia", label: "Transf.", emoji: "🏦" },
    { id: "tarjeta", label: "Tarjeta", emoji: "💳" },
  ];

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div
        className="absolute bottom-0 left-0 right-0 bg-white rounded-t-3xl shadow-2xl max-w-lg mx-auto"
        style={{ animation: "slideUp 0.25s ease-out" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 bg-slate-200 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex items-start justify-between px-5 py-3 border-b border-slate-100">
          <div>
            <h3 className="font-bold text-slate-800 text-lg" data-testid="pago-sheet-cliente">
              {cuota.cliente_nombre}
            </h3>
            <p className="text-sm text-slate-500">
              {cuota.codigo} · Cuota {cuota.cuota_numero}/{cuota.total_cuotas}
            </p>
            <p className={`text-xs font-semibold mt-0.5 ${urgencyColor}`}>{urgencyLabel}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 pt-4 pb-6 space-y-4">
          {/* Amount */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Valor recibido
            </label>
            <div className="mt-1.5 flex items-center gap-2 border-2 border-[#00C853] rounded-xl px-4 py-3 bg-green-50">
              <span className="text-slate-500 font-bold text-lg">$</span>
              <input
                type="number"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                className="flex-1 text-2xl font-bold text-slate-800 bg-transparent outline-none"
                inputMode="numeric"
                data-testid="pago-valor-input"
              />
            </div>
          </div>

          {/* Payment method */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Método de pago
            </label>
            <div className="mt-1.5 grid grid-cols-4 gap-2">
              {METODOS.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMetodo(m.id)}
                  data-testid={`metodo-${m.id}`}
                  className={`py-3 rounded-xl flex flex-col items-center gap-1 text-xs font-semibold transition-all ${
                    metodo === m.id
                      ? "bg-[#00C853] text-white shadow-md scale-105"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  <span className="text-lg">{m.emoji}</span>
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Notas (opcional)
            </label>
            <input
              type="text"
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Observaciones..."
              className="mt-1.5 w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#00C853] focus:border-transparent"
            />
          </div>

          {/* Confirm */}
          <button
            onClick={handlePay}
            disabled={loading || !valor || parseFloat(valor) <= 0}
            data-testid="confirmar-cobro-btn"
            className="w-full py-4 bg-[#00C853] text-white rounded-xl font-bold text-base tracking-wide disabled:opacity-50 hover:bg-[#00a843] active:scale-95 transition-all"
          >
            {loading ? "Procesando..." : `CONFIRMAR COBRO · ${fmt(valor)}`}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Cuota Card (mobile-optimized) ───────────────────────────────────────────
const CuotaCard = ({ cuota, onPay }) => {
  const dias = daysOverdue(cuota.fecha_vencimiento);
  const waPhone = formatPhone(cuota.cliente_telefono);

  const style =
    dias > 0
      ? {
          border: "border-l-red-500",
          badgeBg: "bg-red-100", badgeText: "text-red-700",
          badge: dias === 1 ? "VENCIDA · 1 día" : `VENCIDA · ${dias} días`,
        }
      : {
          border: "border-l-amber-400",
          badgeBg: "bg-amber-100", badgeText: "text-amber-700",
          badge: "HOY",
        };

  return (
    <div
      className={`bg-white rounded-2xl border-l-4 ${style.border} shadow-sm overflow-hidden`}
      data-testid={`cuota-card-${cuota.loanbook_id}`}
    >
      {/* Info section */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${style.badgeBg} ${style.badgeText}`}>
                {style.badge}
              </span>
            </div>
            <h3 className="font-bold text-slate-800 text-base leading-snug truncate">
              {cuota.cliente_nombre}
            </h3>
            <p className="text-xs text-slate-500 truncate mt-0.5">{cuota.moto || "—"}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-xl font-bold text-slate-800">{fmt(cuota.valor)}</p>
            <p className="text-xs text-slate-400 font-mono">{cuota.codigo}</p>
          </div>
        </div>
        <div className="flex items-center justify-between mt-2 text-xs text-slate-400">
          <span>Cuota {cuota.cuota_numero}/{cuota.total_cuotas} · {cuota.plan}</span>
          <span>Vence: {fdate(cuota.fecha_vencimiento)}</span>
        </div>
      </div>

      {/* Action bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-t border-slate-100">
        <button
          onClick={() => onPay(cuota)}
          data-testid={`cobrar-btn-${cuota.cuota_numero}`}
          className="flex-1 py-2.5 bg-[#00C853] text-white rounded-xl font-bold text-sm tracking-wide hover:bg-[#00a843] active:scale-95 transition-all"
        >
          COBRAR
        </button>
        {waPhone && (
          <>
            <a
              href={`tel:${cuota.cliente_telefono}`}
              data-testid={`llamar-btn-${cuota.cuota_numero}`}
              className="p-2.5 bg-blue-50 text-blue-600 rounded-xl hover:bg-blue-100 transition-colors"
              title="Llamar"
            >
              <Phone size={18} />
            </a>
            <a
              href={`https://wa.me/${waPhone}?text=${buildWaText(cuota)}`}
              target="_blank"
              rel="noreferrer"
              data-testid={`whatsapp-btn-${cuota.cuota_numero}`}
              className="p-2.5 bg-green-50 text-green-600 rounded-xl hover:bg-green-100 transition-colors"
              title="Enviar WhatsApp"
            >
              <MessageCircle size={18} />
            </a>
          </>
        )}
      </div>
    </div>
  );
};

// ─── Score Bar ────────────────────────────────────────────────────────────────
const ScoreBar = ({ score, color }) => {
  const colors = {
    green: "bg-green-500", yellow: "bg-yellow-400",
    orange: "bg-orange-400", red: "bg-red-500",
  };
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-100 rounded-full h-2 min-w-16">
        <div
          className={`h-2 rounded-full ${colors[color] || "bg-slate-400"}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-bold text-slate-700 w-9">{score}%</span>
    </div>
  );
};

// ─── TABS config ──────────────────────────────────────────────────────────────
const TABS = [
  { id: "ruta",     label: "Ruta Hoy",  icon: MapPin   },
  { id: "semanal",  label: "Semanal",   icon: Calendar },
  { id: "mensual",  label: "Mensual",   icon: BarChart3 },
  { id: "clientes", label: "Clientes",  icon: Users    },
];

const ESTADO_STYLE = {
  pagada:    { bg: "bg-green-100",  text: "text-green-700",  label: "Pagada",    Icon: CheckCircle },
  pendiente: { bg: "bg-amber-50",   text: "text-amber-700",  label: "Pendiente", Icon: Clock },
  vencida:   { bg: "bg-red-100",    text: "text-red-700",    label: "Vencida",   Icon: AlertTriangle },
};

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Cartera() {
  const { token } = useAuth();
  const [tab, setTab] = useState("ruta");
  const [rutaHoy, setRutaHoy] = useState(null);
  const [semanal, setSemanal] = useState(null);
  const [mensual, setMensual] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPago, setSelectedPago] = useState(null);
  const [clienteSearch, setClienteSearch] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [weekDate, setWeekDate] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));

  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  const weekKey = () => `${format(weekDate, "yyyy")}-W${format(weekDate, "II")}`;

  const fetchRutaHoy = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/cartera/ruta-hoy`, authHeaders);
      setRutaHoy(res.data);
    } catch { toast.error("Error cargando la ruta de hoy"); }
    finally { setLoading(false); }
  }, [token]);

  const fetchSemanal = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/cartera/semanal`, {
        ...authHeaders, params: { semana: weekKey() },
      });
      setSemanal(res.data);
    } catch { toast.error("Error cargando cartera semanal"); }
    finally { setLoading(false); }
  }, [token, weekDate]);

  const fetchMensual = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/cartera/mensual`, {
        ...authHeaders, params: { ano: year },
      });
      setMensual(res.data);
    } catch {} finally { setLoading(false); }
  }, [token, year]);

  const fetchClientes = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/cartera/clientes`, authHeaders);
      setClientes(res.data || []);
    } catch {}
  }, [token]);

  useEffect(() => { if (tab === "ruta")     fetchRutaHoy(); }, [tab, fetchRutaHoy]);
  useEffect(() => { if (tab === "semanal")  fetchSemanal(); }, [tab, fetchSemanal]);
  useEffect(() => { if (tab === "mensual")  fetchMensual(); }, [tab, fetchMensual]);
  useEffect(() => { if (tab === "clientes") fetchClientes(); }, [tab, fetchClientes]);

  const refresh = () => {
    if (tab === "ruta") fetchRutaHoy();
    else if (tab === "semanal") fetchSemanal();
    else if (tab === "mensual") fetchMensual();
    else fetchClientes();
  };

  // Derived data
  const ruta = rutaHoy?.ruta || [];
  const resumenRuta = rutaHoy?.resumen || {};
  const vencidas = ruta.filter((c) => c.dias_vencida > 0);
  const paraHoy = ruta.filter((c) => c.dias_vencida === 0);
  const cobradoPct =
    resumenRuta.total_esperado > 0
      ? Math.min(100, Math.round((resumenRuta.cobrado_hoy || 0) / resumenRuta.total_esperado * 100))
      : 0;

  const resumenSem = semanal?.resumen || {};
  const cuotasSem = semanal?.cuotas || [];
  const filteredClientes = clientes.filter((c) =>
    c.cliente_nombre.toLowerCase().includes(clienteSearch.toLowerCase())
  );

  return (
    <div className="-m-4 lg:-m-6 min-h-screen bg-slate-50">
      <style>{`
        @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
      `}</style>

      {/* ──────────────────── Dark Header ──────────────────── */}
      <div className="bg-[#0f172a] text-white px-5 pt-5 pb-4">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00C853] to-[#009a3e] flex items-center justify-center flex-shrink-0">
                <Wallet size={20} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white leading-tight">Cartera Cobrador</h1>
                <p className="text-xs text-slate-400">
                  {format(new Date(), "EEEE, d 'de' MMMM yyyy", { locale: es })}
                </p>
              </div>
            </div>
            <button
              onClick={refresh}
              disabled={loading}
              data-testid="refresh-btn"
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            </button>
          </div>

          {/* Stats strip — Ruta de Hoy */}
          {tab === "ruta" && rutaHoy && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-5 text-sm flex-wrap">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-400" />
                  <span className="text-slate-300">
                    <span className="font-bold text-white">{resumenRuta.vencidas}</span> vencidas
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-slate-300">
                    <span className="font-bold text-white">{resumenRuta.para_hoy}</span> hoy
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-slate-300">
                    <span className="font-bold text-green-400">{fmt(resumenRuta.cobrado_hoy)}</span> cobrado
                  </span>
                </div>
              </div>
              {resumenRuta.total_esperado > 0 && (
                <div>
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>Meta del día: {fmt(resumenRuta.total_esperado)}</span>
                    <span className="font-semibold text-green-400">{cobradoPct}%</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-gradient-to-r from-[#00C853] to-[#00E5FF] transition-all duration-700"
                      style={{ width: `${cobradoPct}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Stats strip — Semanal */}
          {tab === "semanal" && semanal && (
            <div className="mt-3 flex gap-5 text-sm flex-wrap">
              <span className="text-slate-300">
                Cobrado: <span className="font-bold text-green-400">{fmt(resumenSem.total_cobrado)}</span>
              </span>
              <span className="text-slate-300">
                Pendiente: <span className="font-bold text-amber-400">{fmt(resumenSem.total_pendiente)}</span>
              </span>
              <span className="text-slate-300">
                Tasa: <span className={`font-bold ${resumenSem.tasa_cobro_pct >= 80 ? "text-green-400" : "text-amber-400"}`}>
                  {resumenSem.tasa_cobro_pct}%
                </span>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ──────────────────── Tab Bar ──────────────────── */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-2xl mx-auto flex">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`tab-${t.id}`}
              className={`flex-1 flex flex-col items-center gap-0.5 py-3 text-xs font-semibold transition-all ${
                tab === t.id
                  ? "text-[#00C853] border-b-2 border-[#00C853]"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <t.icon size={16} />
              <span className="hidden sm:block">{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ──────────────────── Content ──────────────────── */}
      <div className="max-w-2xl mx-auto px-4 pt-4 pb-10">

        {/* ── RUTA DE HOY ── */}
        {tab === "ruta" && (
          <div className="space-y-4" data-testid="ruta-hoy-view">
            {loading ? (
              <div className="text-center py-16">
                <RefreshCw size={28} className="animate-spin mx-auto mb-3 text-slate-300" />
                <p className="text-sm text-slate-400">Cargando ruta...</p>
              </div>
            ) : ruta.length === 0 ? (
              <div className="bg-white rounded-2xl p-10 text-center shadow-sm">
                <CheckCircle size={44} className="text-green-400 mx-auto mb-3" />
                <h3 className="font-bold text-slate-800 text-lg">¡Ruta al día!</h3>
                <p className="text-slate-500 text-sm mt-1">
                  No hay cuotas vencidas ni para cobrar hoy
                </p>
              </div>
            ) : (
              <>
                {/* Vencidas */}
                {vencidas.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 px-1">
                      <AlertTriangle size={14} className="text-red-500" />
                      <h2 className="text-xs font-bold text-red-600 uppercase tracking-widest">
                        Vencidas ({vencidas.length})
                      </h2>
                    </div>
                    {vencidas.map((c, i) => (
                      <CuotaCard key={`v-${i}`} cuota={c} onPay={setSelectedPago} />
                    ))}
                  </div>
                )}

                {/* Para hoy */}
                {paraHoy.length > 0 && (
                  <div className="space-y-3 mt-2">
                    <div className="flex items-center gap-2 px-1">
                      <Clock size={14} className="text-amber-500" />
                      <h2 className="text-xs font-bold text-amber-600 uppercase tracking-widest">
                        Para hoy ({paraHoy.length})
                      </h2>
                    </div>
                    {paraHoy.map((c, i) => (
                      <CuotaCard key={`h-${i}`} cuota={c} onPay={setSelectedPago} />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── SEMANAL ── */}
        {tab === "semanal" && (
          <div className="space-y-4" data-testid="semanal-view">
            {/* Week navigator */}
            <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center justify-between">
              <button
                onClick={() => setWeekDate((prev) => subWeeks(prev, 1))}
                className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"
              >
                <ChevronLeft size={18} />
              </button>
              <div className="text-center">
                <p className="font-bold text-slate-800 text-sm">{semanal?.semana_label || "Cargando..."}</p>
                <p className="text-xs text-slate-400">{weekKey()}</p>
              </div>
              <button
                onClick={() => setWeekDate((prev) => addWeeks(prev, 1))}
                className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"
              >
                <ChevronRight size={18} />
              </button>
            </div>

            {/* Stats grid (compact mobile) */}
            {semanal && (
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Esperado", val: fmt(resumenSem.total_esperado), sub: `${resumenSem.total_cuotas} cuotas`, color: "text-slate-800" },
                  { label: "Cobrado", val: fmt(resumenSem.total_cobrado), sub: `${resumenSem.cuotas_pagadas} pagadas`, color: "text-green-600" },
                  { label: "Pendiente", val: fmt(resumenSem.total_pendiente), sub: `${resumenSem.cuotas_pendientes} cuotas`, color: "text-amber-600" },
                  {
                    label: "Tasa cobro",
                    val: `${resumenSem.tasa_cobro_pct}%`,
                    sub: resumenSem.total_vencido > 0 ? `${fmt(resumenSem.total_vencido)} vencido` : "al día",
                    color: resumenSem.tasa_cobro_pct >= 80 ? "text-green-600" : resumenSem.tasa_cobro_pct >= 60 ? "text-amber-600" : "text-red-500",
                  },
                ].map((kpi) => (
                  <div key={kpi.label} className="bg-white rounded-xl border border-slate-100 p-3 shadow-sm">
                    <p className="text-xs text-slate-400">{kpi.label}</p>
                    <p className={`text-base font-bold mt-0.5 ${kpi.color}`}>{kpi.val}</p>
                    <p className="text-xs text-slate-400">{kpi.sub}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Cuotas list */}
            <div className="space-y-2">
              {loading ? (
                <div className="text-center py-8 text-slate-400 text-sm">Cargando...</div>
              ) : cuotasSem.length === 0 ? (
                <div className="bg-white rounded-xl p-8 text-center text-slate-400 text-sm shadow-sm">
                  No hay cuotas para esta semana
                </div>
              ) : cuotasSem.map((c, idx) => {
                const st = ESTADO_STYLE[c.estado] || ESTADO_STYLE.pendiente;
                return (
                  <div
                    key={idx}
                    className="bg-white rounded-xl shadow-sm border border-slate-100 p-3"
                    data-testid={`semanal-row-${idx}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-slate-800 text-sm truncate">{c.cliente_nombre}</p>
                        <p className="text-xs text-slate-400 truncate">{c.moto}</p>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          <span className="font-mono text-xs text-[#00A9E0]">{c.codigo}</span>
                          <span className="text-xs text-slate-400">C.{c.cuota_numero}/{c.total_cuotas}</span>
                          <span className="text-xs text-slate-400">Vence: {fdate(c.fecha_vencimiento)}</span>
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="font-bold text-slate-800">{fmt(c.valor)}</p>
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${st.bg} ${st.text}`}>
                          <st.Icon size={10} />{st.label}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-2">
                      {c.estado !== "pagada" && (
                        <button
                          onClick={() => setSelectedPago(c)}
                          className="flex-1 py-2 bg-[#00A9E0] text-white rounded-lg text-xs font-semibold hover:bg-[#0090c0] transition-colors"
                        >
                          Registrar Cobro
                        </button>
                      )}
                      {c.estado === "pagada" && c.comprobante && (
                        <button
                          onClick={() => generateReceipt(c)}
                          className="flex-1 py-2 border border-slate-200 text-slate-500 rounded-lg text-xs flex items-center justify-center gap-1 hover:bg-slate-50"
                        >
                          <Download size={12} /> Recibo
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── MENSUAL ── */}
        {tab === "mensual" && (
          <div className="space-y-4" data-testid="mensual-view">
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-slate-600">Año:</label>
              <select
                value={year}
                onChange={(e) => setYear(parseInt(e.target.value))}
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                {[2025, 2026, 2027].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Mes</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Esperado</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Cobrado</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase hidden sm:table-cell">Vencido</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Tasa</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-400 text-sm">Cargando...</td></tr>
                  ) : (mensual?.meses || []).map((m) => (
                    <tr
                      key={m.mes}
                      className={`hover:bg-slate-50 ${m.num_cuotas === 0 ? "opacity-40" : ""}`}
                      data-testid={`mensual-row-${m.mes}`}
                    >
                      <td className="px-3 py-2.5 font-semibold text-slate-800">{m.mes_nombre}</td>
                      <td className="px-3 py-2.5 text-right text-slate-600 text-xs">{fmt(m.esperado)}</td>
                      <td className="px-3 py-2.5 text-right font-semibold text-green-600 text-xs">{fmt(m.cobrado)}</td>
                      <td className="px-3 py-2.5 text-right text-red-500 text-xs hidden sm:table-cell">
                        {m.vencido > 0 ? fmt(m.vencido) : "—"}
                      </td>
                      <td className="px-3 py-2.5">
                        {m.num_cuotas > 0 ? (
                          <div className="flex items-center gap-1.5">
                            <div className="w-12 bg-slate-100 rounded-full h-1.5">
                              <div
                                className={`h-1.5 rounded-full ${m.tasa_cobro_pct >= 80 ? "bg-green-500" : m.tasa_cobro_pct >= 60 ? "bg-amber-400" : "bg-red-400"}`}
                                style={{ width: `${m.tasa_cobro_pct}%` }}
                              />
                            </div>
                            <span className={`text-xs font-bold ${m.tasa_cobro_pct >= 80 ? "text-green-600" : m.tasa_cobro_pct >= 60 ? "text-amber-600" : "text-red-500"}`}>
                              {m.tasa_cobro_pct}%
                            </span>
                          </div>
                        ) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
                {mensual?.meses && (
                  <tfoot className="bg-slate-50 border-t-2 border-slate-200">
                    <tr>
                      <td className="px-3 py-2.5 font-bold text-slate-800">Total {year}</td>
                      <td className="px-3 py-2.5 text-right font-bold text-slate-800 text-xs">
                        {fmt(mensual.meses.reduce((s, m) => s + m.esperado, 0))}
                      </td>
                      <td className="px-3 py-2.5 text-right font-bold text-green-600 text-xs">
                        {fmt(mensual.meses.reduce((s, m) => s + m.cobrado, 0))}
                      </td>
                      <td className="px-3 py-2.5 text-right font-bold text-red-500 text-xs hidden sm:table-cell">
                        {fmt(mensual.meses.reduce((s, m) => s + m.vencido, 0))}
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        )}

        {/* ── CLIENTES ── */}
        {tab === "clientes" && (
          <div className="space-y-4" data-testid="clientes-view">
            <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl px-3 py-2.5 shadow-sm">
              <Search size={15} className="text-slate-400 flex-shrink-0" />
              <input
                value={clienteSearch}
                onChange={(e) => setClienteSearch(e.target.value)}
                placeholder="Buscar cliente..."
                className="flex-1 text-sm outline-none bg-transparent"
                data-testid="cliente-search"
              />
              {clienteSearch && (
                <button onClick={() => setClienteSearch("")} className="text-slate-400 hover:text-slate-600">
                  <X size={14} />
                </button>
              )}
            </div>
            <p className="text-xs text-slate-400 px-1">
              {filteredClientes.length} cliente{filteredClientes.length !== 1 ? "s" : ""}
            </p>
            <div className="space-y-3">
              {filteredClientes.length === 0 ? (
                <div className="bg-white rounded-xl p-10 text-center text-slate-400 shadow-sm text-sm">
                  No hay clientes registrados
                </div>
              ) : filteredClientes.map((c, idx) => (
                <div
                  key={idx}
                  className="bg-white rounded-xl shadow-sm border border-slate-100 p-4"
                  data-testid={`cliente-row-${idx}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-slate-800 text-sm">{c.cliente_nombre}</h3>
                      {c.cliente_nit && <p className="text-xs text-slate-400">NIT: {c.cliente_nit}</p>}
                      <div className="flex gap-3 mt-1.5 text-xs flex-wrap">
                        <span className="text-slate-500">{c.num_creditos} crédito{c.num_creditos !== 1 ? "s" : ""}</span>
                        {c.pagadas_tiempo > 0 && <span className="text-green-600 font-medium">{c.pagadas_tiempo} a tiempo</span>}
                        {c.pagadas_tarde > 0 && <span className="text-amber-600">{c.pagadas_tarde} tarde</span>}
                        {c.vencidas > 0 && <span className="text-red-600 font-semibold">{c.vencidas} vencidas</span>}
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-bold text-red-500">{fmt(c.saldo_pendiente)}</p>
                      <p className="text-xs text-slate-400">saldo</p>
                      <p className="text-xs text-green-600 font-medium">{fmt(c.total_cobrado)} cobrado</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                      <span>{c.categoria_pago}</span>
                    </div>
                    <ScoreBar score={c.score_pago} color={c.score_color} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ──────────────────── Payment Bottom Sheet ──────────────────── */}
      {selectedPago && (
        <PagoBottomSheet
          cuota={selectedPago}
          onClose={() => setSelectedPago(null)}
          onSuccess={() => {
            setSelectedPago(null);
            if (tab === "ruta") fetchRutaHoy();
            else fetchSemanal();
          }}
        />
      )}
    </div>
  );
}
