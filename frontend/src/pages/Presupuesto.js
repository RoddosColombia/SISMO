import React, { useState, useEffect, useCallback } from "react";
import { Target, Plus, Trash2, Save, RefreshCw, Loader2, BookOpen, ChevronDown, ChevronUp, Info } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP } from "../utils/formatters";

const CATEGORIAS = ["Ingresos", "Costos Ventas", "Gastos Operacionales", "Gastos Administrativos", "Gastos Financieros", "Otros Egresos"];
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const EMPTY_ITEM = { concepto: "", categoria: CATEGORIAS[0], valor_presupuestado: 0 };

function CfoInstruccionesPanel({ instrucciones }) {
  const [open, setOpen] = useState(true);
  if (!instrucciones || instrucciones.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-amber-100 hover:bg-amber-50 transition"
      >
        <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
          <BookOpen size={15} className="text-[#C9A84C]" />
          Reglas CFO Estratégico para Presupuesto
          <span className="bg-[#C9A84C] text-white text-[10px] px-1.5 py-0.5 rounded-full">
            {instrucciones.length}
          </span>
        </span>
        {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>
      {open && (
        <div className="p-4 space-y-2">
          {instrucciones.map((inst, i) => (
            <div key={i} className="flex items-start gap-2 bg-amber-50 rounded-lg p-3 border border-amber-100">
              <Info size={13} className="text-[#C9A84C] mt-0.5 flex-shrink-0" />
              <div>
                <span className="text-[10px] font-semibold text-amber-700 uppercase">{inst.categoria}</span>
                <p className="text-xs text-slate-700 mt-0.5">{inst.instruccion}</p>
              </div>
            </div>
          ))}
          <p className="text-[10px] text-slate-400 text-right">
            Instrucciones guardadas desde el CFO Estratégico
          </p>
        </div>
      )}
    </div>
  );
}

function CfoPresupuestoPanel({ presupuestos, mesActual }) {
  const [open, setOpen] = useState(false);
  const cfoPres = presupuestos.filter(p =>
    p.mes && p.mes.toLowerCase().includes(mesActual.toLowerCase().slice(0, 3))
  );
  if (cfoPres.length === 0) return null;
  const last = cfoPres[cfoPres.length - 1];
  const pres = last.presupuesto || {};

  return (
    <div className="bg-white rounded-xl border border-blue-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-blue-100 hover:bg-blue-50 transition"
      >
        <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
          <Target size={15} className="text-blue-500" />
          Presupuesto CFO — {mesActual}
        </span>
        {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>
      {open && (
        <div className="p-4">
          <div className="grid grid-cols-2 gap-3 text-xs">
            {Object.entries(pres).map(([k, v], i) => (
              <div key={i} className="bg-blue-50 rounded-lg px-3 py-2 flex justify-between">
                <span className="text-slate-600 capitalize">{k.replace(/_/g, " ")}</span>
                <span className="font-bold text-[#0F2A5C]">
                  {typeof v === "number" ? formatCOP(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-400 mt-2">Generado por CFO Estratégico</p>
        </div>
      )}
    </div>
  );
}

export default function Presupuesto() {
  const { api } = useAuth();
  const [ano, setAno] = useState(new Date().getFullYear());
  const [mesActual, setMesActual] = useState(MESES[new Date().getMonth()]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [cfoInstrucciones, setCfoInstrucciones] = useState([]);
  const [cfoPresupuestos, setCfoPresupuestos] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [presuRes, invRes, instRes, cfoPresRes] = await Promise.allSettled([
        api.get("/presupuesto", { params: { ano } }),
        api.get("/alegra/invoices", { params: { date_start: `${ano}-01-01`, date_end: `${ano}-12-31` } }),
        api.get("/cfo/instrucciones"),
        api.get("/cfo/presupuesto"),
      ]);
      if (presuRes.status === "fulfilled") {
        setItems(presuRes.value.data.length > 0
          ? presuRes.value.data
          : [{ ...EMPTY_ITEM, mes: mesActual, ano, id: `new-${Date.now()}` }]
        );
      }
      if (invRes.status === "fulfilled") {
        setInvoices(Array.isArray(invRes.value.data) ? invRes.value.data : []);
      }
      if (instRes.status === "fulfilled") {
        const all = instRes.value.data?.instrucciones || [];
        setCfoInstrucciones(all.filter(i => i.modulo_afectado === "presupuesto" || i.categoria === "regla_presupuesto"));
      }
      if (cfoPresRes.status === "fulfilled") {
        const data = cfoPresRes.value.data;
        setCfoPresupuestos(Array.isArray(data) ? data : []);
      }
    } catch { toast.error("Error cargando presupuesto"); }
    finally { setLoading(false); }
  }, [api, ano, mesActual]);

  useEffect(() => { loadData(); }, [loadData]);

  const mesItems = items.filter(i => i.mes === mesActual);
  const realIngresos = invoices
    .filter(inv => inv.date?.startsWith(`${ano}-${String(MESES.indexOf(mesActual) + 1).padStart(2, "0")}`))
    .reduce((s, inv) => s + parseFloat(inv.total || 0), 0);

  const totalPresupuestado = mesItems.reduce((s, i) => s + parseFloat(i.valor_presupuestado || 0), 0);
  const ingresosPresupuestados = mesItems.filter(i => i.categoria === "Ingresos").reduce((s, i) => s + parseFloat(i.valor_presupuestado || 0), 0);
  const variacion = realIngresos - ingresosPresupuestados;

  const addItem = () => {
    setItems([...items, { ...EMPTY_ITEM, mes: mesActual, ano, id: `new-${Date.now()}` }]);
  };

  const removeItem = (id) => setItems(items.filter(i => i.id !== id));

  const updateItem = (id, field, val) => setItems(items.map(i => i.id === id ? { ...i, [field]: val } : i));

  const handleSave = async () => {
    setSaving(true);
    try {
      const toSave = mesItems.filter(i => i.concepto.trim());
      await api.post("/presupuesto", toSave.map(({ id, ...rest }) => rest));
      toast.success(`Presupuesto ${mesActual} ${ano} guardado`);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando");
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Presupuesto</h2>
          <p className="text-sm text-slate-500 mt-1">Plan presupuestal vs ejecución real desde Alegra</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={ano} onChange={(e) => setAno(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none">
            {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button onClick={loadData} disabled={loading}
            className="flex items-center gap-1.5 text-xs bg-white border border-slate-200 text-slate-600 px-3 py-2 rounded-lg hover:bg-slate-50">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Month tabs */}
      <div className="flex flex-wrap gap-1.5">
        {MESES.map((m) => {
          const cnt = items.filter(i => i.mes === m).length;
          return (
            <button key={m} onClick={() => setMesActual(m)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition ${mesActual === m ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "bg-white text-slate-600 border-slate-200 hover:border-[#0F2A5C]"}`}>
              {m} {cnt > 0 && <span className="ml-1 opacity-60">({cnt})</span>}
            </button>
          );
        })}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Presupuestado {mesActual}</span>
          <div className="text-2xl font-bold text-[#0F2A5C] mt-1">{formatCOP(totalPresupuestado)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Ingresos Reales (Alegra)</span>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{formatCOP(realIngresos)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Variación Ingresos</span>
          <div className={`text-2xl font-bold mt-1 ${variacion >= 0 ? "text-emerald-600" : "text-red-600"}`}>
            {variacion >= 0 ? "+" : ""}{formatCOP(variacion)}
          </div>
          <span className="text-xs text-slate-400">{variacion >= 0 ? "Por encima del presupuesto" : "Por debajo del presupuesto"}</span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-[#0F2A5C]" /></div>
      ) : (
        <>
          {/* CFO Instructions sync */}
          <CfoInstruccionesPanel instrucciones={cfoInstrucciones} />
          <CfoPresupuestoPanel presupuestos={cfoPresupuestos} mesActual={mesActual} />

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-[#0F2A5C]">Ítems Presupuesto — {mesActual} {ano}</span>
            <button onClick={addItem} className="flex items-center gap-1 text-xs bg-[#0F2A5C] text-white px-3 py-1.5 rounded-lg hover:bg-[#163A7A]">
              <Plus size={12} /> Agregar línea
            </button>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
              <th className="px-4 py-2.5 text-left">Concepto</th>
              <th className="px-4 py-2.5 text-left">Categoría</th>
              <th className="px-4 py-2.5 text-right">Valor Presupuestado</th>
              <th className="px-4 py-2.5 text-center w-12"></th>
            </tr></thead>
            <tbody>
              {mesItems.map((item, i) => (
                <tr key={item.id} className={`border-b border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/40"}`}>
                  <td className="px-4 py-2">
                    <input className="w-full border-0 bg-transparent focus:bg-white focus:border focus:rounded px-1 py-0.5 text-sm outline-none"
                      value={item.concepto} onChange={(e) => updateItem(item.id, "concepto", e.target.value)} placeholder="Descripción del ítem..." />
                  </td>
                  <td className="px-4 py-2">
                    <select value={item.categoria} onChange={(e) => updateItem(item.id, "categoria", e.target.value)}
                      className="border-0 bg-transparent text-sm outline-none focus:bg-white focus:border focus:rounded px-1 py-0.5 w-full">
                      {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <input type="number" className="w-full text-right border-0 bg-transparent focus:bg-white focus:border focus:rounded px-1 py-0.5 text-sm outline-none font-medium"
                      value={item.valor_presupuestado} onChange={(e) => updateItem(item.id, "valor_presupuestado", e.target.value)} />
                  </td>
                  <td className="px-4 py-2 text-center">
                    <button onClick={() => removeItem(item.id)} className="text-slate-300 hover:text-red-500"><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
              {mesItems.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400 text-sm">
                  Sin ítems. Haz clic en "Agregar línea" para comenzar.
                </td></tr>
              )}
              <tr className="bg-[#F0F4FF] border-t-2 border-[#C7D7FF]">
                <td colSpan={2} className="px-4 py-3 text-sm font-bold text-[#0F2A5C]">Total presupuestado</td>
                <td className="px-4 py-3 text-right text-sm font-bold text-[#0F2A5C]">{formatCOP(totalPresupuestado)}</td>
                <td />
              </tr>
            </tbody>
          </table>
          <div className="px-4 py-3 flex justify-end">
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-2 bg-[#0F2A5C] text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[#163A7A] disabled:opacity-50"
              data-testid="save-presupuesto-btn">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Guardar Presupuesto
            </button>
          </div>
        </div>
        </>
      )}
    </div>
  );
}
