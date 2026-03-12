import React, { useState, useEffect, useCallback } from "react";
import { DollarSign, RefreshCw, CheckCircle2, Loader2, AlertCircle, CreditCard } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP, formatDate, todayStr } from "../utils/formatters";

function StatusBadge({ status }) {
  const map = {
    open: "bg-amber-100 text-amber-700 border-amber-200",
    overdue: "bg-red-100 text-red-700 border-red-200",
    paid: "bg-green-100 text-green-700 border-green-200",
  };
  const label = { open: "Pendiente", overdue: "Vencida", paid: "Pagada" };
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${map[status] || "bg-slate-100 text-slate-600 border-slate-200"}`}>
      {label[status] || status}
    </span>
  );
}

export default function RegistroCuotas() {
  const { api } = useAuth();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(null);
  const [payForm, setPayForm] = useState({ amount: "", date: todayStr(), bankAccountId: "", notes: "" });
  const [bankAccounts, setBankAccounts] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [invRes, bankRes] = await Promise.all([
        api.get("/alegra/invoices", { params: { status: "open" } }),
        api.get("/alegra/bank-accounts"),
      ]);
      const data = invRes.data;
      setInvoices(Array.isArray(data) ? data : []);
      setBankAccounts(Array.isArray(bankRes.data) ? bankRes.data : []);
    } catch {
      toast.error("Error cargando facturas");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { loadData(); }, [loadData]);

  const openPayModal = (inv) => {
    setPaying(inv);
    setPayForm({ amount: inv.total || inv.balance || "", date: todayStr(), bankAccountId: bankAccounts[0]?.id || "", notes: "" });
  };

  const handlePay = async () => {
    if (!payForm.amount || !payForm.date) { toast.error("Complete todos los campos"); return; }
    try {
      const payload = {
        date: payForm.date,
        invoices: [{ id: paying.id, amount: parseFloat(payForm.amount) }],
        bankAccount: { id: payForm.bankAccountId },
        observations: payForm.notes,
      };
      await api.post("/alegra/payments", payload);
      toast.success(`Pago de ${formatCOP(payForm.amount)} registrado en Alegra`);
      setPaying(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando pago");
    }
  };

  const totalPendiente = invoices.reduce((s, inv) => s + (inv.balance || inv.total || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Registro de Cuotas</h2>
          <p className="text-sm text-slate-500 mt-1">Facturas pendientes de cobro y registro de pagos</p>
        </div>
        <button onClick={loadData} disabled={loading} className="flex items-center gap-1.5 text-xs bg-white border border-slate-200 text-slate-600 px-3 py-2 rounded-lg hover:bg-slate-50">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Actualizar
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Total Pendiente</span>
          <div className="text-2xl font-bold text-red-600 mt-1">{formatCOP(totalPendiente)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Facturas Abiertas</span>
          <div className="text-2xl font-bold text-[#0F2A5C] mt-1">{invoices.length}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Vencidas</span>
          <div className="text-2xl font-bold text-amber-600 mt-1">{invoices.filter(i => i.status === "overdue").length}</div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-[#0F2A5C]" /></div>
      ) : invoices.length === 0 ? (
        <div className="bg-[#F0F4FF] border-2 border-dashed border-[#C7D7FF] rounded-2xl p-10 text-center">
          <CheckCircle2 size={36} className="mx-auto text-emerald-500 mb-2" />
          <p className="text-[#0F2A5C] font-semibold">Sin facturas pendientes</p>
          <p className="text-slate-500 text-sm">Todas las facturas están pagadas</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#0F2A5C] text-white text-xs uppercase">
                <th className="px-4 py-3 text-left">Factura</th>
                <th className="px-4 py-3 text-left">Cliente</th>
                <th className="px-4 py-3 text-left">Fecha</th>
                <th className="px-4 py-3 text-left">Vencimiento</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3 text-right">Saldo</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3 text-center">Acción</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv, i) => (
                <tr key={inv.id} className={`border-b border-slate-100 hover:bg-[#F0F4FF]/50 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/40"}`}>
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-[#0F2A5C]">{inv.numberTemplate?.fullNumber || inv.number || inv.id}</td>
                  <td className="px-4 py-3 text-xs">{inv.client?.name || "—"}</td>
                  <td className="px-4 py-3 text-xs">{formatDate(inv.date)}</td>
                  <td className="px-4 py-3 text-xs">{formatDate(inv.dueDate)}</td>
                  <td className="px-4 py-3 text-right text-xs font-medium">{formatCOP(inv.total)}</td>
                  <td className="px-4 py-3 text-right text-xs font-bold text-red-600">{formatCOP(inv.balance || inv.total)}</td>
                  <td className="px-4 py-3"><StatusBadge status={inv.status} /></td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => openPayModal(inv)}
                      className="flex items-center gap-1 text-xs bg-[#C9A84C] text-[#0F2A5C] font-semibold px-3 py-1.5 rounded-lg hover:bg-[#b8903e] transition mx-auto"
                      data-testid={`pay-btn-${inv.id}`}
                    >
                      <CreditCard size={12} /> Registrar Pago
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Payment Modal */}
      {paying && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-[420px] p-6">
            <h3 className="text-lg font-bold text-[#0F2A5C] mb-1">Registrar Pago</h3>
            <p className="text-sm text-slate-500 mb-4">{paying.client?.name} — {paying.numberTemplate?.fullNumber || paying.number}</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Valor del Pago *</label>
                <input
                  type="number"
                  value={payForm.amount}
                  onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                  placeholder="0"
                  data-testid="pay-amount-input"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Fecha de Pago *</label>
                <input
                  type="date"
                  value={payForm.date}
                  onChange={(e) => setPayForm({ ...payForm, date: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Cuenta Bancaria</label>
                <select
                  value={payForm.bankAccountId}
                  onChange={(e) => setPayForm({ ...payForm, bankAccountId: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                >
                  {bankAccounts.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Observaciones</label>
                <input
                  value={payForm.notes}
                  onChange={(e) => setPayForm({ ...payForm, notes: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                  placeholder="Referencia de pago..."
                />
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={handlePay} className="flex-1 bg-[#0F2A5C] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#163A7A]" data-testid="confirm-pay-btn">
                Registrar en Alegra
              </button>
              <button onClick={() => setPaying(null)} className="px-4 py-2.5 border rounded-lg text-sm text-slate-600 hover:bg-slate-50">
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
