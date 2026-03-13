import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import { format } from "date-fns";
import {
  Wrench, Plus, Search, Package, Tag, FileText, BarChart2,
  AlertTriangle, CheckCircle, X, Edit3, Trash2, Layers, ShoppingBag, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (n) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);

// ─── Product Form Modal ───────────────────────────────────────────────────────
const ProductModal = ({ item, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [catalog, setCatalog] = useState([]);
  const [form, setForm] = useState(item ? { ...item } : {
    referencia: "", descripcion: "", marca: "", modelos_compatibles: [],
    tipo: "unidad", componentes: [], precio_costo: "", precio_venta: "",
    stock: 0, stock_minimo: 5, unidad_medida: "und",
  });
  const [loading, setLoading] = useState(false);
  const [modelsInput, setModelsInput] = useState((item?.modelos_compatibles || []).join(", "));

  useEffect(() => {
    axios.get(`${API}/api/repuestos/catalogo?tipo=unidad`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setCatalog(r.data || [])).catch(() => {});
  }, [token]);

  const handleAddComponent = () => {
    setForm(f => ({ ...f, componentes: [...(f.componentes || []), { repuesto_id: "", referencia: "", descripcion: "", cantidad: 1 }] }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const body = { ...form, modelos_compatibles: modelsInput.split(",").map(s => s.trim()).filter(Boolean), precio_costo: parseFloat(form.precio_costo || 0), precio_venta: parseFloat(form.precio_venta || 0), stock: parseInt(form.stock || 0), stock_minimo: parseInt(form.stock_minimo || 5) };
    try {
      if (item) {
        await axios.put(`${API}/api/repuestos/catalogo/${item.id}`, body, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Repuesto actualizado");
      } else {
        await axios.post(`${API}/api/repuestos/catalogo`, body, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Repuesto creado");
      }
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando repuesto");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white flex items-center justify-between p-5 border-b z-10">
          <h3 className="font-bold text-slate-800">{item ? "Editar Repuesto" : "Nuevo Repuesto / Kit"}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="flex gap-3">
            <button type="button" onClick={() => setForm(f => ({ ...f, tipo: "unidad" }))}
              className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-all ${form.tipo === "unidad" ? "bg-[#00A9E0] text-white border-[#00A9E0]" : "border-slate-300 text-slate-600 hover:border-[#00A9E0]"}`}>
              <Package size={14} className="inline mr-1" /> Unidad
            </button>
            <button type="button" onClick={() => setForm(f => ({ ...f, tipo: "kit" }))}
              className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-all ${form.tipo === "kit" ? "bg-[#00A9E0] text-white border-[#00A9E0]" : "border-slate-300 text-slate-600 hover:border-[#00A9E0]"}`}>
              <Layers size={14} className="inline mr-1" /> Kit
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Referencia / SKU *</label>
              <input required value={form.referencia} onChange={e => setForm(f => ({ ...f, referencia: e.target.value }))}
                placeholder="REP-001" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Marca</label>
              <input value={form.marca} onChange={e => setForm(f => ({ ...f, marca: e.target.value }))}
                placeholder="Auteco, Bajaj..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Descripción *</label>
            <input required value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
              placeholder="Ej: Filtro de aire Boxer 150" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Modelos compatibles (separados por coma)</label>
            <input value={modelsInput} onChange={e => setModelsInput(e.target.value)}
              placeholder="Boxer 150, Pulsar 200, Discover 125" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          {form.tipo === "unidad" && (
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">P. Costo</label>
                <input type="number" value={form.precio_costo} onChange={e => setForm(f => ({ ...f, precio_costo: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">P. Venta *</label>
                <input required type="number" value={form.precio_venta} onChange={e => setForm(f => ({ ...f, precio_venta: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Stock inicial</label>
                <input type="number" value={form.stock} onChange={e => setForm(f => ({ ...f, stock: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
          )}
          {form.tipo === "kit" && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Componentes del kit</label>
                <button type="button" onClick={handleAddComponent} className="text-xs text-[#00A9E0] font-medium hover:underline">+ Agregar componente</button>
              </div>
              <div className="space-y-2">
                {(form.componentes || []).map((comp, idx) => (
                  <div key={idx} className="flex gap-2 items-center bg-slate-50 rounded-lg p-2">
                    <select value={comp.repuesto_id} onChange={e => {
                      const sel = catalog.find(c => c.id === e.target.value);
                      const comps = [...form.componentes];
                      comps[idx] = { ...comps[idx], repuesto_id: e.target.value, referencia: sel?.referencia || "", descripcion: sel?.descripcion || "" };
                      setForm(f => ({ ...f, componentes: comps }));
                    }} className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-xs">
                      <option value="">Seleccionar repuesto...</option>
                      {catalog.map(c => <option key={c.id} value={c.id}>{c.referencia} — {c.descripcion}</option>)}
                    </select>
                    <input type="number" min="1" value={comp.cantidad} onChange={e => {
                      const comps = [...form.componentes]; comps[idx] = { ...comps[idx], cantidad: parseInt(e.target.value) };
                      setForm(f => ({ ...f, componentes: comps }));
                    }} className="w-16 border border-slate-300 rounded px-2 py-1.5 text-xs text-center" placeholder="Cant" />
                    <button type="button" onClick={() => setForm(f => ({ ...f, componentes: f.componentes.filter((_, i) => i !== idx) }))}
                      className="text-red-400 hover:text-red-600"><X size={14} /></button>
                  </div>
                ))}
                {(form.componentes || []).length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-3">Agrega los repuestos que componen este kit</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">P. Venta kit *</label>
                  <input required type="number" value={form.precio_venta} onChange={e => setForm(f => ({ ...f, precio_venta: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">P. Costo kit</label>
                  <input type="number" value={form.precio_costo} onChange={e => setForm(f => ({ ...f, precio_costo: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Stock mínimo</label>
              <input type="number" value={form.stock_minimo} onChange={e => setForm(f => ({ ...f, stock_minimo: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Unidad de medida</label>
              <select value={form.unidad_medida} onChange={e => setForm(f => ({ ...f, unidad_medida: e.target.value }))}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
                <option value="und">Unidad</option>
                <option value="kit">Kit</option>
                <option value="par">Par</option>
                <option value="lt">Litro</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium">Cancelar</button>
            <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0] disabled:opacity-50">
              {loading ? "Guardando..." : item ? "Actualizar" : "Crear Repuesto"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Invoice Form Modal ────────────────────────────────────────────────────────
const FacturaModal = ({ onClose, onSuccess }) => {
  const { token } = useAuth();
  const [catalog, setCatalog] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [contactSearch, setContactSearch] = useState("");
  const [form, setForm] = useState({ cliente_id: "", cliente_nombre: "", cliente_nit: "", items: [], notas: "" });
  const [itemSearch, setItemSearch] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/api/repuestos/catalogo`, { headers: { Authorization: `Bearer ${token}` } }),
      axios.get(`${API}/api/alegra/contacts`, { headers: { Authorization: `Bearer ${token}` } }),
    ]).then(([c, con]) => { setCatalog(c.data || []); setContacts(con.data || []); }).catch(() => {});
  }, [token]);

  const addItem = (rep) => {
    if (form.items.find(i => i.repuesto_id === rep.id)) return;
    setForm(f => ({ ...f, items: [...f.items, { repuesto_id: rep.id, referencia: rep.referencia, descripcion: rep.descripcion, tipo: rep.tipo, cantidad: 1, precio_unitario: rep.precio_venta, descuento_pct: 0, iva_pct: 19 }] }));
    setItemSearch("");
  };

  const total = form.items.reduce((s, it) => {
    const base = it.precio_unitario * it.cantidad * (1 - it.descuento_pct / 100);
    return s + base + base * (it.iva_pct / 100);
  }, 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.items.length === 0) { toast.error("Agrega al menos un ítem a la factura"); return; }
    setLoading(true);
    try {
      await axios.post(`${API}/api/repuestos/facturas`, form, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Factura de repuestos creada en Alegra");
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error creando factura");
    } finally { setLoading(false); }
  };

  const filteredCatalog = catalog.filter(c => c.descripcion.toLowerCase().includes(itemSearch.toLowerCase()) || c.referencia.toLowerCase().includes(itemSearch.toLowerCase())).slice(0, 6);
  const filteredContacts = contacts.filter(c => c.name?.toLowerCase().includes(contactSearch.toLowerCase())).slice(0, 6);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-white flex items-center justify-between p-5 border-b z-10">
          <h3 className="font-bold text-slate-800 flex items-center gap-2"><ShoppingBag size={18} className="text-[#00A9E0]" />Nueva Factura de Repuestos</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Client */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Cliente *</label>
            <input value={contactSearch} onChange={e => setContactSearch(e.target.value)}
              placeholder="Buscar cliente en Alegra..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            {contactSearch && filteredContacts.length > 0 && (
              <div className="mt-1 border border-slate-200 rounded-lg shadow-sm">
                {filteredContacts.map(c => (
                  <button key={c.id} type="button" onClick={() => { setForm(f => ({ ...f, cliente_id: c.id, cliente_nombre: c.name, cliente_nit: c.identification || "" })); setContactSearch(c.name); }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-0">
                    <span className="font-medium">{c.name}</span>{c.identification && <span className="text-slate-400 text-xs ml-2">NIT: {c.identification}</span>}
                  </button>
                ))}
              </div>
            )}
            {form.cliente_nombre && <p className="text-xs text-green-600 mt-1">✓ {form.cliente_nombre}</p>}
          </div>

          {/* Item Search */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Agregar repuesto / kit</label>
            <input value={itemSearch} onChange={e => setItemSearch(e.target.value)}
              placeholder="Buscar por referencia o descripción..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
            {itemSearch && filteredCatalog.length > 0 && (
              <div className="mt-1 border border-slate-200 rounded-lg shadow-sm">
                {filteredCatalog.map(c => (
                  <button key={c.id} type="button" onClick={() => addItem(c)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b border-slate-100 last:border-0 flex items-center justify-between">
                    <div>
                      <span className="font-mono text-xs text-[#00A9E0] mr-2">{c.referencia}</span>
                      <span>{c.descripcion}</span>
                      <span className="text-xs text-slate-400 ml-2">{c.tipo === "kit" ? "Kit" : `Stock: ${c.stock}`}</span>
                    </div>
                    <span className="font-semibold text-slate-700 text-sm">{fmt(c.precio_venta)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Items */}
          {form.items.length > 0 && (
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2 text-left text-slate-500">Ítem</th>
                    <th className="px-3 py-2 text-center text-slate-500">Cant</th>
                    <th className="px-3 py-2 text-right text-slate-500">P.Unit</th>
                    <th className="px-3 py-2 text-center text-slate-500">IVA%</th>
                    <th className="px-3 py-2 text-right text-slate-500">Total</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {form.items.map((it, idx) => {
                    const base = it.precio_unitario * it.cantidad * (1 - it.descuento_pct / 100);
                    const lineTotal = base + base * (it.iva_pct / 100);
                    return (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="px-3 py-2">
                          <p className="font-medium text-slate-700">{it.referencia}</p>
                          <p className="text-slate-400 text-[10px]">{it.descripcion}</p>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <input type="number" min="1" value={it.cantidad} onChange={e => {
                            const items = [...form.items]; items[idx] = { ...items[idx], cantidad: parseInt(e.target.value) };
                            setForm(f => ({ ...f, items }));
                          }} className="w-12 border border-slate-300 rounded px-1 py-0.5 text-center text-xs" />
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-slate-700">{fmt(it.precio_unitario)}</td>
                        <td className="px-3 py-2 text-center">
                          <select value={it.iva_pct} onChange={e => {
                            const items = [...form.items]; items[idx] = { ...items[idx], iva_pct: parseFloat(e.target.value) };
                            setForm(f => ({ ...f, items }));
                          }} className="border border-slate-300 rounded px-1 py-0.5 text-xs">
                            <option value="19">19%</option>
                            <option value="5">5%</option>
                            <option value="0">0%</option>
                          </select>
                        </td>
                        <td className="px-3 py-2 text-right font-semibold text-slate-800">{fmt(lineTotal)}</td>
                        <td className="px-3 py-2">
                          <button type="button" onClick={() => setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }))}
                            className="text-red-300 hover:text-red-500"><X size={13} /></button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="bg-slate-50 border-t border-slate-200">
                  <tr><td colSpan={4} className="px-3 py-2 text-right font-bold text-slate-800">TOTAL</td><td className="px-3 py-2 text-right font-bold text-[#00A9E0] text-sm">{fmt(total)}</td><td /></tr>
                </tfoot>
              </table>
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Notas (opcional)</label>
            <input value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
              placeholder="Observaciones..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium">Cancelar</button>
            <button type="submit" disabled={loading || !form.cliente_id} className="flex-1 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0] disabled:opacity-50">
              {loading ? "Emitiendo..." : `Emitir Factura ${fmt(total)}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Repuestos() {
  const { token } = useAuth();
  const [tab, setTab] = useState("inventario");
  const [catalog, setCatalog] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tipoFilter, setTipoFilter] = useState("");
  const [showProduct, setShowProduct] = useState(false);
  const [showFactura, setShowFactura] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [adjusting, setAdjusting] = useState(null);
  const [adjustQty, setAdjustQty] = useState(0);
  const [adjustMotivo, setAdjustMotivo] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [catRes, facRes, statsRes] = await Promise.all([
        axios.get(`${API}/api/repuestos/catalogo`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/repuestos/facturas`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/repuestos/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setCatalog(catRes.data || []);
      setFacturas(facRes.data || []);
      setStats(statsRes.data || {});
    } catch { toast.error("Error cargando repuestos"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAjusteStock = async (item) => {
    try {
      await axios.post(`${API}/api/repuestos/catalogo/${item.id}/ajuste-stock`,
        { cantidad: parseInt(adjustQty), motivo: adjustMotivo },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Stock actualizado");
      setAdjusting(null); setAdjustQty(0); setAdjustMotivo("");
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || "Error ajustando stock"); }
  };

  const handleAnular = async (facId) => {
    if (!window.confirm("¿Anular esta factura? El stock será restaurado.")) return;
    try {
      await axios.post(`${API}/api/repuestos/facturas/${facId}/anular`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Factura anulada");
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || "Error anulando factura"); }
  };

  const filteredCatalog = catalog.filter(c =>
    (c.descripcion.toLowerCase().includes(search.toLowerCase()) || c.referencia.toLowerCase().includes(search.toLowerCase())) &&
    (!tipoFilter || c.tipo === tipoFilter)
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF6B35] to-[#cc5228] flex items-center justify-center">
            <Wrench size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Repuestos</h1>
            <p className="text-sm text-slate-500">Inventario y facturación de repuestos y accesorios</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchData} className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500"><RefreshCw size={16} /></button>
          {tab === "inventario" && <button onClick={() => { setEditItem(null); setShowProduct(true); }} className="flex items-center gap-2 px-4 py-2 bg-[#FF6B35] text-white rounded-lg text-sm font-medium hover:bg-[#cc5228]"><Plus size={16} />Nuevo Repuesto</button>}
          {tab === "facturas" && <button onClick={() => setShowFactura(true)} className="flex items-center gap-2 px-4 py-2 bg-[#00A9E0] text-white rounded-lg text-sm font-medium hover:bg-[#0090c0]"><Plus size={16} />Nueva Factura</button>}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4"><p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Productos</p><p className="text-xl font-bold text-slate-800 mt-1">{stats.total_productos || 0}</p><p className="text-xs text-slate-400">{stats.unidades || 0} unidades · {stats.kits || 0} kits</p></div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4"><p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Alertas stock</p><p className={`text-xl font-bold mt-1 ${stats.alertas_stock > 0 ? "text-red-500" : "text-green-600"}`}>{stats.alertas_stock || 0}</p><p className="text-xs text-slate-400">productos bajo mínimo</p></div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4"><p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Facturas emitidas</p><p className="text-xl font-bold text-slate-800 mt-1">{stats.facturas_emitidas || 0}</p></div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4"><p className="text-xs text-slate-400 uppercase tracking-wide font-medium">Valor inventario</p><p className="text-xl font-bold text-slate-800 mt-1">{fmt(catalog.filter(c => c.tipo === "unidad").reduce((s, c) => s + (c.precio_costo || 0) * (c.stock || 0), 0))}</p></div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
        {[{ id: "inventario", label: "Inventario", icon: Package }, { id: "facturas", label: "Historial Facturas", icon: FileText }].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === t.id ? "bg-white shadow text-slate-800" : "text-slate-500 hover:text-slate-700"}`}>
            <t.icon size={15} />{t.label}
          </button>
        ))}
      </div>

      {/* INVENTARIO TAB */}
      {tab === "inventario" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="flex-1 flex items-center gap-2 border border-slate-300 rounded-lg px-3 py-2">
              <Search size={14} className="text-slate-400" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar por referencia o descripción..." className="flex-1 text-sm outline-none bg-transparent" />
            </div>
            <select value={tipoFilter} onChange={e => setTipoFilter(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2 text-sm">
              <option value="">Todos</option>
              <option value="unidad">Unidades</option>
              <option value="kit">Kits</option>
            </select>
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Referencia</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Descripción</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase hidden md:table-cell">Tipo</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">P. Costo</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">P. Venta</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Stock</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Estado</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
                : filteredCatalog.length === 0 ? <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400">No hay repuestos registrados</td></tr>
                : filteredCatalog.map(item => {
                  const stockDisplay = item.tipo === "kit" ? (item.stock_virtual ?? "—") : item.stock;
                  const isLow = item.tipo === "unidad" && item.stock <= item.stock_minimo;
                  return (
                    <tr key={item.id} className="hover:bg-slate-50 transition-colors" data-testid={`repuesto-row-${item.id}`}>
                      <td className="px-4 py-3"><span className="font-mono text-xs font-semibold text-[#FF6B35]">{item.referencia}</span></td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-800">{item.descripcion}</p>
                        {item.marca && <p className="text-xs text-slate-400">{item.marca}</p>}
                        {item.modelos_compatibles?.length > 0 && <p className="text-xs text-slate-300">{item.modelos_compatibles.join(", ")}</p>}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${item.tipo === "kit" ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-600"}`}>
                          {item.tipo === "kit" ? <><Layers size={10} className="inline mr-1" />Kit</> : <><Package size={10} className="inline mr-1" />Unidad</>}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-500 text-xs">{fmt(item.precio_costo)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-800">{fmt(item.precio_venta)}</td>
                      <td className="px-4 py-3 text-center">
                        {adjusting?.id === item.id ? (
                          <div className="flex items-center gap-1 justify-center">
                            <input type="number" value={adjustQty} onChange={e => setAdjustQty(e.target.value)}
                              className="w-16 border border-slate-300 rounded px-1 py-0.5 text-xs text-center" placeholder="±" />
                            <button onClick={() => handleAjusteStock(item)} className="text-xs text-green-600 font-bold hover:underline">OK</button>
                            <button onClick={() => setAdjusting(null)} className="text-xs text-slate-400">×</button>
                          </div>
                        ) : (
                          <button onClick={() => { if (item.tipo === "unidad") { setAdjusting(item); setAdjustQty(0); } }}
                            className={`font-bold text-sm ${isLow ? "text-red-500" : "text-slate-700"} hover:text-[#00A9E0] transition-colors`}
                            title={item.tipo === "unidad" ? "Clic para ajustar stock" : "Stock calculado por componentes"}>
                            {stockDisplay}
                          </button>
                        )}
                        <p className="text-xs text-slate-400">min: {item.stock_minimo}</p>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {item.tipo === "kit" ? <span className="text-xs text-violet-500">virtual</span>
                        : isLow ? <span className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full"><AlertTriangle size={10} />Bajo</span>
                        : <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full"><CheckCircle size={10} />OK</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button onClick={() => { setEditItem(item); setShowProduct(true); }} className="p-1.5 text-slate-400 hover:text-[#00A9E0] hover:bg-slate-100 rounded"><Edit3 size={13} /></button>
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

      {/* FACTURAS TAB */}
      {tab === "facturas" && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Número</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Fecha</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cliente</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Ítems</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Total</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
              : facturas.length === 0 ? <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">No hay facturas registradas</td></tr>
              : facturas.map(f => (
                <tr key={f.id} className="hover:bg-slate-50" data-testid={`factura-row-${f.id}`}>
                  <td className="px-4 py-3"><span className="font-mono text-xs font-semibold text-[#00A9E0]">{f.numero}</span></td>
                  <td className="px-4 py-3 text-xs text-slate-500">{f.fecha}</td>
                  <td className="px-4 py-3"><p className="font-medium text-slate-800">{f.cliente_nombre}</p><p className="text-xs text-slate-400">{f.cliente_nit}</p></td>
                  <td className="px-4 py-3 text-center text-xs text-slate-500">{f.items?.length || 0}</td>
                  <td className="px-4 py-3 text-right font-bold text-slate-800">{fmt(f.total)}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${f.estado === "emitida" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>{f.estado}</span>
                  </td>
                  <td className="px-4 py-3">
                    {f.estado === "emitida" && (
                      <button onClick={() => handleAnular(f.id)} className="text-xs text-red-400 hover:text-red-600 font-medium">Anular</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showProduct && <ProductModal item={editItem} onClose={() => { setShowProduct(false); setEditItem(null); }} onSuccess={() => { setShowProduct(false); setEditItem(null); fetchData(); }} />}
      {showFactura && <FacturaModal onClose={() => setShowFactura(false)} onSuccess={() => { setShowFactura(false); fetchData(); }} />}
    </div>
  );
}
