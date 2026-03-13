import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import {
  BookOpen, Plus, Search, Filter, ChevronRight, ChevronDown, Calendar,
  CheckCircle, Clock, AlertTriangle, XCircle, Truck, DollarSign,
  Edit3, X, TrendingUp, Users, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (n) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
const fdate = (d) => { try { return format(parseISO(d), "dd/MMM/yy", { locale: es }); } catch { return d || "—"; } };

const PLAN_COLORS = {
  Contado:  "bg-emerald-100 text-emerald-700",
  P39S:     "bg-blue-100 text-blue-700",
  P52S:     "bg-violet-100 text-violet-700",
  P78S:     "bg-orange-100 text-orange-700",
};
const ESTADO_INFO = {
  activo:            { icon: CheckCircle,    color: "text-green-600",  bg: "bg-green-50",  label: "Activo" },
  mora:              { icon: AlertTriangle,  color: "text-red-600",    bg: "bg-red-50",    label: "En Mora" },
  completado:        { icon: CheckCircle,    color: "text-slate-400",  bg: "bg-slate-50",  label: "Completado" },
  pendiente_entrega: { icon: Truck,          color: "text-amber-600",  bg: "bg-amber-50",  label: "Sin Entrega" },
  cancelado:         { icon: XCircle,        color: "text-slate-400",  bg: "bg-slate-50",  label: "Cancelado" },
};

// ─── Stat Card ────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, icon: Icon, color = "text-[#00A9E0]", sub }) => (
  <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 flex items-start gap-4">
    <div className={`p-2.5 rounded-lg bg-slate-50 ${color}`}><Icon size={20} /></div>
    <div>
      <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold text-slate-800 mt-0.5">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  </div>
);

