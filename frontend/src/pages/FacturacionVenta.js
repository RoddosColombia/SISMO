import React, { useState, useEffect, useCallback } from "react";
import { Plus, Search, Send, Ban, RefreshCw, Loader2 } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import AlegraAccountSelector from "../components/AlegraAccountSelector";
import JournalEntryPreview from "../components/JournalEntryPreview";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { formatCOP, formatDate, todayStr, addDays, getStatusInfo, calcIVA } from "../utils/formatters";
import { toast } from "sonner";

const EMPTY_ITEM = { description: "", quantity: 1, price: 0, ivaRate: 19, account: null };
const STATUS_LABEL = { open: "Pendiente", paid: "Pagada", overdue: "Vencida", voided: "Anulada", draft: "Borrador" };

export default function FacturacionVenta() {
  const { api } = useAuth();
  const { contacts, getDefaultAccount } = useAlegra();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Form state
  const [client, setClient] = useState(null);
  const [clientSearch, setClientSearch] = useState("");
  const [date, setDate] = useState(todayStr());
  const [dueDate, setDueDate] = useState(addDays(todayStr(), 30));
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [incomeAccount, setIncomeAccount] = useState(null);
  const [paymentAccount, setPaymentAccount] = useState(null);
  const [observations, setObservations] = useState("");

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get("/alegra/invoices");
      setInvoices(resp.data);
    } catch { toast.error("Error cargando facturas"); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { loadInvoices(); }, [loadInvoices]);

  const filteredContacts = contacts.filter(c =>
    c.type === "client" && c.name.toLowerCase().includes(clientSearch.toLowerCase())
  );

  const updateItem = (i, field, value) => {
    setItems(prev => {
      const newItems = [...prev];
      newItems[i] = { ...newItems[i], [field]: value };
      return newItems;
    });
  };

  const addItem = () => setItems(prev => [...prev, { ...EMPTY_ITEM }]);
  const removeItem = (i) => setItems(prev => prev.filter((_, idx) => idx !== i));

  const openNewInvoice = () => {
    setClient(null); setClientSearch(""); setDate(todayStr());
    setDueDate(addDays(todayStr(), 30));
    setItems([{ ...EMPTY_ITEM }]);
    setIncomeAccount(getDefaultAccount("ingreso_operacional"));
    setPaymentAccount(getDefaultAccount("banco_principal"));
    setObservations("");
    setOpen(true);
  };

  // Totals
  const subtotal = items.reduce((s, it) => s + (parseFloat(it.price) || 0) * (parseFloat(it.quantity) || 1), 0);
  const totalIVA = items.reduce((s, it) => {
    const base = (parseFloat(it.price) || 0) * (parseFloat(it.quantity) || 1);
    return s + calcIVA(base, it.ivaRate || 0);
  }, 0);
  const total = subtotal + totalIVA;

  // Journal preview
  const journalEntries = incomeAccount && paymentAccount ? [
    { account: paymentAccount, debit: total, credit: 0 },
    { account: incomeAccount, debit: 0, credit: subtotal },
    ...(totalIVA > 0 ? [{ account: { id: "2408", code: "2408", name: "IVA por pagar" }, debit: 0, credit: totalIVA }] : []),
  ] : [];

  const handleSubmit = async () => {
    if (!client) { toast.error("Selecciona un cliente"); return; }
    if (!incomeAccount) { toast.error("Selecciona la cuenta de ingreso"); return; }
    if (items.some(it => !it.description || !it.price)) { toast.error("Completa todos los items"); return; }

    setSubmitting(true);
    try {
      const body = {
        date, dueDate,
        client: { id: client.id },
        items: items.map(it => ({
          description: it.description,
          quantity: parseFloat(it.quantity) || 1,
          price: parseFloat(it.price) || 0,
          account: incomeAccount ? { id: incomeAccount.id } : undefined,
          tax: it.ivaRate > 0 ? [{ percentage: it.ivaRate }] : [],
        })),
        observations,
      };
      const result = await api.post("/alegra/invoices", body);
      toast.success(`Factura creada en Alegra — ID: ${result.data.id || result.data.number}`);
      setOpen(false);
      loadInvoices();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al crear la factura");
    } finally { setSubmitting(false); }
  };

  const handleVoid = async (invoiceId) => {
    try {
      await api.post(`/alegra/invoices/${invoiceId}/void`);
      toast.success("Factura anulada en Alegra");
      loadInvoices();
    } catch { toast.error("Error al anular la factura"); }
  };

  const filtered = invoices.filter(inv =>
    !search || inv.number?.toLowerCase().includes(search.toLowerCase()) ||
    inv.client?.name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5" data-testid="facturacion-venta-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Facturación de Venta</h2>
          <p className="text-sm text-slate-500">Crea y gestiona facturas directamente en Alegra</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadInvoices} className="p-2.5 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
          <Button onClick={openNewInvoice} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="new-invoice-btn">
            <Plus size={16} className="mr-1.5" /> Nueva Factura
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input placeholder="Buscar por número o cliente..." className="pl-9" value={search} onChange={e => setSearch(e.target.value)} data-testid="invoice-search" />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="invoices-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Número</th>
              <th className="text-left px-5 py-3">Cliente</th>
              <th className="text-left px-5 py-3">Fecha</th>
              <th className="text-left px-5 py-3">Vencimiento</th>
              <th className="text-right px-5 py-3">Total</th>
              <th className="text-center px-5 py-3">Estado</th>
              <th className="text-center px-5 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-5 py-10 text-center text-slate-400"><Loader2 size={20} className="animate-spin mx-auto" /></td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-400">No hay facturas registradas</td></tr>
            ) : filtered.map(inv => {
              const si = getStatusInfo(inv.status);
              return (
                <tr key={inv.id} className="border-t border-slate-50 hover:bg-[#F0F4FF]/30 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs font-semibold text-[#0F2A5C]">{inv.number}</td>
                  <td className="px-5 py-3 text-slate-700 max-w-[150px] truncate">{inv.client?.name}</td>
                  <td className="px-5 py-3 text-slate-500">{formatDate(inv.date)}</td>
                  <td className="px-5 py-3 text-slate-500">{formatDate(inv.dueDate)}</td>
                  <td className="px-5 py-3 text-right font-bold text-[#0F172A] num-right">{formatCOP(inv.total)}</td>
                  <td className="px-5 py-3 text-center"><span className={`text-xs font-medium px-2 py-0.5 rounded-full ${si.className}`}>{si.label}</span></td>
                  <td className="px-5 py-3 text-center">
                    {inv.status !== "voided" && (
                      <button onClick={() => handleVoid(inv.id)} className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1 mx-auto" data-testid={`void-invoice-${inv.id}`}>
                        <Ban size={12} /> Anular
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* New Invoice Sheet */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="font-montserrat text-[#0F2A5C]">Nueva Factura de Venta</SheetTitle>
          </SheetHeader>

          <div className="mt-6 space-y-5">
            {/* Client */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">Cliente *</Label>
              <Input
                placeholder="Buscar cliente..."
                value={clientSearch}
                onChange={e => setClientSearch(e.target.value)}
                className="mt-1.5"
                data-testid="client-search-input"
              />
              {clientSearch && filteredContacts.length > 0 && (
                <div className="mt-1 border border-slate-200 rounded-lg bg-white shadow-sm max-h-40 overflow-y-auto">
                  {filteredContacts.map(c => (
                    <button key={c.id} className="w-full text-left px-3 py-2 text-sm hover:bg-[#F0F4FF] transition-colors" onClick={() => { setClient(c); setClientSearch(c.name); }} data-testid={`contact-option-${c.id}`}>
                      <span className="font-medium">{c.name}</span>
                      <span className="text-slate-400 text-xs ml-2">{c.identification}</span>
                    </button>
                  ))}
                </div>
              )}
              {client && <p className="text-xs text-green-600 mt-1">Cliente: {client.name} · NIT: {client.identification}</p>}
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold text-slate-700">Fecha</Label>
                <Input type="date" value={date} onChange={e => { setDate(e.target.value); setDueDate(addDays(e.target.value, 30)); }} className="mt-1.5" data-testid="invoice-date" />
              </div>
              <div>
                <Label className="text-sm font-semibold text-slate-700">Vencimiento</Label>
                <Input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} className="mt-1.5" data-testid="invoice-due-date" />
              </div>
            </div>

            {/* Income Account */}
            <AlegraAccountSelector
              label="Cuenta contable del ingreso"
              value={incomeAccount}
              onChange={setIncomeAccount}
              filterType="income"
              required
              helpText="Cuenta 4xxx que se acredita al generar esta factura"
            />

            {/* Items */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold text-slate-700">Items de la factura</Label>
                <button onClick={addItem} className="text-xs text-[#0F2A5C] hover:text-[#C9A84C] font-semibold flex items-center gap-1">
                  <Plus size={12} /> Agregar línea
                </button>
              </div>
              {items.map((item, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 mb-2 items-end">
                  <div className="col-span-5">
                    {i === 0 && <Label className="text-xs text-slate-500 mb-1 block">Descripción</Label>}
                    <Input placeholder="Descripción" value={item.description} onChange={e => updateItem(i, "description", e.target.value)} className="h-9 text-sm" data-testid={`item-description-${i}`} />
                  </div>
                  <div className="col-span-2">
                    {i === 0 && <Label className="text-xs text-slate-500 mb-1 block">Cant.</Label>}
                    <Input type="number" placeholder="1" value={item.quantity} onChange={e => updateItem(i, "quantity", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="col-span-3">
                    {i === 0 && <Label className="text-xs text-slate-500 mb-1 block">Valor unitario</Label>}
                    <Input type="number" placeholder="0" value={item.price} onChange={e => updateItem(i, "price", e.target.value)} className="h-9 text-sm" data-testid={`item-price-${i}`} />
                  </div>
                  <div className="col-span-1">
                    {i === 0 && <Label className="text-xs text-slate-500 mb-1 block">IVA%</Label>}
                    <Select value={String(item.ivaRate)} onValueChange={v => updateItem(i, "ivaRate", parseInt(v))}>
                      <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="19">19%</SelectItem>
                        <SelectItem value="5">5%</SelectItem>
                        <SelectItem value="0">0%</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-1 flex justify-end">
                    {items.length > 1 && (
                      <button onClick={() => removeItem(i)} className="text-red-400 hover:text-red-600 h-9 w-9 flex items-center justify-center">×</button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Payment Account */}
            <AlegraAccountSelector
              label="Cuenta donde se recibe el pago"
              value={paymentAccount}
              onChange={setPaymentAccount}
              filterType="asset"
              allowedCodes={["11", "13"]}
              helpText="Cuenta bancaria o cartera donde ingresará el cobro"
            />

            {/* Totals */}
            <div className="bg-slate-50 rounded-lg p-4 text-sm space-y-2">
              <div className="flex justify-between text-slate-600"><span>Subtotal</span><span className="num-right font-medium">{formatCOP(subtotal)}</span></div>
              <div className="flex justify-between text-slate-600"><span>IVA</span><span className="num-right font-medium">{formatCOP(totalIVA)}</span></div>
              <div className="flex justify-between font-bold text-[#0F2A5C] text-base border-t border-slate-200 pt-2"><span>Total</span><span className="num-right">{formatCOP(total)}</span></div>
            </div>

            {/* Preview */}
            {journalEntries.length > 0 && <JournalEntryPreview entries={journalEntries} />}

            {/* Observations */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">Observaciones</Label>
              <Input placeholder="Notas adicionales..." value={observations} onChange={e => setObservations(e.target.value)} className="mt-1.5" />
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">Cancelar</Button>
              <Button onClick={handleSubmit} disabled={submitting} className="flex-1 bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="submit-invoice-btn">
                {submitting ? <><Loader2 size={15} className="mr-2 animate-spin" />Ejecutando en Alegra...</> : <><Send size={15} className="mr-2" />Crear en Alegra</>}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
