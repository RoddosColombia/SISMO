import React, { useState, useEffect, useCallback } from "react";
import { RefreshCw, Loader2, CheckCircle, Circle, Save } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { formatCOP, formatDate } from "../utils/formatters";
import { toast } from "sonner";

export default function ConciliacionBancaria() {
  const { api } = useAuth();
  const { bankAccounts } = useAlegra();
  const [selectedAccount, setSelectedAccount] = useState("");
  const [statementDate, setStatementDate] = useState(new Date().toISOString().split("T")[0]);
  const [statementBalance, setStatementBalance] = useState("");
  const [reconItems, setReconItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reconciledIds, setReconciledIds] = useState(new Set());

  const loadReconciliation = useCallback(async () => {
    if (!selectedAccount) return;
    setLoading(true);
    try {
      const resp = await api.get(`/alegra/bank-accounts/${selectedAccount}/reconciliations`);
      setReconItems(resp.data.items || []);
      if (resp.data.statementBalance && !statementBalance) {
        setStatementBalance(String(resp.data.statementBalance));
      }
      // Pre-mark reconciled items
      const reconciled = new Set((resp.data.items || []).filter(i => i.reconciled).map(i => i.id));
      setReconciledIds(reconciled);
    } catch { toast.error("Error cargando conciliación"); }
    finally { setLoading(false); }
  }, [selectedAccount, api]); // eslint-disable-line

  useEffect(() => { loadReconciliation(); }, [loadReconciliation]);

  const toggleItem = (id) => {
    setReconciledIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!selectedAccount) { toast.error("Selecciona una cuenta bancaria"); return; }
    setSubmitting(true);
    try {
      const body = {
        statementDate,
        statementBalance: parseFloat(statementBalance) || 0,
        reconciledTransactions: Array.from(reconciledIds),
      };
      await api.post(`/alegra/bank-accounts/${selectedAccount}/reconciliations`, body);
      toast.success("Conciliación guardada en Alegra");
      loadReconciliation();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al guardar conciliación");
    } finally { setSubmitting(false); }
  };

  const currentAccount = bankAccounts.find(b => b.id === selectedAccount);
  const reconciledItems = reconItems.filter(i => reconciledIds.has(i.id));
  const pendingItems = reconItems.filter(i => !reconciledIds.has(i.id));

  const saldoLibros = reconItems.reduce((s, i) => s + (i.amount || 0), 0);
  const saldoConciliado = reconciledItems.reduce((s, i) => s + (i.amount || 0), 0);
  const saldoExtracto = parseFloat(statementBalance) || 0;
  const diferencia = saldoExtracto - saldoConciliado;

  return (
    <div className="space-y-5" data-testid="conciliacion-bancaria-page">
      <div>
        <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Conciliación Bancaria</h2>
        <p className="text-sm text-slate-500">Concilia los movimientos bancarios con los registros contables en Alegra</p>
      </div>

      {/* Account selector + parameters */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
        <h3 className="text-sm font-bold text-[#0F2A5C] mb-4 font-montserrat">Parámetros de conciliación</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label className="text-sm font-semibold text-slate-700">Cuenta bancaria *</Label>
            <Select value={selectedAccount} onValueChange={setSelectedAccount}>
              <SelectTrigger className="mt-1.5" data-testid="bank-account-select">
                <SelectValue placeholder="Seleccionar cuenta..." />
              </SelectTrigger>
              <SelectContent>
                {bankAccounts.map(ba => (
                  <SelectItem key={ba.id} value={ba.id}>
                    {ba.name} ({ba.number})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm font-semibold text-slate-700">Fecha del extracto</Label>
            <Input type="date" value={statementDate} onChange={e => setStatementDate(e.target.value)} className="mt-1.5" data-testid="statement-date" />
          </div>
          <div>
            <Label className="text-sm font-semibold text-slate-700">Saldo extracto bancario</Label>
            <Input type="number" placeholder="0" value={statementBalance} onChange={e => setStatementBalance(e.target.value)} className="mt-1.5" data-testid="statement-balance" />
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <Button onClick={loadReconciliation} disabled={!selectedAccount} variant="outline" className="gap-2">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Cargar movimientos
          </Button>
          {selectedAccount && currentAccount && (
            <span className="text-sm text-slate-500 self-center">
              Saldo en libros: <strong className="text-[#0F2A5C]">{formatCOP(currentAccount.balance)}</strong>
            </span>
          )}
        </div>
      </div>

      {/* Summary cards */}
      {reconItems.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border-l-4 border-[#0F2A5C] shadow-sm p-4">
            <p className="text-xs text-slate-500 uppercase font-semibold">Saldo extracto</p>
            <p className="text-xl font-bold text-[#0F2A5C] font-montserrat">{formatCOP(saldoExtracto)}</p>
          </div>
          <div className="bg-white rounded-xl border-l-4 border-[#C9A84C] shadow-sm p-4">
            <p className="text-xs text-slate-500 uppercase font-semibold">Saldo conciliado</p>
            <p className="text-xl font-bold text-[#0F172A] font-montserrat">{formatCOP(saldoConciliado)}</p>
          </div>
          <div className={`bg-white rounded-xl border-l-4 shadow-sm p-4 ${Math.abs(diferencia) < 1 ? "border-green-500" : "border-red-400"}`}>
            <p className="text-xs text-slate-500 uppercase font-semibold">Diferencia</p>
            <p className={`text-xl font-bold font-montserrat ${Math.abs(diferencia) < 1 ? "text-green-600" : "text-red-600"}`}>{formatCOP(diferencia)}</p>
          </div>
          <div className="bg-white rounded-xl border-l-4 border-slate-300 shadow-sm p-4">
            <p className="text-xs text-slate-500 uppercase font-semibold">Pendientes</p>
            <p className="text-xl font-bold text-slate-700 font-montserrat">{pendingItems.length}</p>
          </div>
        </div>
      )}

      {/* Transactions table */}
      {reconItems.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="reconciliation-items">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Movimientos del período</h3>
            <div className="flex items-center gap-3">
              <span className="text-xs text-green-600 font-medium">{reconciledIds.size} conciliados</span>
              <span className="text-xs text-slate-500 font-medium">{pendingItems.length} pendientes</span>
            </div>
          </div>
          {loading ? (
            <div className="p-10 text-center"><Loader2 size={20} className="animate-spin mx-auto text-slate-400" /></div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="text-center px-4 py-3 w-12">Rec.</th>
                  <th className="text-left px-4 py-3">Fecha</th>
                  <th className="text-left px-4 py-3">Descripción</th>
                  <th className="text-right px-4 py-3">Débito</th>
                  <th className="text-right px-4 py-3">Crédito</th>
                </tr>
              </thead>
              <tbody>
                {reconItems.map(item => {
                  const isRec = reconciledIds.has(item.id);
                  return (
                    <tr key={item.id} className={`border-t border-slate-50 transition-colors ${isRec ? "bg-green-50/30" : "hover:bg-[#F0F4FF]/20"}`} data-testid={`recon-item-${item.id}`}>
                      <td className="px-4 py-3 text-center">
                        <button onClick={() => toggleItem(item.id)} className="text-slate-400 hover:text-green-600">
                          {isRec ? <CheckCircle size={18} className="text-green-500" /> : <Circle size={18} />}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-slate-500">{formatDate(item.date)}</td>
                      <td className={`px-4 py-3 ${isRec ? "text-slate-400 line-through" : "text-slate-700"}`}>{item.description}</td>
                      <td className="px-4 py-3 text-right num-right font-medium text-red-600">{item.amount < 0 ? formatCOP(Math.abs(item.amount)) : ""}</td>
                      <td className="px-4 py-3 text-right num-right font-medium text-green-600">{item.amount > 0 ? formatCOP(item.amount) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {reconItems.length > 0 && (
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={submitting} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="save-reconciliation-btn">
            {submitting ? <><Loader2 size={15} className="mr-2 animate-spin" />Guardando...</> : <><Save size={15} className="mr-2" />Guardar conciliación en Alegra</>}
          </Button>
        </div>
      )}

      {!selectedAccount && (
        <div className="text-center py-16 text-slate-400">
          <div className="text-4xl mb-3">🏦</div>
          <p className="text-sm font-medium">Selecciona una cuenta bancaria para comenzar la conciliación</p>
        </div>
      )}
    </div>
  );
}
