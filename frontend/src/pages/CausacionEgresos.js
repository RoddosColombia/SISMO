import React, { useState, useEffect, useCallback } from "react";
import { Plus, RefreshCw, Loader2, Send } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import AlegraAccountSelector from "../components/AlegraAccountSelector";
import JournalEntryPreview from "../components/JournalEntryPreview";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { formatCOP, formatDate, todayStr } from "../utils/formatters";
import { toast } from "sonner";

const EXPENSE_TYPES = [
  { value: "costo_venta", label: "Costo de venta", defaultDebit: { id: "6135", code: "6135", name: "Costos de ventas" } },
  { value: "gasto_personal", label: "Gasto de personal", defaultDebit: { id: "5105", code: "5105", name: "Gastos de personal - administración" } },
  { value: "gasto_admin", label: "Gasto de administración", defaultDebit: { id: "5195", code: "5195", name: "Gastos generales - administración" } },
  { value: "arrendamiento", label: "Arrendamiento", defaultDebit: { id: "5120", code: "5120", name: "Arrendamientos - administración" } },
  { value: "servicios_publicos", label: "Servicios públicos", defaultDebit: { id: "5185", code: "5185", name: "Servicios públicos" } },
  { value: "honorarios", label: "Honorarios", defaultDebit: { id: "5110", code: "5110", name: "Honorarios - administración" } },
  { value: "gasto_ventas", label: "Gasto de ventas", defaultDebit: { id: "5295", code: "5295", name: "Gastos generales - ventas" } },
  { value: "gasto_financiero", label: "Gasto financiero", defaultDebit: { id: "5305", code: "5305", name: "Gastos financieros" } },
  { value: "depreciacion", label: "Depreciación", defaultDebit: { id: "5160", code: "5160", name: "Depreciaciones - administración" } },
  { value: "impuesto_ica", label: "Impuesto ICA", defaultDebit: { id: "5415", code: "5415", name: "Impuesto de industria y comercio (ICA)" } },
];

