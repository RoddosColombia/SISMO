import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import { format, parseISO, addWeeks, subWeeks, startOfWeek } from "date-fns";
import { es } from "date-fns/locale";
import {
  Wallet, ChevronLeft, ChevronRight, BarChart3, Users, CheckCircle,
  AlertTriangle, Clock, Download, X, TrendingUp, TrendingDown, RefreshCw, Calendar,
} from "lucide-react";
import { toast } from "sonner";
import jsPDF from "jspdf";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (n) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
const fdate = (d) => { try { return format(parseISO(d), "dd/MMM", { locale: es }); } catch { return d || "—"; } };

const ESTADO_STYLE = {
  pagada:    { bg: "bg-green-100",  text: "text-green-700",  label: "Pagada",    icon: CheckCircle },
  pendiente: { bg: "bg-amber-50",   text: "text-amber-700",  label: "Pendiente", icon: Clock },
  vencida:   { bg: "bg-red-100",    text: "text-red-700",    label: "Vencida",   icon: AlertTriangle },
};

const ScoreBar = ({ score, color }) => {
  const colors = { green: "bg-green-500", yellow: "bg-yellow-400", orange: "bg-orange-400", red: "bg-red-500" };
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-100 rounded-full h-2 min-w-20">
        <div className={`h-2 rounded-full ${colors[color] || "bg-slate-400"}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-bold text-slate-700 w-10">{score}%</span>
    </div>
  );
};

// ─── Receipt Generator ────────────────────────────────────────────────────────
function generateReceipt(cuota) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: [80, 120] });
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("RODDOS S.A.S.", 40, 8, { align: "center" });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  doc.text("Concesionario Auteco", 40, 12, { align: "center" });
  doc.setLineWidth(0.3);
  doc.line(4, 15, 76, 15);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.text("COMPROBANTE DE PAGO", 40, 20, { align: "center" });
  if (cuota.comprobante) doc.text(cuota.comprobante, 40, 25, { align: "center" });
  doc.line(4, 28, 76, 28);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  const rows = [
    ["Cliente:", cuota.cliente_nombre || ""],
    ["Plan:", cuota.plan || ""],
    ["Código crédito:", cuota.codigo || ""],
    ["Cuota N°:", `${cuota.cuota_numero} / ${cuota.total_cuotas}`],
    ["Vencimiento:", cuota.fecha_vencimiento || ""],
    ["Fecha pago:", cuota.fecha_pago || ""],
    ["Método:", cuota.metodo_pago || "efectivo"],
  ];
  let y = 33;
  for (const [k, v] of rows) {
    doc.setFont("helvetica", "bold");
    doc.text(k, 5, y);
    doc.setFont("helvetica", "normal");
    doc.text(String(v).slice(0, 35), 30, y);
    y += 5;
  }
  doc.line(4, y, 76, y); y += 5;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text(fmt(cuota.valor_pagado || cuota.valor), 40, y + 4, { align: "center" });
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.text("Gracias por su pago puntual", 40, y + 11, { align: "center" });
  doc.save(`${cuota.comprobante || "recibo"}.pdf`);
}

// ─── Pago Modal (inline from Cartera) ─────────────────────────────────────────
const PagoModal = ({ cuota, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [form, setForm] = useState({ valor_pagado: cuota.valor, metodo_pago: "efectivo", notas: "" });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/api/loanbook/${cuota.loanbook_id}/pago`,
        { cuota_numero: cuota.cuota_numero, ...form, valor_pagado: parseFloat(form.valor_pagado) },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Pago registrado — ${cuota.cliente_nombre}`);
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando el pago");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b">
          <div>
            <h3 className="font-bold text-slate-800">Registrar Cobro</h3>
            <p className="text-sm text-slate-500">{cuota.cliente_nombre} · Cuota {cuota.cuota_numero} · {cuota.plan}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="bg-amber-50 rounded-lg p-3 text-sm space-y-1">
            <p className="font-semibold text-amber-800">Vence: {cuota.fecha_vencimiento}</p>
            <p className="text-amber-700">Moto: {cuota.moto || "—"}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Valor recibido</label>
            <input type="number" value={form.valor_pagado} onChange={e => setForm(f => ({ ...f, valor_pagado: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#00A9E0] focus:border-transparent" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Método de pago</label>
            <select value={form.metodo_pago} onChange={e => setForm(f => ({ ...f, metodo_pago: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
              <option value="efectivo">Efectivo</option>
              <option value="transferencia">Transferencia</option>
              <option value="tarjeta">Tarjeta</option>
              <option value="nequi">Nequi / Daviplata</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Notas</label>
            <input type="text" value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
              placeholder="Observaciones..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium">Cancelar</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0] disabled:opacity-50">
              {loading ? "Procesando..." : "Confirmar Cobro"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Cartera() {
  const { token } = useAuth();
  const [tab, setTab] = useState("semanal");
  const [weekDate, setWeekDate] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [semanal, setSemanal] = useState(null);
  const [mensual, setMensual] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPago, setSelectedPago] = useState(null);
  const [clienteSearch, setClienteSearch] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());

  const weekKey = () => {
    const iso = format(weekDate, "yyyy");
    const week = format(weekDate, "II");
    return `${iso}-W${week}`;
  };

  const fetchSemanal = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/cartera/semanal`,
        { headers: { Authorization: `Bearer ${token}` }, params: { semana: weekKey() } });
      setSemanal(res.data);
    } catch { toast.error("Error cargando cartera semanal"); }
    finally { setLoading(false); }
  }, [token, weekDate]);

  const fetchMensual = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/cartera/mensual`, { headers: { Authorization: `Bearer ${token}` }, params: { ano: year } });
      setMensual(res.data);
    } catch {} finally { setLoading(false); }
  }, [token, year]);

  const fetchClientes = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/cartera/clientes`, { headers: { Authorization: `Bearer ${token}` } });
      setClientes(res.data || []);
    } catch {}
  }, [token]);

  useEffect(() => { if (tab === "semanal") fetchSemanal(); }, [tab, fetchSemanal]);
  useEffect(() => { if (tab === "mensual") fetchMensual(); }, [tab, fetchMensual]);
  useEffect(() => { if (tab === "clientes") fetchClientes(); }, [tab, fetchClientes]);

  const resumen = semanal?.resumen || {};
  const cuotas = semanal?.cuotas || [];

  const filteredClientes = clientes.filter(c =>
    c.cliente_nombre.toLowerCase().includes(clienteSearch.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00C853] to-[#009a3e] flex items-center justify-center">
            <Wallet size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Cartera</h1>
            <p className="text-sm text-slate-500">Control de cobros semanales y comportamiento de clientes</p>
          </div>
        </div>
        <button onClick={() => { if (tab === "semanal") fetchSemanal(); else if (tab === "mensual") fetchMensual(); else fetchClientes(); }}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500"><RefreshCw size={16} /></button>
      </div>

      {/* Stats row (semanal) */}
      {tab === "semanal" && semanal && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Esperado semana</p>
            <p className="text-xl font-bold text-slate-800 mt-1">{fmt(resumen.total_esperado)}</p>
            <p className="text-xs text-slate-400">{resumen.total_cuotas} cuotas</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Cobrado</p>
            <p className="text-xl font-bold text-green-600 mt-1">{fmt(resumen.total_cobrado)}</p>
            <p className="text-xs text-green-500">{resumen.cuotas_pagadas} cuotas pagadas</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Por cobrar</p>
            <p className="text-xl font-bold text-amber-600 mt-1">{fmt(resumen.total_pendiente)}</p>
            <p className="text-xs text-amber-500">{resumen.cuotas_pendientes} pendientes</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Tasa de cobro</p>
              {resumen.total_vencido > 0 && <span className="text-xs text-red-500 font-semibold">{fmt(resumen.total_vencido)} vencido</span>}
            </div>
            <p className={`text-xl font-bold mt-1 ${resumen.tasa_cobro_pct >= 80 ? "text-green-600" : resumen.tasa_cobro_pct >= 60 ? "text-amber-600" : "text-red-500"}`}>
              {resumen.tasa_cobro_pct}%
            </p>
            <div className="w-full bg-slate-100 rounded-full h-1.5 mt-1.5">
              <div className={`h-1.5 rounded-full ${resumen.tasa_cobro_pct >= 80 ? "bg-green-500" : resumen.tasa_cobro_pct >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                style={{ width: `${resumen.tasa_cobro_pct || 0}%` }} />
            </div>
          </div>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
        {[
          { id: "semanal", label: "Vista Semanal", icon: Calendar },
          { id: "mensual", label: "Resumen Mensual", icon: BarChart3 },
          { id: "clientes", label: "Clientes", icon: Users },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === t.id ? "bg-white shadow text-slate-800" : "text-slate-500 hover:text-slate-700"}`}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {/* SEMANAL TAB */}
      {tab === "semanal" && (
        <div className="space-y-4">
          {/* Week Navigator */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center justify-between">
            <button onClick={() => setWeekDate(prev => subWeeks(prev, 1))}
              className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"><ChevronLeft size={18} /></button>
            <div className="text-center">
              <p className="font-bold text-slate-800 text-base">{semanal?.semana_label || "Cargando..."}</p>
              <p className="text-xs text-slate-400">{weekKey()}</p>
            </div>
            <button onClick={() => setWeekDate(prev => addWeeks(prev, 1))}
              className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"><ChevronRight size={18} /></button>
          </div>

          {/* Cuotas Table */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cliente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Crédito</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase hidden md:table-cell">Plan</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cuota</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Vence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Valor</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Estado</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-400">Cargando...</td></tr>
                ) : cuotas.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-400">No hay cuotas para esta semana</td></tr>
                ) : cuotas.map((c, idx) => {
                  const st = ESTADO_STYLE[c.estado] || ESTADO_STYLE.pendiente;
                  const SIcon = st.icon;
                  return (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors" data-testid={`cartera-row-${idx}`}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-800">{c.cliente_nombre}</p>
                        <p className="text-xs text-slate-400 hidden sm:block">{c.moto}</p>
                      </td>
                      <td className="px-4 py-3"><span className="font-mono text-xs text-[#00A9E0]">{c.codigo}</span></td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">{c.plan}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{c.cuota_numero}/{c.total_cuotas}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{fdate(c.fecha_vencimiento)}</td>
                      <td className="px-4 py-3 font-semibold text-slate-800">{fmt(c.valor)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${st.bg} ${st.text}`}>
                          <SIcon size={10} />{st.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          {c.estado !== "pagada" && (
                            <button onClick={() => setSelectedPago(c)}
                              className="px-2.5 py-1 text-xs bg-[#00A9E0] text-white rounded-lg hover:bg-[#0090c0] font-medium">
                              Registrar
                            </button>
                          )}
                          {c.estado === "pagada" && c.comprobante && (
                            <button onClick={() => generateReceipt(c)}
                              className="p-1.5 text-slate-400 hover:text-[#00A9E0] hover:bg-slate-100 rounded-lg">
                              <Download size={13} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MENSUAL TAB */}
      {tab === "mensual" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-slate-600">Año:</label>
            <select value={year} onChange={e => setYear(parseInt(e.target.value))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm">
              {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Mes</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Esperado</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Cobrado</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Vencido</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Tasa cobro</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Cuotas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400">Cargando...</td></tr>
                ) : (mensual?.meses || []).map(m => (
                  <tr key={m.mes} className={`hover:bg-slate-50 ${m.num_cuotas === 0 ? "opacity-40" : ""}`} data-testid={`mensual-row-${m.mes}`}>
                    <td className="px-4 py-3 font-semibold text-slate-800">{m.mes_nombre}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{fmt(m.esperado)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-green-600">{fmt(m.cobrado)}</td>
                    <td className="px-4 py-3 text-right text-red-500">{m.vencido > 0 ? fmt(m.vencido) : "—"}</td>
                    <td className="px-4 py-3">
                      {m.num_cuotas > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-slate-100 rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${m.tasa_cobro_pct >= 80 ? "bg-green-500" : m.tasa_cobro_pct >= 60 ? "bg-amber-400" : "bg-red-400"}`}
                              style={{ width: `${m.tasa_cobro_pct}%` }} />
                          </div>
                          <span className={`text-xs font-bold ${m.tasa_cobro_pct >= 80 ? "text-green-600" : m.tasa_cobro_pct >= 60 ? "text-amber-600" : "text-red-500"}`}>
                            {m.tasa_cobro_pct}%
                          </span>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-slate-500">{m.num_pagadas}/{m.num_cuotas}</td>
                  </tr>
                ))}
              </tbody>
              {mensual?.meses && (
                <tfoot className="bg-slate-50 border-t-2 border-slate-200">
                  <tr>
                    <td className="px-4 py-3 font-bold text-slate-800">Total {year}</td>
                    <td className="px-4 py-3 text-right font-bold text-slate-800">{fmt(mensual.meses.reduce((s, m) => s + m.esperado, 0))}</td>
                    <td className="px-4 py-3 text-right font-bold text-green-600">{fmt(mensual.meses.reduce((s, m) => s + m.cobrado, 0))}</td>
                    <td className="px-4 py-3 text-right font-bold text-red-500">{fmt(mensual.meses.reduce((s, m) => s + m.vencido, 0))}</td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3 text-center font-bold text-slate-700">{mensual.meses.reduce((s, m) => s + m.num_pagadas, 0)}/{mensual.meses.reduce((s, m) => s + m.num_cuotas, 0)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}

      {/* CLIENTES TAB */}
      {tab === "clientes" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 flex items-center gap-2 border border-slate-300 rounded-lg px-3 py-2 max-w-80">
              <Users size={14} className="text-slate-400" />
              <input value={clienteSearch} onChange={e => setClienteSearch(e.target.value)}
                placeholder="Buscar cliente..." className="flex-1 text-sm outline-none bg-transparent" />
            </div>
            <span className="text-sm text-slate-400">{filteredClientes.length} cliente{filteredClientes.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cliente</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Créditos</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Cobrado</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Saldo</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Pagadas a tiempo</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Tardías</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Vencidas</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredClientes.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-400">No hay clientes registrados</td></tr>
                ) : filteredClientes.map((c, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors" data-testid={`cliente-row-${idx}`}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800">{c.cliente_nombre}</p>
                      {c.cliente_nit && <p className="text-xs text-slate-400">NIT: {c.cliente_nit}</p>}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-600">{c.num_creditos}</td>
                    <td className="px-4 py-3 text-right font-semibold text-green-600">{fmt(c.total_cobrado)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-red-500">{fmt(c.saldo_pendiente)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-xs font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded-full">{c.pagadas_tiempo}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {c.pagadas_tarde > 0 ? <span className="text-xs font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">{c.pagadas_tarde}</span> : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {c.vencidas > 0 ? <span className="text-xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-full">{c.vencidas}</span> : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3 min-w-32">
                      <div className="space-y-1">
                        <ScoreBar score={c.score_pago} color={c.score_color} />
                        <span className={`text-xs font-medium ${c.score_color === "green" ? "text-green-600" : c.score_color === "yellow" ? "text-yellow-600" : c.score_color === "orange" ? "text-orange-500" : "text-red-500"}`}>
                          {c.categoria_pago}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedPago && (
        <PagoModal cuota={selectedPago} onClose={() => setSelectedPago(null)}
          onSuccess={() => { setSelectedPago(null); fetchSemanal(); }} />
      )}
    </div>
  );
}
