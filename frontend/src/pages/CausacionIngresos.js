import React, { useState, useEffect, useCallback } from "react";
import { Plus, RefreshCw, Loader2, Send, Trash2 } from "lucide-react";
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

const INCOME_TYPES = [
  { value: "operacional_servicios", label: "Operacional - Servicios", defaultCredit: { id: "4135", code: "4135", name: "Ingresos por servicios" } },
  { value: "operacional_ventas", label: "Operacional - Ventas", defaultCredit: { id: "4105", code: "4105", name: "Ingresos por ventas de productos" } },
  { value: "operacional_honorarios", label: "Operacional - Honorarios", defaultCredit: { id: "4155", code: "4155", name: "Ingresos por honorarios" } },
  { value: "no_operacional_arriendo", label: "No Operacional - Arrendamiento", defaultCredit: { id: "4210", code: "4210", name: "Ingresos por arrendamientos" } },
  { value: "no_operacional_financiero", label: "No Operacional - Financiero", defaultCredit: { id: "4250", code: "4250", name: "Ingresos financieros" } },
  { value: "recuperaciones", label: "Recuperaciones", defaultCredit: { id: "4295", code: "4295", name: "Recuperaciones" } },
  { value: "extraordinario", label: "Extraordinario", defaultCredit: { id: "4800", code: "4800", name: "Ingresos extraordinarios" } },
];

const EMPTY_LINE = { account: null, debit: 0, credit: 0, description: "" };