export default function CausacionEgresos() {
  const { api } = useAuth();
  const { getDefaultAccount } = useAlegra();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);

  // Form
  const [expenseType, setExpenseType] = useState("");
  const [date, setDate] = useState(todayStr());
  const [observations, setObservations] = useState("");
  const [debitAccount, setDebitAccount] = useState(null);
  const [creditAccount, setCreditAccount] = useState(null);
  const [amount, setAmount] = useState("");
  const [ivaRate, setIvaRate] = useState("0");
  const [ivaAccount, setIvaAccount] = useState(null);
  const [hasRetencion, setHasRetencion] = useState(false);
  const [retencionRate, setRetencionRate] = useState("4");
  const [retencionAccount, setRetencionAccount] = useState(null);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get("/alegra/journals");
      setEntries(resp.data);
    } catch { toast.error("Error cargando causaciones"); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleTypeChange = (val) => {
    setExpenseType(val);
    const type = EXPENSE_TYPES.find(t => t.value === val);
    if (type) setDebitAccount(type.defaultDebit);
    setCreditAccount(getDefaultAccount("banco_principal") || { id: "2205", code: "2205", name: "Proveedores nacionales" });
  };

  const amt = parseFloat(amount) || 0;
  const ivaAmt = Math.round(amt * (parseFloat(ivaRate) / 100));
  const retencionAmt = hasRetencion ? Math.round(amt * (parseFloat(retencionRate) / 100)) : 0;
  const totalDebitAmt = amt + ivaAmt;
  const netCredit = totalDebitAmt - retencionAmt;

  const journalEntries = (() => {
    if (!amt) return [];
    const lines = [];
    lines.push({ account: debitAccount || { code: "???", name: "Seleccionar cuenta" }, debit: amt, credit: 0 });
    if (ivaAmt > 0 && ivaAccount) {
      lines.push({ account: ivaAccount, debit: ivaAmt, credit: 0 });
    }
    if (retencionAmt > 0 && retencionAccount) {
      lines.push({ account: retencionAccount, debit: 0, credit: retencionAmt });
    }
    lines.push({ account: creditAccount || { code: "???", name: "Seleccionar cuenta" }, debit: 0, credit: netCredit });
    return lines;
  })();

  const totalDebit = journalEntries.reduce((s, e) => s + (e.debit || 0), 0);
  const totalCredit = journalEntries.reduce((s, e) => s + (e.credit || 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 1 && journalEntries.length > 0;

  const openNew = () => {
    setExpenseType(""); setDate(todayStr()); setObservations(""); setAmount("");
    setDebitAccount(getDefaultAccount("gasto_admin"));
    setCreditAccount(getDefaultAccount("banco_principal") || { id: "2205", code: "2205", name: "Proveedores nacionales" });
    setIvaRate("0"); setIvaAccount(null); setHasRetencion(false);
    setRetencionRate("4");
    setRetencionAccount({ id: "2365", code: "2365", name: "Retención en la fuente por pagar" });
    setOpen(true);
  };

  const handleSubmit = async () => {
    if (!debitAccount || !creditAccount) { toast.error("Selecciona las cuentas requeridas"); return; }
    if (!amt) { toast.error("Ingresa un monto"); return; }
    if (!isBalanced) { toast.error("El asiento no cuadra"); return; }

    setSubmitting(true);
    try {
      const body = {
        date, observations: observations || `Causación egreso ${expenseType} — ${date}`,
        entries: journalEntries.map(e => ({
          account: { id: e.account.id },
          debit: e.debit, credit: e.credit,
        })),
      };
      const result = await api.post("/alegra/journals", body);
      toast.success(`Causación creada en Alegra — ${result.data.number || result.data.id}`);
      setOpen(false);
      loadEntries();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al crear la causación");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="space-y-5" data-testid="causacion-egresos-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Causación de Egresos</h2>
          <p className="text-sm text-slate-500">Registra comprobantes contables de gasto y costo en Alegra</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadEntries} className="p-2.5 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
          <Button onClick={openNew} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="new-causacion-egreso-btn">
            <Plus size={16} className="mr-1.5" /> Nueva Causación
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="egreso-entries-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Número</th>
              <th className="text-left px-5 py-3">Fecha</th>
              <th className="text-left px-5 py-3">Concepto</th>
              <th className="text-right px-5 py-3">Total</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-5 py-10 text-center"><Loader2 size={20} className="animate-spin mx-auto text-slate-400" /></td></tr>
            ) : entries.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-10 text-center text-sm text-slate-400">No hay causaciones de egreso</td></tr>
            ) : entries.map(e => {
              const totalDeb = e.entries?.reduce((s, en) => s + (en.debit || 0), 0) || 0;
              return (
                <tr key={e.id} className="border-t border-slate-50 hover:bg-[#F0F4FF]/30 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs font-semibold text-[#0F2A5C]">{e.number}</td>
                  <td className="px-5 py-3 text-slate-500">{formatDate(e.date)}</td>
                  <td className="px-5 py-3 text-slate-700 max-w-[200px] truncate">{e.observations}</td>
                  <td className="px-5 py-3 text-right font-bold text-[#0F172A] num-right">{formatCOP(totalDeb)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="font-montserrat text-[#0F2A5C]">Nueva Causación de Egreso</SheetTitle>
          </SheetHeader>

          <div className="mt-6 space-y-5">
            <div>
              <Label className="text-sm font-semibold text-slate-700">Tipo de egreso</Label>
              <Select value={expenseType} onValueChange={handleTypeChange}>
                <SelectTrigger className="mt-1.5" data-testid="expense-type-select">
                  <SelectValue placeholder="Seleccionar tipo..." />
                </SelectTrigger>
                <SelectContent>
                  {EXPENSE_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold text-slate-700">Fecha</Label>
                <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="mt-1.5" data-testid="egreso-date" />
              </div>
              <div>
                <Label className="text-sm font-semibold text-slate-700">Monto base (sin IVA)</Label>
                <Input type="number" placeholder="0" value={amount} onChange={e => setAmount(e.target.value)} className="mt-1.5" data-testid="egreso-amount" />
              </div>
            </div>

            <div>
              <Label className="text-sm font-semibold text-slate-700">¿El egreso tiene IVA?</Label>
              <Select value={ivaRate} onValueChange={v => { setIvaRate(v); if (v !== "0") setIvaAccount({ id: "2409", code: "2409", name: "IVA descontable" }); else setIvaAccount(null); }}>
                <SelectTrigger className="mt-1.5" data-testid="egreso-iva-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Sin IVA</SelectItem>
                  <SelectItem value="19">IVA 19%</SelectItem>
                  <SelectItem value="5">IVA 5%</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-3">
              <input type="checkbox" id="hasRetencionE" checked={hasRetencion} onChange={e => setHasRetencion(e.target.checked)} className="rounded" />
              <Label htmlFor="hasRetencionE" className="text-sm font-semibold text-slate-700 cursor-pointer">¿Practico retención al proveedor?</Label>
            </div>
            {hasRetencion && (
              <div className="grid grid-cols-2 gap-4 pl-4 border-l-2 border-[#00A9E0]/30">
                <div>
                  <Label className="text-sm text-slate-600">Tarifa de retención</Label>
                  <Select value={retencionRate} onValueChange={setRetencionRate}>
                    <SelectTrigger className="mt-1.5 h-9 text-sm" data-testid="egreso-retencion-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="4">Servicios 4%</SelectItem>
                      <SelectItem value="10">Honorarios 10%</SelectItem>
                      <SelectItem value="3.5">Arrendamiento 3.5%</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="text-right pt-6">
                  <span className="text-xs text-slate-500">Retención practicada:</span>
                  <div className="text-base font-bold text-orange-600">{formatCOP(retencionAmt)}</div>
                </div>
              </div>
            )}

            <AlegraAccountSelector
              label="Cuenta del gasto / costo (Débito)"
              value={debitAccount}
              onChange={(acc) => {
                setDebitAccount(acc);
                if (acc && !["5","6","7"].some(p => acc.code?.startsWith(p))) {
                  toast.warning(`Cuenta ${acc.code} no parece ser un gasto/costo. Se esperan cuentas 5xxx, 6xxx o 7xxx.`);
                }
              }}
              filterType="expense"
              required
              helpText="Cuenta 5xxx, 6xxx o 7xxx que se debita al registrar el gasto"
            />
            <AlegraAccountSelector
              label="Cuenta contrapartida (Crédito)"
              value={creditAccount}
              onChange={setCreditAccount}
              filterType="all"
              allowedCodes={["11", "22", "23", "25"]}
              required
              helpText="Proveedor (2205), banco (11xx) si pagado, o pasivo (22-25xx)"
            />

            {journalEntries.length > 0 && <JournalEntryPreview entries={journalEntries} />}

            <div>
              <Label className="text-sm font-semibold text-slate-700">Concepto / Observaciones</Label>
              <Input placeholder="Descripción de la causación..." value={observations} onChange={e => setObservations(e.target.value)} className="mt-1.5" />
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">Cancelar</Button>
              <Button onClick={handleSubmit} disabled={submitting || !isBalanced} className="flex-1 bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="submit-causacion-egreso-btn">
                {submitting ? <><Loader2 size={15} className="mr-2 animate-spin" />Ejecutando...</> : <><Send size={15} className="mr-2" />Guardar en Alegra</>}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