// ─── Payment Modal ────────────────────────────────────────────────────────────
const PagoModal = ({ loan, cuota, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [form, setForm] = useState({ valor_pagado: cuota.valor, metodo_pago: "efectivo", notas: "" });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/api/loanbook/${loan.id}/pago`,
        { cuota_numero: cuota.numero, ...form, valor_pagado: parseFloat(form.valor_pagado) },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Cuota ${cuota.numero} registrada exitosamente`);
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando el pago");
    } finally {
      setLoading(false);
    }
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
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Valor recibido</label>
            <input type="number" value={form.valor_pagado} onChange={e => setForm(f => ({ ...f, valor_pagado: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#00A9E0] focus:border-transparent" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Método de pago</label>
            <select value={form.metodo_pago} onChange={e => setForm(f => ({ ...f, metodo_pago: e.target.value }))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#00A9E0]">
              <option value="efectivo">Efectivo</option>
              <option value="transferencia">Transferencia</option>
              <option value="tarjeta">Tarjeta</option>
              <option value="nequi">Nequi / Daviplata</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Notas (opcional)</label>
            <input type="text" value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
              placeholder="Observaciones del pago" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50">Cancelar</button>
            <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0] disabled:opacity-50">
              {loading ? "Procesando..." : "Confirmar Pago"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Loan Detail Panel ────────────────────────────────────────────────────────
const LoanDetail = ({ loan, onClose, onRefresh }) => {
  const { token } = useAuth();
  const [selectedCuota, setSelectedCuota] = useState(null);
  const [editCuota, setEditCuota] = useState(null);
  const [editVal, setEditVal] = useState("");
  const [entregaDate, setEntregaDate] = useState("");
  const [showEntrega, setShowEntrega] = useState(false);
  const [loadingEntrega, setLoadingEntrega] = useState(false);

  const cuotas = loan.cuotas || [];
  const pct = loan.num_cuotas > 0 ? Math.round((loan.num_cuotas_pagadas / (loan.num_cuotas + 1)) * 100) : 0;

  const handleEntrega = async () => {
    if (!entregaDate) return;
    setLoadingEntrega(true);
    try {
      await axios.put(`${API}/api/loanbook/${loan.id}/entrega`, { fecha_entrega: entregaDate },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Fecha de entrega registrada. Cronograma generado.");
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando entrega");
    } finally {
      setLoadingEntrega(false); setShowEntrega(false);
    }
  };

  const handleEditCuota = async (cuota) => {
    const newVal = parseFloat(editVal);
    if (isNaN(newVal) || newVal <= 0) { toast.error("Valor inválido"); return; }
    try {
      await axios.put(`${API}/api/loanbook/${loan.id}/cuota/${cuota.numero}`, { valor: newVal },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Cuota actualizada");
      setEditCuota(null);
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error editando cuota");
    }
  };

  const estadoIcon = { pagada: "✅", pendiente: "⏳", vencida: "🔴", parcial: "🟡" };

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
          </div>
          <button onClick={onClose} className="text-slate-300 hover:text-white mt-1"><X size={22} /></button>
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
        </div>

        {/* Delivery */}
        {loan.plan !== "Contado" && (
          <div className="px-5 py-3 border-b bg-slate-50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Fecha de entrega</p>
                <p className="font-semibold text-slate-800">{loan.fecha_entrega ? fdate(loan.fecha_entrega) : <span className="text-amber-600">Sin registrar</span>}</p>
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
                <button onClick={() => setShowEntrega(false)} className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm text-slate-600">X</button>
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
                ${c.estado === "pagada" ? "bg-green-50 border-green-200" : c.estado === "vencida" ? "bg-red-50 border-red-200" : "bg-white border-slate-200"}`}>
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
                          <button onClick={() => { setEditCuota(c.numero); setEditVal(c.valor); }}
                            className="text-slate-300 hover:text-[#00A9E0] transition-colors"><Edit3 size={11} /></button>
                        )}
                      </>
                    )}
                    {c.fecha_pago && <span className="text-xs text-green-600">Pagado {fdate(c.fecha_pago)}</span>}
                    {c.comprobante && <span className="text-xs text-slate-400">{c.comprobante}</span>}
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
              <p className="text-center text-slate-400 text-sm py-8">Registre la fecha de entrega para generar el cronograma de cuotas</p>
            )}
          </div>
        </div>
      </div>
      {selectedCuota && (
        <PagoModal loan={loan} cuota={selectedCuota} onClose={() => setSelectedCuota(null)}
          onSuccess={() => { setSelectedCuota(null); onRefresh(); }} />
      )}
    </div>
  );
};

// ─── Create Loan Modal ────────────────────────────────────────────────────────
const CreateLoanModal = ({ onClose, onSuccess }) => {
  const { token } = useAuth();
  const [form, setForm] = useState({
    factura_alegra_id: "", factura_numero: "", moto_descripcion: "",
    cliente_id: "", cliente_nombre: "", cliente_nit: "", cliente_telefono: "",
    plan: "P52S", fecha_factura: new Date().toISOString().split("T")[0],
    precio_venta: "", cuota_inicial: "", valor_cuota: "",
  });
  const [loading, setLoading] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [contactSearch, setContactSearch] = useState("");
  const [aiSuggestion, setAiSuggestion] = useState(null);

  useEffect(() => {
    axios.get(`${API}/api/alegra/contacts`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setContacts(r.data || [])).catch(() => {});
  }, [token]);

  // Suggest cuota when price+plan changes
  useEffect(() => {
    if (!form.precio_venta || !form.plan || form.plan === "Contado") return;
    axios.get(`${API}/api/agent/memory`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        const patterns = (r.data || []).filter(p => p.tipo === "loanbook_pattern" && p.plan === form.plan);
        if (patterns.length > 0) {
          patterns.sort((a, b) => (b.frecuencia_count || 0) - (a.frecuencia_count || 0));
          const p = patterns[0];
          setAiSuggestion({ cuota: p.valor_cuota_tipico, inicial: p.cuota_inicial_tipica, frecuencia: p.frecuencia_count || 1 });
        }
      }).catch(() => {});
  }, [form.precio_venta, form.plan, token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/api/loanbook`, {
        ...form,
        precio_venta: parseFloat(form.precio_venta),
        cuota_inicial: parseFloat(form.cuota_inicial),
        valor_cuota: parseFloat(form.valor_cuota || 0),
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Plan de pagos creado exitosamente");
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error creando plan");
    } finally {
      setLoading(false);
    }
  };

  const filteredContacts = contacts.filter(c => c.name?.toLowerCase().includes(contactSearch.toLowerCase())).slice(0, 8);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white flex items-center justify-between p-5 border-b z-10">
          <h3 className="font-bold text-slate-800 flex items-center gap-2"><BookOpen size={18} className="text-[#00A9E0]" /> Nuevo Plan de Pagos</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">ID Factura Alegra *</label>
              <input required value={form.factura_alegra_id} onChange={e => setForm(f => ({ ...f, factura_alegra_id: e.target.value }))}
                placeholder="Ej: 12345" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Número factura</label>
              <input value={form.factura_numero} onChange={e => setForm(f => ({ ...f, factura_numero: e.target.value }))}
                placeholder="FAC-001" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Moto</label>
            <input value={form.moto_descripcion} onChange={e => setForm(f => ({ ...f, moto_descripcion: e.target.value }))}
              placeholder="Ej: Boxer 150 Azul Chasis: ABC123" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Cliente *</label>
            <input value={contactSearch} onChange={e => setContactSearch(e.target.value)}
              placeholder="Buscar cliente..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm mb-1" />
            {contactSearch && filteredContacts.length > 0 && (
              <div className="border border-slate-200 rounded-lg shadow-sm max-h-36 overflow-y-auto">
                {filteredContacts.map(c => (
                  <button key={c.id} type="button" onClick={() => {
                    setForm(f => ({ ...f, cliente_id: c.id, cliente_nombre: c.name, cliente_nit: c.identification || "" }));
                    setContactSearch(c.name);
                  }} className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-0">
                    <span className="font-medium">{c.name}</span>
                    {c.identification && <span className="text-slate-400 text-xs ml-2">NIT: {c.identification}</span>}
                  </button>
                ))}
              </div>
            )}
            {form.cliente_nombre && (
              <p className="text-xs text-green-600 mt-1">✓ {form.cliente_nombre} {form.cliente_nit && `· ${form.cliente_nit}`}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Plan *</label>
              <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="Contado">Contado</option>
                <option value="P39S">P39S — 39 semanas</option>
                <option value="P52S">P52S — 52 semanas</option>
                <option value="P78S">P78S — 78 semanas</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Fecha factura</label>
              <input type="date" value={form.fecha_factura} onChange={e => setForm(f => ({ ...f, fecha_factura: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Precio venta *</label>
              <input required type="number" value={form.precio_venta} onChange={e => setForm(f => ({ ...f, precio_venta: e.target.value }))}
                placeholder="3500000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Cuota inicial *</label>
              <input required type="number" value={form.cuota_inicial} onChange={e => setForm(f => ({ ...f, cuota_inicial: e.target.value }))}
                placeholder="500000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            {form.plan !== "Contado" && (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Valor cuota/sem *</label>
                <input required type="number" value={form.valor_cuota} onChange={e => setForm(f => ({ ...f, valor_cuota: e.target.value }))}
                  placeholder="90000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              </div>
            )}
          </div>
          {aiSuggestion && form.plan !== "Contado" && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
              <p className="font-semibold text-blue-700 mb-1">Sugerencia del Agente IA ({aiSuggestion.frecuencia} plan{aiSuggestion.frecuencia > 1 ? "es" : ""} similar{aiSuggestion.frecuencia > 1 ? "es" : ""})</p>
              <p className="text-blue-600">Cuota inicial típica: <strong>{fmt(aiSuggestion.inicial)}</strong> · Cuota semanal: <strong>{fmt(aiSuggestion.cuota)}</strong></p>
              <button type="button" onClick={() => setForm(f => ({ ...f, cuota_inicial: aiSuggestion.inicial, valor_cuota: aiSuggestion.cuota }))}
                className="mt-2 text-xs px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Usar sugerencia (verificar antes de confirmar)
              </button>
            </div>
          )}
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
  const [loans, setLoans] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedLoan, setSelectedLoan] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [filters, setFilters] = useState({ estado: "", plan: "", search: "" });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [loansRes, statsRes] = await Promise.all([
        axios.get(`${API}/api/loanbook`, { headers: { Authorization: `Bearer ${token}` }, params: { estado: filters.estado || undefined, plan: filters.plan || undefined, cliente: filters.search || undefined } }),
        axios.get(`${API}/api/loanbook/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setLoans(loansRes.data || []);
      setStats(statsRes.data || {});
    } catch (err) {
      toast.error("Error cargando Loanbook");
    } finally {
      setLoading(false);
    }
  }, [token, filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const refreshLoan = async (loanId) => {
    try {
      const res = await axios.get(`${API}/api/loanbook/${loanId}`, { headers: { Authorization: `Bearer ${token}` } });
      setLoans(prev => prev.map(l => l.id === loanId ? res.data : l));
      if (selectedLoan?.id === loanId) setSelectedLoan(res.data);
    } catch {}
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
          <button onClick={fetchData} className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500"><RefreshCw size={16} /></button>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0]">
            <Plus size={16} /> Nuevo Plan
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Créditos activos" value={stats.activos || 0} icon={Users} sub={`${stats.pendiente_entrega || 0} sin entrega`} />
        <StatCard label="Cartera activa" value={fmt(stats.total_cartera_activa)} icon={DollarSign} color="text-red-500" sub="saldo pendiente" />
        <StatCard label="Total cobrado" value={fmt(stats.total_cobrado_historico)} icon={TrendingUp} color="text-green-600" />
        <StatCard label="Cuotas esta semana" value={`${stats.cuotas_esta_semana || 0}`} icon={Calendar} color="text-amber-500" sub={fmt(stats.valor_esta_semana)} />
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 flex-1 min-w-52 border border-slate-300 rounded-lg px-3 py-2">
          <Search size={14} className="text-slate-400" />
          <input value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
            placeholder="Buscar cliente..." className="flex-1 text-sm outline-none bg-transparent" />
        </div>
        <select value={filters.plan} onChange={e => setFilters(f => ({ ...f, plan: e.target.value }))}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm min-w-36">
          <option value="">Todos los planes</option>
          <option value="Contado">Contado</option>
          <option value="P39S">P39S</option>
          <option value="P52S">P52S</option>
          <option value="P78S">P78S</option>
        </select>
        <select value={filters.estado} onChange={e => setFilters(f => ({ ...f, estado: e.target.value }))}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm min-w-36">
          <option value="">Todos los estados</option>
          <option value="activo">Activos</option>
          <option value="mora">En mora</option>
          <option value="pendiente_entrega">Sin entrega</option>
          <option value="completado">Completados</option>
        </select>
        {(filters.estado || filters.plan || filters.search) && (
          <button onClick={() => setFilters({ estado: "", plan: "", search: "" })} className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1"><X size={12} /> Limpiar</button>
        )}
        <span className="text-sm text-slate-400 ml-auto">{loans.length} resultado{loans.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
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
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
            ) : loans.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400">No hay planes de pago registrados</td></tr>
            ) : loans.map(loan => {
              const total = loan.num_cuotas + 1;
              const pct = total > 0 ? Math.round((loan.num_cuotas_pagadas / total) * 100) : 0;
              const info = ESTADO_INFO[loan.estado] || ESTADO_INFO.activo;
              const StateIcon = info.icon;
              return (
                <tr key={loan.id} className="hover:bg-slate-50 cursor-pointer transition-colors" onClick={() => setSelectedLoan(loan)} data-testid={`loan-row-${loan.id}`}>
                  <td className="px-4 py-3"><span className="font-mono text-xs font-semibold text-[#00A9E0]">{loan.codigo}</span></td>
                  <td className="px-4 py-3"><p className="font-medium text-slate-800 text-sm">{loan.cliente_nombre}</p><p className="text-xs text-slate-400">{loan.cliente_nit}</p></td>
                  <td className="px-4 py-3 hidden lg:table-cell"><p className="text-xs text-slate-500 max-w-36 truncate">{loan.moto_descripcion || "—"}</p></td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${PLAN_COLORS[loan.plan] || "bg-slate-100 text-slate-600"}`}>{loan.plan}</span></td>
                  <td className="px-4 py-3 hidden md:table-cell text-xs text-slate-500">{loan.fecha_entrega ? fdate(loan.fecha_entrega) : <span className="text-amber-500">Sin registrar</span>}</td>
                  <td className="px-4 py-3 min-w-36">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-slate-100 rounded-full h-1.5"><div className="bg-[#00A9E0] h-1.5 rounded-full" style={{ width: `${pct}%` }} /></div>
                      <span className="text-xs text-slate-500 w-12">{loan.num_cuotas_pagadas}/{total}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${info.bg} ${info.color}`}>
                      <StateIcon size={11} />{info.label}
                    </span>
                  </td>
                  <td className="px-4 py-3"><ChevronRight size={16} className="text-slate-300" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedLoan && (
        <LoanDetail loan={selectedLoan} onClose={() => setSelectedLoan(null)}
          onRefresh={() => refreshLoan(selectedLoan.id)} />
      )}
      {showCreate && <CreateLoanModal onClose={() => setShowCreate(false)} onSuccess={() => { setShowCreate(false); fetchData(); }} />}
    </div>
  );
}