export default function CausacionIngresos() {
  const { api } = useAuth();
  const { getDefaultAccount } = useAlegra();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);

  // Form
  const [incomeType, setIncomeType] = useState("");
  const [date, setDate] = useState(todayStr());
  const [observations, setObservations] = useState("");
  const [creditAccount, setCreditAccount] = useState(null);
  const [debitAccount, setDebitAccount] = useState(null);
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
      // Filter income-related entries
      setEntries(resp.data);
    } catch { toast.error("Error cargando causaciones"); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleTypeChange = (val) => {
    setIncomeType(val);
    const type = INCOME_TYPES.find(t => t.value === val);
    if (type) setCreditAccount(type.defaultCredit);
    setDebitAccount(getDefaultAccount("banco_principal") || { id: "1110", code: "1110", name: "Bancos" });
  };

  // Build journal preview
  const amt = parseFloat(amount) || 0;
  const ivaAmt = Math.round(amt * (parseFloat(ivaRate) / 100));
  const retencionAmt = hasRetencion ? Math.round(amt * (parseFloat(retencionRate) / 100)) : 0;
  const netDebit = amt + ivaAmt - retencionAmt;

  const journalEntries = (() => {
    if (!amt) return [];
    const lines = [];
    if (retencionAmt > 0 && retencionAccount) {
      lines.push({ account: retencionAccount, debit: retencionAmt, credit: 0 });
    }
    lines.push({ account: debitAccount || { code: "???", name: "Seleccionar cuenta" }, debit: netDebit, credit: 0 });
    lines.push({ account: creditAccount || { code: "???", name: "Seleccionar cuenta" }, debit: 0, credit: amt });
    if (ivaAmt > 0 && ivaAccount) {
      lines.push({ account: ivaAccount, debit: 0, credit: ivaAmt });
    }
    return lines;
  })();

  const totalDebit = journalEntries.reduce((s, e) => s + (e.debit || 0), 0);
  const totalCredit = journalEntries.reduce((s, e) => s + (e.credit || 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 1 && journalEntries.length > 0;

  const openNew = () => {
    setIncomeType(""); setDate(todayStr()); setObservations(""); setAmount("");
    setCreditAccount(getDefaultAccount("ingreso_operacional"));
    setDebitAccount(getDefaultAccount("banco_principal") || { id: "1110", code: "1110", name: "Bancos" });
    setIvaRate("0"); setIvaAccount(null); setHasRetencion(false);
    setRetencionRate("4");
    setRetencionAccount({ id: "1355", code: "1355", name: "Anticipo de impuestos y retenciones" });
    setOpen(true);
  };

  const handleSubmit = async () => {
    if (!creditAccount || !debitAccount) { toast.error("Selecciona las cuentas requeridas"); return; }
    if (!amt) { toast.error("Ingresa un monto"); return; }
    if (!isBalanced) { toast.error("El asiento no cuadra, verifica los valores"); return; }

    setSubmitting(true);
    try {
      const body = {
        date, observations: observations || `Causación ingreso ${incomeType} — ${date}`,
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
    <div className="space-y-5" data-testid="causacion-ingresos-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Causación de Ingresos</h2>
          <p className="text-sm text-slate-500">Registra comprobantes contables de ingreso en Alegra</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadEntries} className="p-2.5 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
          <Button onClick={openNew} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="new-causacion-ingreso-btn">
            <Plus size={16} className="mr-1.5" /> Nueva Causación
          </Button>
        </div>
      </div>

      {/* Manual de uso */}
      <div className="bg-gradient-to-r from-[#F0F4FF] to-[#E8F0FF] border border-[#C7D7FF] rounded-xl p-4">
        <h3 className="text-sm font-bold text-[#0F2A5C] mb-2">Manual de uso — Módulo de Causaciones IA</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-700">
          <div>
            <p className="font-semibold text-[#0F2A5C] mb-1">¿Qué es una causación?</p>
            <p>Es el registro contable que reconoce un ingreso o gasto en el período en que ocurre, independientemente de si se cobró o pagó. Crea un asiento de diario directamente en Alegra.</p>
          </div>
          <div>
            <p className="font-semibold text-[#0F2A5C] mb-1">Integración con IA</p>
            <p>Puedes usar el <strong>chat de IA</strong> (icono inferior derecho) para que el asistente genere causaciones automáticamente. Di, por ejemplo: <em>"Causar ingreso de $2.000.000 por venta de servicios del 15 de marzo"</em>.</p>
          </div>
          <div>
            <p className="font-semibold text-[#0F2A5C] mb-1">Causación desde Facturación de Venta</p>
            <p>Cuando creas una factura de venta, Alegra registra automáticamente el ingreso. La causación manual aquí es para ingresos que NO pasan por factura, como cobros de cuotas directos o ingresos financieros.</p>
          </div>
          <div>
            <p className="font-semibold text-[#0F2A5C] mb-1">Causación desde Registro de Pagos (Cartera)</p>
            <p>Al registrar un pago de cuota en el módulo de <strong>Cartera</strong>, el sistema crea el pago en Alegra automáticamente. Si necesitas causar el ingreso sin el pago físico aún, usa este módulo.</p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="journal-entries-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Número</th>
              <th className="text-left px-5 py-3">Fecha</th>
              <th className="text-left px-5 py-3">Concepto</th>
              <th className="text-right px-5 py-3">Total Débito</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-5 py-10 text-center"><Loader2 size={20} className="animate-spin mx-auto text-slate-400" /></td></tr>
            ) : entries.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-10 text-center text-sm text-slate-400">No hay causaciones registradas</td></tr>
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
            <SheetTitle className="font-montserrat text-[#0F2A5C]">Nueva Causación de Ingreso</SheetTitle>
          </SheetHeader>

          <div className="mt-6 space-y-5">
            {/* Type */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">Tipo de ingreso</Label>
              <Select value={incomeType} onValueChange={handleTypeChange}>
                <SelectTrigger className="mt-1.5" data-testid="income-type-select">
                  <SelectValue placeholder="Seleccionar tipo..." />
                </SelectTrigger>
                <SelectContent>
                  {INCOME_TYPES.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold text-slate-700">Fecha</Label>
                <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="mt-1.5" data-testid="causacion-date" />
              </div>
              <div>
                <Label className="text-sm font-semibold text-slate-700">Monto base (sin IVA)</Label>
                <Input type="number" placeholder="0" value={amount} onChange={e => setAmount(e.target.value)} className="mt-1.5" data-testid="causacion-amount" />
              </div>
            </div>

            {/* IVA */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">¿El ingreso genera IVA?</Label>
              <Select value={ivaRate} onValueChange={v => { setIvaRate(v); if (v !== "0") setIvaAccount({ id: "2408", code: "2408", name: "IVA por pagar" }); else setIvaAccount(null); }}>
                <SelectTrigger className="mt-1.5" data-testid="iva-rate-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Sin IVA</SelectItem>
                  <SelectItem value="19">IVA 19%</SelectItem>
                  <SelectItem value="5">IVA 5%</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Retención */}
            <div className="flex items-center gap-3">
              <input type="checkbox" id="hasRetencion" checked={hasRetencion} onChange={e => setHasRetencion(e.target.checked)} className="rounded" />
              <Label htmlFor="hasRetencion" className="text-sm font-semibold text-slate-700 cursor-pointer">¿Aplica retención en la fuente?</Label>
            </div>
            {hasRetencion && (
              <div className="grid grid-cols-2 gap-4 pl-4 border-l-2 border-[#00A9E0]/30">
                <div>
                  <Label className="text-sm text-slate-600">Tarifa de retención</Label>
                  <Select value={retencionRate} onValueChange={setRetencionRate}>
                    <SelectTrigger className="mt-1.5 h-9 text-sm" data-testid="retencion-rate-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="4">Servicios 4%</SelectItem>
                      <SelectItem value="10">Honorarios 10%</SelectItem>
                      <SelectItem value="3.5">Arrendamiento 3.5%</SelectItem>
                      <SelectItem value="2">Compras 2%</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="text-right pt-6">
                  <span className="text-xs text-slate-500">Retención calculada:</span>
                  <div className="text-base font-bold text-red-600">{formatCOP(retencionAmt)}</div>
                </div>
              </div>
            )}

            {/* Accounts */}
            <AlegraAccountSelector
              label="Cuenta de ingreso (Crédito)"
              value={creditAccount}
              onChange={setCreditAccount}
              filterType="income"
              required
              helpText="Cuenta 4xxx que se acredita al registrar el ingreso"
            />
            <AlegraAccountSelector
              label="Cuenta contrapartida (Débito)"
              value={debitAccount}
              onChange={setDebitAccount}
              filterType="asset"
              allowedCodes={["11", "13"]}
              required
              helpText="Banco (1110) o cartera (1305) que recibe el ingreso"
            />

            {/* Preview */}
            {journalEntries.length > 0 && <JournalEntryPreview entries={journalEntries} />}

            {/* Observations */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">Concepto / Observaciones</Label>
              <Input placeholder="Descripción de la causación..." value={observations} onChange={e => setObservations(e.target.value)} className="mt-1.5" />
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">Cancelar</Button>
              <Button onClick={handleSubmit} disabled={submitting || !isBalanced} className="flex-1 bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="submit-causacion-ingreso-btn">
                {submitting ? <><Loader2 size={15} className="mr-2 animate-spin" />Ejecutando...</> : <><Send size={15} className="mr-2" />Guardar en Alegra</>}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
