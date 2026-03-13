import React, { useState, useEffect, useCallback } from "react";
import { Plus, Search, RefreshCw, Loader2, Send, FileDown, Calendar } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import AlegraAccountSelector from "../components/AlegraAccountSelector";
import JournalEntryPreview from "../components/JournalEntryPreview";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { formatCOP, formatDate, todayStr, addDays, getStatusInfo, calcIVA, getDocNumber, getVendorName, getMonthRange } from "../utils/formatters";
import { exportExcel } from "../utils/exportUtils";
import { toast } from "sonner";

const EMPTY_ITEM = { description: "", quantity: 1, price: 0, ivaRate: 19, account: null };

// Plazos de pago por tipo de proveedor
const PLAZOS_PROVEEDOR = [
  { value: "contado", label: "Contado (mismo día)", dias: 0 },
  { value: "30", label: "30 días", dias: 30 },
  { value: "60", label: "60 días", dias: 60 },
  { value: "80", label: "80 días — Repuestos", dias: 80 },
  { value: "90", label: "90 días — Motos Auteco", dias: 90 },
];

export default function FacturacionCompra() {
  const { api } = useAuth();
  const { contacts, getDefaultAccount } = useAlegra();
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Date filter — default current month
  const { from: defaultFrom, to: defaultTo } = getMonthRange();
  const [dateFrom, setDateFrom] = useState(defaultFrom);
  const [dateTo, setDateTo] = useState(defaultTo);

  // Form
  const [provider, setProvider] = useState(null);
  const [providerSearch, setProviderSearch] = useState("");
  const [date, setDate] = useState(todayStr());
  const [plazo, setPlazo] = useState("contado");
  const [dueDate, setDueDate] = useState(todayStr());
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [paymentAccount, setPaymentAccount] = useState(null);
  const [observations, setObservations] = useState("");

  const loadBills = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get("/alegra/bills", { params: { date_start: dateFrom, date_end: dateTo } });
      setBills(resp.data);
    } catch { toast.error("Error cargando facturas de compra"); }
    finally { setLoading(false); }
  }, [api, dateFrom, dateTo]);

  useEffect(() => { loadBills(); }, [loadBills]);

  const filteredProviders = contacts.filter(c =>
    c.type === "provider" && c.name.toLowerCase().includes(providerSearch.toLowerCase())
  );

  const updateItem = (i, field, value) => {
    setItems(prev => { const n = [...prev]; n[i] = { ...n[i], [field]: value }; return n; });
  };

  const openNew = () => {
    setProvider(null); setProviderSearch(""); setDate(todayStr());
    setPlazo("contado");
    setDueDate(todayStr());
    setItems([{ ...EMPTY_ITEM, account: getDefaultAccount("gasto_admin") }]);
    setPaymentAccount(getDefaultAccount("banco_principal"));
    setObservations("");
    setOpen(true);
  };

  const handlePlazoChange = (p) => {
    setPlazo(p);
    const found = PLAZOS_PROVEEDOR.find(x => x.value === p);
    if (found) setDueDate(addDays(date, found.dias));
  };

  const handleDateChange = (newDate) => {
    setDate(newDate);
    const found = PLAZOS_PROVEEDOR.find(x => x.value === plazo);
    if (found) setDueDate(addDays(newDate, found.dias));
  };

  const subtotal = items.reduce((s, it) => s + (parseFloat(it.price) || 0) * (parseFloat(it.quantity) || 1), 0);
  const totalIVA = items.reduce((s, it) => {
    const base = (parseFloat(it.price) || 0) * (parseFloat(it.quantity) || 1);
    return s + calcIVA(base, it.ivaRate || 0);
  }, 0);
  const total = subtotal + totalIVA;

  // Build journal preview from all expense accounts
  const journalEntries = (() => {
    const entries = [];
    items.forEach(it => {
      if (it.account) {
        const lineTotal = (parseFloat(it.price) || 0) * (parseFloat(it.quantity) || 1);
        entries.push({ account: it.account, debit: lineTotal, credit: 0 });
        if (it.ivaRate > 0) {
          entries.push({ account: { id: "2409", code: "2409", name: "IVA descontable" }, debit: calcIVA(lineTotal, it.ivaRate), credit: 0 });
        }
      }
    });
    if (entries.length > 0) {
      entries.push({ account: paymentAccount || { id: "2205", code: "2205", name: "Proveedores nacionales" }, debit: 0, credit: total });
    }
    return entries;
  })();

  const handleSubmit = async () => {
    if (!provider) { toast.error("Selecciona un proveedor"); return; }
    if (items.some(it => !it.description || !it.price)) { toast.error("Completa todos los items"); return; }

    setSubmitting(true);
    try {
      const body = {
        date, dueDate,
        provider: { id: provider.id },
        items: items.map(it => ({
          description: it.description,
          quantity: parseFloat(it.quantity) || 1,
          price: parseFloat(it.price) || 0,
          account: it.account ? { id: it.account.id } : undefined,
          tax: it.ivaRate > 0 ? [{ percentage: it.ivaRate }] : [],
        })),
        observations,
      };
      const result = await api.post("/alegra/bills", body);
      toast.success(`Factura de compra creada en Alegra — ID: ${result.data.id || result.data.number}`);
      setOpen(false);
      loadBills();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al registrar la factura");
    } finally { setSubmitting(false); }
  };

  const filtered = bills.filter(b =>
    !search || getDocNumber(b).toLowerCase().includes(search.toLowerCase()) ||
    getVendorName(b).toLowerCase().includes(search.toLowerCase())
  );

  const handleExportExcel = () => {
    const STATUS_ES = { open: "Pendiente", paid: "Pagada", overdue: "Vencida", voided: "Anulada", draft: "Borrador" };
    exportExcel({
      filename: `facturas-compra-${new Date().toISOString().slice(0, 10)}`,
      sheets: [{
        name: "Facturas Compra",
        columns: [
          { key: "numero", label: "Número", width: 18 },
          { key: "proveedor", label: "Proveedor", width: 30 },
          { key: "fecha", label: "Fecha", width: 14 },
          { key: "fecha_pago", label: "Fecha de pago", width: 14 },
          { key: "total", label: "Total", width: 16 },
          { key: "estado", label: "Estado", width: 14 },
        ],
        rows: filtered.map(b => ({
          numero: getDocNumber(b),
          proveedor: getVendorName(b),
          fecha: b.date || "—",
          fecha_pago: b.dueDate || "—",
          total: parseFloat(b.total || 0),
          estado: STATUS_ES[b.status] || b.status || "—",
        })),
      }],
    });
  };

  return (
    <div className="space-y-5" data-testid="facturacion-compra-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Facturación de Compra</h2>
          <p className="text-sm text-slate-500">Registra facturas de proveedores directamente en Alegra</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadBills} className="p-2.5 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
          {!loading && filtered.length > 0 && (
            <button onClick={handleExportExcel} data-testid="export-excel-bills-btn"
              className="flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg transition">
              <FileDown size={13} /> Excel
            </button>
          )}
          <Button onClick={openNew} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="new-bill-btn">
            <Plus size={16} className="mr-1.5" /> Registrar Compra
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs border border-slate-200 bg-white">
          <Calendar size={13} className="text-[#0F2A5C]" />
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="outline-none text-xs text-slate-700" data-testid="bill-date-from" />
          <span className="text-slate-300">—</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="outline-none text-xs text-slate-700" data-testid="bill-date-to" />
        </div>
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Buscar por número o proveedor..." className="pl-9" value={search} onChange={e => setSearch(e.target.value)} data-testid="bill-search" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="bills-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Número</th>
              <th className="text-left px-5 py-3">Proveedor</th>
              <th className="text-left px-5 py-3">Fecha</th>
              <th className="text-left px-5 py-3">Fecha de pago</th>
              <th className="text-right px-5 py-3">Total</th>
              <th className="text-center px-5 py-3">Estado pago</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-5 py-10 text-center"><Loader2 size={20} className="animate-spin mx-auto text-slate-400" /></td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-400">No hay facturas de compra</td></tr>
            ) : filtered.map(b => {
              const si = getStatusInfo(b.status);
              return (
                <tr key={b.id} className="border-t border-slate-50 hover:bg-[#F0F4FF]/30 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs font-semibold text-[#0F2A5C]">{getDocNumber(b)}</td>
                  <td className="px-5 py-3 text-slate-700 max-w-[130px] truncate">{getVendorName(b)}</td>
                  <td className="px-5 py-3 text-slate-500">{formatDate(b.date)}</td>
                  <td className="px-5 py-3 text-slate-600 max-w-[150px] truncate">{formatDate(b.dueDate) || "—"}</td>
                  <td className="px-5 py-3 text-right font-bold text-[#0F172A] num-right">{formatCOP(b.total)}</td>
                  <td className="px-5 py-3 text-center"><span className={`text-xs font-medium px-2 py-0.5 rounded-full ${si.className}`}>{si.label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="font-montserrat text-[#0F2A5C]">Registrar Factura de Compra</SheetTitle>
          </SheetHeader>

          <div className="mt-6 space-y-5">
            {/* Provider */}
            <div>
              <Label className="text-sm font-semibold text-slate-700">Proveedor *</Label>
              <Input placeholder="Buscar proveedor..." value={providerSearch} onChange={e => setProviderSearch(e.target.value)} className="mt-1.5" data-testid="provider-search-input" />
              {providerSearch && filteredProviders.length > 0 && (
                <div className="mt-1 border border-slate-200 rounded-lg bg-white shadow-sm max-h-40 overflow-y-auto">
                  {filteredProviders.map(p => (
                    <button key={p.id} className="w-full text-left px-3 py-2 text-sm hover:bg-[#F0F4FF]" onClick={() => { setProvider(p); setProviderSearch(p.name); }}>
                      <span className="font-medium">{p.name}</span>
                      <span className="text-xs text-slate-400 ml-2">{p.identification}</span>
                    </button>
                  ))}
                </div>
              )}
              {provider && <p className="text-xs text-green-600 mt-1">{provider.name} · NIT: {provider.identification}</p>}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold text-slate-700">Fecha de factura</Label>
                <Input type="date" value={date} onChange={e => handleDateChange(e.target.value)} className="mt-1.5" data-testid="bill-date" />
              </div>
              <div>
                <Label className="text-sm font-semibold text-slate-700">Plazo de pago</Label>
                <Select value={plazo} onValueChange={handlePlazoChange}>
                  <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PLAZOS_PROVEEDOR.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-sm font-semibold text-slate-700">Fecha de pago estimada</Label>
              <Input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} className="mt-1.5" />
              <p className="text-[11px] text-slate-400 mt-1">Calculada según el plazo. Puedes editarla manualmente.</p>
            </div>

            {/* Items with per-line account */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold text-slate-700">Líneas de la factura</Label>
                <button onClick={() => setItems(p => [...p, { ...EMPTY_ITEM, account: getDefaultAccount("gasto_admin") }])} className="text-xs text-[#0F2A5C] font-semibold flex items-center gap-1">
                  <Plus size={12} /> Agregar línea
                </button>
              </div>
              {items.map((item, i) => (
                <div key={i} className="border border-slate-200 rounded-lg p-3 mb-3 space-y-3">
                  <div className="grid grid-cols-12 gap-2">
                    <div className="col-span-5">
                      <Label className="text-xs text-slate-500">Descripción</Label>
                      <Input value={item.description} onChange={e => updateItem(i, "description", e.target.value)} placeholder="Descripción del gasto" className="h-8 text-sm mt-1" data-testid={`bill-item-desc-${i}`} />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-xs text-slate-500">Cantidad</Label>
                      <Input type="number" value={item.quantity} onChange={e => updateItem(i, "quantity", e.target.value)} className="h-8 text-sm mt-1" />
                    </div>
                    <div className="col-span-3">
                      <Label className="text-xs text-slate-500">Valor</Label>
                      <Input type="number" value={item.price} onChange={e => updateItem(i, "price", e.target.value)} placeholder="0" className="h-8 text-sm mt-1" data-testid={`bill-item-price-${i}`} />
                    </div>
                    <div className="col-span-1">
                      <Label className="text-xs text-slate-500">IVA%</Label>
                      <Select value={String(item.ivaRate)} onValueChange={v => updateItem(i, "ivaRate", parseInt(v))}>
                        <SelectTrigger className="h-8 text-xs mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="19">19%</SelectItem>
                          <SelectItem value="5">5%</SelectItem>
                          <SelectItem value="0">0%</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="col-span-1 flex items-end justify-end">
                      {items.length > 1 && (
                        <button onClick={() => setItems(p => p.filter((_, idx) => idx !== i))} className="h-8 w-8 flex items-center justify-center text-red-400 hover:text-red-600">×</button>
                      )}
                    </div>
                  </div>
                  {/* Per-line account selector */}
                  <AlegraAccountSelector
                    label="Cuenta del gasto"
                    value={item.account}
                    onChange={acc => updateItem(i, "account", acc)}
                    filterType="expense"
                    helpText="Cuenta 5xxx o 6xxx a la que se carga este gasto"
                  />
                </div>
              ))}
            </div>

            {/* Payment account */}
            <AlegraAccountSelector
              label="Cuenta contrapartida (Crédito)"
              value={paymentAccount}
              onChange={setPaymentAccount}
              filterType="liability"
              allowedCodes={["22", "11"]}
              helpText="Cuenta del proveedor (2205) o banco (11xx) si ya se pagó"
            />

            {/* Totals */}
            <div className="bg-slate-50 rounded-lg p-4 text-sm space-y-2">
              <div className="flex justify-between text-slate-600"><span>Subtotal</span><span className="font-medium">{formatCOP(subtotal)}</span></div>
              <div className="flex justify-between text-slate-600"><span>IVA</span><span className="font-medium">{formatCOP(totalIVA)}</span></div>
              <div className="flex justify-between font-bold text-[#0F2A5C] text-base border-t border-slate-200 pt-2"><span>Total</span><span>{formatCOP(total)}</span></div>
            </div>

            {journalEntries.length > 0 && <JournalEntryPreview entries={journalEntries} />}

            <div>
              <Label className="text-sm font-semibold text-slate-700">Observaciones</Label>
              <Input placeholder="Notas..." value={observations} onChange={e => setObservations(e.target.value)} className="mt-1.5" />
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">Cancelar</Button>
              <Button onClick={handleSubmit} disabled={submitting} className="flex-1 bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="submit-bill-btn">
                {submitting ? <><Loader2 size={15} className="mr-2 animate-spin" />Ejecutando en Alegra...</> : <><Send size={15} className="mr-2" />Crear en Alegra</>}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
