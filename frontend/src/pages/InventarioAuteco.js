import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Upload, RefreshCw, CheckCircle2, XCircle, Loader2, Bike,
  TrendingUp, Package, Tag, AlertCircle, Edit2, Trash2, Link, ShoppingBag
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP, formatDate } from "../utils/formatters";

const ESTADO_COLORS = {
  Disponible: "bg-emerald-100 text-emerald-700 border-emerald-200",
  Vendida: "bg-blue-100 text-blue-700 border-blue-200",
  Entregada: "bg-slate-100 text-slate-600 border-slate-200",
};

function StatCard({ label, value, sub, color }) {
  return (
    <div className={`bg-white rounded-xl border p-4 flex flex-col gap-1 shadow-sm`}>
      <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</span>
      <span className={`text-2xl font-bold ${color || "text-[#0F2A5C]"}`}>{value}</span>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

function EstadoBadge({ estado }) {
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${ESTADO_COLORS[estado] || "bg-slate-100 text-slate-500 border-slate-200"}`}>
      {estado}
    </span>
  );
}

export default function InventarioAuteco() {
  const { api } = useAuth();
  const [motos, setMotos] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [registeringId, setRegisteringId] = useState(null);
  const [filterEstado, setFilterEstado] = useState("");
  const [editId, setEditId] = useState(null);
  const [editData, setEditData] = useState({});
  const [selling, setSelling] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [sellForm, setSellForm] = useState({ cliente_id: "", cliente_nombre: "", precio_venta: "", tipo_pago: "contado", cuotas: 12, valor_cuota: "", include_iva: true, ipoc_pct: 8 });
  const [sellLoading, setSellLoading] = useState(false);
  const fileRef = useRef();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [motosRes, statsRes] = await Promise.all([
        api.get("/inventario/motos", { params: { estado: filterEstado || undefined } }),
        api.get("/inventario/stats"),
      ]);
      setMotos(motosRes.data);
      setStats(statsRes.data);
    } catch {
      toast.error("Error cargando inventario");
    } finally {
      setLoading(false);
    }
  }, [api, filterEstado]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/inventario/upload-pdf", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${res.data.inserted} moto(s) importada(s) desde ${file.name}`);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error procesando PDF");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleRegisterAlegra = async (moto) => {
    setRegisteringId(moto.id);
    try {
      const res = await api.post(`/inventario/motos/${moto.id}/register-alegra`);
      toast.success(`Moto registrada en Alegra — ID: ${res.data.alegra_item_id}`);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando en Alegra");
    } finally {
      setRegisteringId(null);
    }
  };

  const handleEditSave = async (id) => {
    try {
      await api.put(`/inventario/motos/${id}`, editData);
      toast.success("Moto actualizada");
      setEditId(null);
      loadData();
    } catch {
      toast.error("Error actualizando");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar esta moto del inventario?")) return;
    try {
      await api.delete(`/inventario/motos/${id}`);
      toast.success("Moto eliminada");
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error eliminando");
    }
  };

  const openSellModal = async (moto) => {
    setSelling(moto);
    setSellForm({ cliente_id: "", cliente_nombre: "", precio_venta: moto.total || "", tipo_pago: "contado", cuotas: 12, valor_cuota: "", include_iva: true, ipoc_pct: 8 });
    try {
      const res = await api.get("/alegra/contacts");
      setContacts(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  const handleSell = async () => {
    if (!sellForm.cliente_id || !sellForm.precio_venta) { toast.error("Selecciona cliente y precio"); return; }
    setSellLoading(true);
    try {
      const res = await api.post(`/inventario/motos/${selling.id}/vender`, {
        cliente_id: sellForm.cliente_id,
        cliente_nombre: sellForm.cliente_nombre || contacts.find(c => String(c.id) === String(sellForm.cliente_id))?.name || "",
        precio_venta: parseFloat(sellForm.precio_venta),
        tipo_pago: sellForm.tipo_pago,
        cuotas: parseInt(sellForm.cuotas) || 1,
        valor_cuota: sellForm.valor_cuota ? parseFloat(sellForm.valor_cuota) : null,
        include_iva: sellForm.include_iva,
        ipoc_pct: parseFloat(sellForm.ipoc_pct) || 0,
      });
      toast.success(res.data.message);
      setSelling(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error procesando venta");
    } finally {
      setSellLoading(false);
    }
  };

  const startEdit = (moto) => {
    setEditId(moto.id);
    setEditData({ placa: moto.placa || "", estado: moto.estado, ubicacion: moto.ubicacion || "" });
  };

  return (
    <div className="space-y-6 max-w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Inventario Auteco</h2>
          <p className="text-sm text-slate-500 mt-1">Importa facturas PDF de Auteco y registra el inventario en Alegra</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs bg-white border border-slate-200 text-slate-600 px-3 py-2 rounded-lg hover:bg-slate-50 transition"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Actualizar
          </button>
          <label className="flex items-center gap-2 bg-[#0F2A5C] hover:bg-[#163A7A] text-white text-sm font-medium px-4 py-2 rounded-lg cursor-pointer transition" data-testid="upload-pdf-btn">
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
            {uploading ? "Procesando PDF..." : "Importar Factura PDF"}
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Motos" value={stats.total || 0} color="text-[#0F2A5C]" />
        <StatCard label="Disponibles" value={stats.disponibles || 0} color="text-emerald-600" sub="En bodega" />
        <StatCard label="Vendidas/Entregadas" value={(stats.vendidas || 0) + (stats.entregadas || 0)} color="text-blue-600" />
        <StatCard label="Inversión Total" value={formatCOP(stats.total_inversion || 0)} color="text-[#C9A84C]" sub="Costo + IVA + IPOC" />
      </div>

      {/* Upload hint */}
      {!loading && motos.length === 0 && (
        <div className="bg-[#F0F4FF] border-2 border-dashed border-[#C7D7FF] rounded-2xl p-10 text-center">
          <Bike size={40} className="mx-auto text-[#0F2A5C] opacity-40 mb-3" />
          <p className="text-[#0F2A5C] font-semibold text-base">No hay motos en inventario</p>
          <p className="text-slate-500 text-sm mt-1">Importa una factura PDF de Auteco para comenzar</p>
        </div>
      )}

      {/* Filter */}
      {motos.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Filtrar por estado:</span>
          {["", "Disponible", "Vendida", "Entregada"].map((e) => (
            <button
              key={e}
              onClick={() => setFilterEstado(e)}
              className={`text-xs px-3 py-1 rounded-full border transition ${filterEstado === e ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "bg-white text-slate-600 border-slate-200 hover:border-[#0F2A5C]"}`}
            >
              {e || "Todos"}
            </button>
          ))}
        </div>
      )}

      {/* Table */}
      {motos.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#0F2A5C] text-white text-xs uppercase">
                  <th className="px-3 py-3 text-left font-semibold">Placa</th>
                  <th className="px-3 py-3 text-left font-semibold">Marca / Versión</th>
                  <th className="px-3 py-3 text-left font-semibold">Color</th>
                  <th className="px-3 py-3 text-left font-semibold">Año</th>
                  <th className="px-3 py-3 text-left font-semibold">Motor</th>
                  <th className="px-3 py-3 text-left font-semibold">Chasis</th>
                  <th className="px-3 py-3 text-right font-semibold">Costo</th>
                  <th className="px-3 py-3 text-right font-semibold">IVA Compra</th>
                  <th className="px-3 py-3 text-right font-semibold">IPOC</th>
                  <th className="px-3 py-3 text-right font-semibold">Total</th>
                  <th className="px-3 py-3 text-left font-semibold">Estado</th>
                  <th className="px-3 py-3 text-left font-semibold">Ubicación</th>
                  <th className="px-3 py-3 text-left font-semibold">Alegra</th>
                  <th className="px-3 py-3 text-left font-semibold">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {motos.map((moto, i) => (
                  <tr
                    key={moto.id}
                    className={`border-b border-slate-100 hover:bg-[#F0F4FF]/50 transition ${i % 2 === 0 ? "bg-white" : "bg-slate-50/40"}`}
                    data-testid={`moto-row-${moto.id}`}
                  >
                    <td className="px-3 py-2.5">
                      {editId === moto.id ? (
                        <input
                          className="w-20 border rounded px-1 py-0.5 text-xs"
                          value={editData.placa}
                          onChange={(e) => setEditData({ ...editData, placa: e.target.value })}
                          placeholder="AAA000"
                        />
                      ) : (
                        <span className="font-mono text-xs font-semibold text-[#0F2A5C]">{moto.placa || "—"}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-semibold text-[#0F2A5C] text-xs">{moto.marca}</div>
                      <div className="text-[11px] text-slate-500">{moto.version}</div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-700">{moto.color || "—"}</td>
                    <td className="px-3 py-2.5 text-xs text-center font-medium">{moto.ano_modelo || "—"}</td>
                    <td className="px-3 py-2.5 font-mono text-[10px] text-slate-600">{moto.motor || "—"}</td>
                    <td className="px-3 py-2.5 font-mono text-[10px] text-slate-600">{moto.chasis || "—"}</td>
                    <td className="px-3 py-2.5 text-right text-xs">{formatCOP(moto.costo)}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-amber-700">{formatCOP(moto.iva_compra)}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-purple-700">{formatCOP(moto.ipoconsumo)}</td>
                    <td className="px-3 py-2.5 text-right text-xs font-bold text-[#0F2A5C]">{formatCOP(moto.total)}</td>
                    <td className="px-3 py-2.5">
                      {editId === moto.id ? (
                        <select
                          className="text-xs border rounded px-1 py-0.5"
                          value={editData.estado}
                          onChange={(e) => setEditData({ ...editData, estado: e.target.value })}
                        >
                          <option>Disponible</option>
                          <option>Vendida</option>
                          <option>Entregada</option>
                        </select>
                      ) : (
                        <EstadoBadge estado={moto.estado} />
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-600">
                      {editId === moto.id ? (
                        <input
                          className="w-24 border rounded px-1 py-0.5 text-xs"
                          value={editData.ubicacion}
                          onChange={(e) => setEditData({ ...editData, ubicacion: e.target.value })}
                        />
                      ) : (
                        moto.ubicacion || "BODEGA"
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {moto.alegra_item_id ? (
                        <span className="flex items-center gap-1 text-[10px] text-emerald-600 font-semibold">
                          <CheckCircle2 size={12} />Registrado
                        </span>
                      ) : (
                        <button
                          onClick={() => handleRegisterAlegra(moto)}
                          disabled={registeringId === moto.id}
                          className="flex items-center gap-1 text-[10px] bg-[#0F2A5C] text-white px-2 py-1 rounded hover:bg-[#163A7A] transition disabled:opacity-50"
                          data-testid={`register-alegra-${moto.id}`}
                        >
                          {registeringId === moto.id ? <Loader2 size={10} className="animate-spin" /> : <Link size={10} />}
                          Alegra
                        </button>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1">
                        {moto.estado === "Disponible" && (
                          <button
                            onClick={() => openSellModal(moto)}
                            className="flex items-center gap-1 text-[10px] bg-[#C9A84C] text-[#0F2A5C] font-bold px-2 py-1 rounded hover:bg-[#b8903e] transition"
                            data-testid={`sell-moto-${moto.id}`}
                          >
                            <ShoppingBag size={10} /> Vender
                          </button>
                        )}
                        {editId === moto.id ? (
                          <>
                            <button onClick={() => handleEditSave(moto.id)} className="text-[10px] bg-emerald-600 text-white px-2 py-1 rounded hover:bg-emerald-700">Guardar</button>
                            <button onClick={() => setEditId(null)} className="text-[10px] bg-slate-200 text-slate-700 px-2 py-1 rounded hover:bg-slate-300">Cancelar</button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => startEdit(moto)} className="p-1 text-slate-400 hover:text-[#0F2A5C]"><Edit2 size={13} /></button>
                            <button onClick={() => handleDelete(moto.id)} className="p-1 text-slate-400 hover:text-red-500"><Trash2 size={13} /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer summary */}
          <div className="px-4 py-3 bg-[#F0F4FF] border-t border-slate-200 flex flex-wrap gap-4 text-xs text-slate-600">
            <span><strong className="text-[#0F2A5C]">{motos.length}</strong> motos mostradas</span>
            <span>Costo total: <strong className="text-[#0F2A5C]">{formatCOP(motos.reduce((s, m) => s + (m.costo || 0), 0))}</strong></span>
            <span>IVA total: <strong className="text-amber-700">{formatCOP(motos.reduce((s, m) => s + (m.iva_compra || 0), 0))}</strong></span>
            <span>Inversión total: <strong className="text-[#C9A84C]">{formatCOP(motos.reduce((s, m) => s + (m.total || 0), 0))}</strong></span>
          </div>
        </div>
      )}

      {/* Sell Modal */}
      {selling && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-[500px] p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-[#0F2A5C] mb-1">Registrar Venta de Moto</h3>
            <p className="text-sm text-slate-500 mb-4">
              {selling.marca} {selling.version} — Chasis: {selling.chasis}
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Cliente *</label>
                <select value={sellForm.cliente_id}
                  onChange={(e) => {
                    const c = contacts.find(c => String(c.id) === e.target.value);
                    setSellForm({ ...sellForm, cliente_id: e.target.value, cliente_nombre: c?.name || "" });
                  }}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                  data-testid="sell-client-select">
                  <option value="">Seleccionar cliente...</option>
                  {contacts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Precio de venta *</label>
                <input type="number" value={sellForm.precio_venta}
                  onChange={(e) => setSellForm({ ...sellForm, precio_venta: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                  placeholder="Precio final al cliente" data-testid="sell-price-input" />
                <p className="text-[10px] text-slate-400 mt-0.5">Costo + impuestos: {formatCOP(selling.total)}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Tipo de pago</label>
                  <select value={sellForm.tipo_pago} onChange={(e) => setSellForm({ ...sellForm, tipo_pago: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none">
                    <option value="contado">Contado</option>
                    <option value="credito">Crédito</option>
                    <option value="leasing">Leasing</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">IPOC %</label>
                  <select value={sellForm.ipoc_pct} onChange={(e) => setSellForm({ ...sellForm, ipoc_pct: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none">
                    <option value={0}>0% (No aplica)</option>
                    <option value={8}>8% (≤125cc)</option>
                    <option value={16}>16% (&gt;125cc)</option>
                  </select>
                </div>
              </div>
              {sellForm.tipo_pago === "credito" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">N° cuotas</label>
                    <input type="number" value={sellForm.cuotas} onChange={(e) => setSellForm({ ...sellForm, cuotas: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Valor cuota</label>
                    <input type="number" value={sellForm.valor_cuota} onChange={(e) => setSellForm({ ...sellForm, valor_cuota: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" placeholder="$" />
                  </div>
                </div>
              )}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={sellForm.include_iva}
                  onChange={(e) => setSellForm({ ...sellForm, include_iva: e.target.checked })} className="rounded" />
                <span className="text-slate-700">Incluir IVA 19% en la factura Alegra</span>
              </label>
              {sellForm.precio_venta && (
                <div className="bg-[#F0F4FF] rounded-xl p-3 text-xs space-y-1">
                  <div className="flex justify-between"><span>Precio base</span><span className="font-semibold">{formatCOP(sellForm.precio_venta)}</span></div>
                  {sellForm.include_iva && <div className="flex justify-between text-amber-700"><span>IVA 19%</span><span>{formatCOP(parseFloat(sellForm.precio_venta || 0) * 0.19)}</span></div>}
                  <div className="flex justify-between font-bold text-[#0F2A5C] pt-1 border-t border-[#C7D7FF]">
                    <span>Total factura</span><span>{formatCOP(parseFloat(sellForm.precio_venta || 0) * (sellForm.include_iva ? 1.19 : 1))}</span>
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={handleSell} disabled={sellLoading}
                className="flex-1 bg-[#C9A84C] text-[#0F2A5C] font-bold py-3 rounded-xl text-sm hover:bg-[#b8903e] disabled:opacity-50 flex items-center justify-center gap-2"
                data-testid="confirm-sell-btn">
                {sellLoading ? <Loader2 size={16} className="animate-spin" /> : <ShoppingBag size={16} />}
                Crear Factura en Alegra
              </button>
              <button onClick={() => setSelling(null)} className="px-4 py-3 border rounded-xl text-sm text-slate-600 hover:bg-slate-50">Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
