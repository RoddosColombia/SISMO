import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Upload, RefreshCw, CheckCircle2, XCircle, Loader2, Bike,
  TrendingUp, Package, Tag, AlertCircle, Edit2, Trash2, Link, ShoppingBag, FileDown,
  DollarSign, Download, X, CheckCircle
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP, formatDate } from "../utils/formatters";
import { exportExcel } from "../utils/exportUtils";

const ESTADO_STYLE = {
  Disponible: { bg: "#15803d", text: "#fff" },
  Vendida: { bg: "#92400e", text: "#fff" },
  Entregada: { bg: "#1d4ed8", text: "#fff" },
  "Pendiente datos": { bg: "#9a3412", text: "#fff" },
  Anulada: { bg: "#111827", text: "#fff" },
};

const FILTER_STATES = [
  { key: "TODAS", label: "TODAS" },
  { key: "Disponible", label: "Disponible" },
  { key: "Vendida", label: "Vendida" },
  { key: "Entregada", label: "Entregada" },
  { key: "Pendiente datos", label: "Pendiente datos" },
  { key: "Anulada", label: "Anulada" },
];

const FILTER_BG = {
  TODAS: "#374151",
  Disponible: "#15803d",
  Vendida: "#92400e",
  Entregada: "#1d4ed8",
  "Pendiente datos": "#9a3412",
  Anulada: "#111827",
};

function getFilterCount(key, stats) {
  switch (key) {
    case "TODAS": return Math.max(0, (stats.total || 0) - (stats.anuladas || 0));
    case "Disponible": return stats.disponibles || 0;
    case "Vendida": return stats.vendidas || 0;
    case "Entregada": return stats.entregadas || 0;
    case "Pendiente datos": return stats.pendiente_datos || 0;
    case "Anulada": return stats.anuladas || 0;
    default: return 0;
  }
}

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
  const style = ESTADO_STYLE[estado] || { bg: "#6B7280", text: "#fff" };
  return (
    <span
      className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
      style={{ background: style.bg, color: style.text }}
    >
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
  const [filterEstado, setFilterEstado] = useState("Disponible");
  const [editId, setEditId] = useState(null);
  const [editData, setEditData] = useState({});
  const [selling, setSelling] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [sellForm, setSellForm] = useState({ cliente_id: "", cliente_nombre: "", precio_venta: "", tipo_pago: "contado", cuotas: 12, valor_cuota: "", include_iva: true, ipoc_pct: 8 });
  const [sellLoading, setSellLoading] = useState(false);
  const [showCostModal, setShowCostModal] = useState(false);
  const [costosFile, setCostosFile] = useState(null);
  const [costosLoading, setCostosLoading] = useState(false);
  const [costosPreview, setCostosPreview] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const fileRef = useRef();
  const costFileRef = useRef();
  const prevStatsRef = useRef(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const apiEstado = filterEstado === "TODAS" ? undefined : filterEstado || undefined;
      const [motosRes, statsRes] = await Promise.all([
        api.get("/inventario/motos", { params: { estado: apiEstado } }),
        api.get("/inventario/stats"),
      ]);
      let motosData = motosRes.data;
      if (filterEstado === "TODAS") {
        motosData = motosData.filter((m) => m.estado !== "Anulada");
      }
      setMotos(motosData);
      setStats(statsRes.data);
      prevStatsRef.current = statsRes.data;
    } catch {
      toast.error("Error cargando inventario");
    } finally {
      setLoading(false);
    }
  }, [api, filterEstado]);

  useEffect(() => { loadData(); }, [loadData]);

  // Polling cada 30s — refresca si los contadores cambian
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const statsRes = await api.get("/inventario/stats");
        const newStats = statsRes.data;
        const prev = prevStatsRef.current;
        if (prev && (
          newStats.total !== prev.total ||
          newStats.disponibles !== prev.disponibles ||
          newStats.vendidas !== prev.vendidas ||
          newStats.entregadas !== prev.entregadas
        )) {
          prevStatsRef.current = newStats;
          setStats(newStats);
          const apiEstado = filterEstado === "TODAS" ? undefined : filterEstado || undefined;
          const motosRes = await api.get("/inventario/motos", { params: { estado: apiEstado } });
          let motosData = motosRes.data;
          if (filterEstado === "TODAS") motosData = motosData.filter((m) => m.estado !== "Anulada");
          setMotos(motosData);
          toast.info("Inventario actualizado automáticamente");
        }
      } catch {
        // ignore polling errors silently
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [api, filterEstado]);

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

  const handleExportExcel = () => {    exportExcel({
      filename: `inventario-auteco-${new Date().toISOString().slice(0, 10)}`,
      sheets: [{
        name: "Inventario Motos",
        columns: [
          { key: "placa", label: "Placa", width: 14 },
          { key: "marca", label: "Marca", width: 16 },
          { key: "version", label: "Versión", width: 22 },
          { key: "color", label: "Color", width: 14 },
          { key: "ano_modelo", label: "Año", width: 10 },
          { key: "motor", label: "Motor", width: 16 },
          { key: "chasis", label: "Chasis", width: 18 },
          { key: "costo", label: "Costo", width: 16 },
          { key: "iva_compra", label: "IVA Compra", width: 16 },
          { key: "ipoconsumo", label: "IPOC", width: 14 },
          { key: "total", label: "Total", width: 16 },
          { key: "estado", label: "Estado", width: 14 },
          { key: "ubicacion", label: "Ubicación", width: 20 },
        ],
        rows: motos.map(m => ({
          placa: m.placa || "—",
          marca: m.marca || "—",
          version: m.version || "—",
          color: m.color || "—",
          ano_modelo: m.ano_modelo || "—",
          motor: m.motor || "—",
          chasis: m.chasis || "—",
          costo: parseFloat(m.costo || 0),
          iva_compra: parseFloat(m.iva_compra || 0),
          ipoconsumo: parseFloat(m.ipoconsumo || 0),
          total: parseFloat(m.total || 0),
          estado: m.estado || "—",
          ubicacion: m.ubicacion || "—",
        })),
      }],
    });
  };

  const handleDownloadCostTemplate = async () => {
    const API = process.env.REACT_APP_BACKEND_URL;
    window.open(`${API}/api/inventario/plantilla-costos`, "_blank");
  };

  const handleCostFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCostosFile(file);
    setCostosLoading(true);
    setCostosPreview(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/inventario/cargar-costos/preview", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setCostosPreview(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error procesando plantilla");
      setCostosFile(null);
    } finally {
      setCostosLoading(false);
    }
  };

  const handleConfirmCostos = async () => {
    if (!costosPreview?.actualizadas) return;
    setConfirming(true);
    try {
      const res = await api.post("/inventario/cargar-costos/confirmar", { actualizadas: costosPreview.actualizadas });
      toast.success(`${res.data.guardadas} motos actualizadas con costos de compra`);
      setShowCostModal(false);
      setCostosPreview(null);
      setCostosFile(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando costos");
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="space-y-6 max-w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Motos</h2>
          <p className="text-sm text-slate-500 mt-1">Inventario de motos Auteco — importa PDF de compra y gestiona disponibilidad y ventas</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs bg-white border border-slate-200 text-slate-600 px-3 py-2 rounded-lg hover:bg-slate-50 transition"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Actualizar
          </button>
          {!loading && motos.length > 0 && (
            <button onClick={handleExportExcel} data-testid="export-excel-inventory-btn"
              className="flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg transition">
              <FileDown size={13} /> Excel
            </button>
          )}
          <label className="flex items-center gap-2 bg-[#0F2A5C] hover:bg-[#163A7A] text-white text-sm font-medium px-4 py-2 rounded-lg cursor-pointer transition" data-testid="upload-pdf-btn">
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
            {uploading ? "Procesando PDF..." : "Importar Factura PDF"}
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
          <button
            onClick={() => setShowCostModal(true)}
            data-testid="carga-costos-btn"
            className="flex items-center gap-1.5 text-sm font-medium bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg transition"
          >
            <DollarSign size={14} /> Cargar Costos
          </button>
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

      {/* Filter bar */}
      {!loading && stats.total !== undefined && (
        <div className="flex items-center gap-2 flex-wrap" data-testid="inventory-filter-bar">
          {FILTER_STATES.map((f) => {
            const isActive = filterEstado === f.key;
            const bg = FILTER_BG[f.key] || "#374151";
            const count = getFilterCount(f.key, stats);
            return (
              <button
                key={f.key}
                onClick={() => setFilterEstado(f.key)}
                data-testid={`filter-btn-${f.key.toLowerCase().replace(/ /g, "-")}`}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-semibold transition-all"
                style={
                  isActive
                    ? { background: bg, color: "#fff", border: "2px solid #fff", boxShadow: `0 0 0 2px ${bg}` }
                    : { background: "#F9FAFB", color: "#374151", border: "1px solid #E5E7EB" }
                }
              >
                {f.label}
                <span className="text-[10px] font-bold opacity-80 ml-0.5">{count}</span>
              </button>
            );
          })}
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
      {/* Modal Carga de Costos */}
      {showCostModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" data-testid="cost-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="font-bold text-[#0F2A5C] text-base">Carga inicial de costos de compra</h3>
                <p className="text-xs text-slate-500 mt-0.5">Actualiza el precio de compra de cada moto para el cálculo de margen</p>
              </div>
              <button onClick={() => { setShowCostModal(false); setCostosPreview(null); setCostosFile(null); }} className="text-slate-400 hover:text-slate-700">
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">1</div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-blue-800">Descarga la plantilla Excel</p>
                    <p className="text-xs text-blue-600 mt-0.5">Contiene todas las motos con sus datos actuales</p>
                    <button onClick={handleDownloadCostTemplate} data-testid="download-cost-template-btn"
                      className="mt-2 flex items-center gap-1.5 text-xs font-bold text-blue-700 bg-blue-100 hover:bg-blue-200 px-3 py-1.5 rounded-lg transition">
                      <Download size={12} /> Descargar Plantilla (.xlsx)
                    </button>
                  </div>
                </div>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-amber-500 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">2</div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-amber-800">Sube la plantilla con los costos llenados</p>
                    <p className="text-xs text-amber-700 mt-0.5">Llena columnas: precio_compra, iva_compra, ipoc_compra</p>
                    <label className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold text-amber-800 bg-amber-100 hover:bg-amber-200 px-3 py-1.5 rounded-lg transition cursor-pointer" data-testid="upload-cost-file-btn">
                      {costosLoading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
                      {costosFile ? costosFile.name : "Seleccionar archivo .xlsx"}
                      <input ref={costFileRef} type="file" accept=".xlsx" className="hidden" onChange={handleCostFileChange} disabled={costosLoading} />
                    </label>
                  </div>
                </div>
              </div>
              {costosPreview && (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700">Vista previa — {costosPreview.actualizadas?.length || 0} motos</span>
                    {costosPreview.no_encontradas?.length > 0 && <span className="text-xs text-amber-600 font-medium">{costosPreview.no_encontradas.length} no encontradas</span>}
                  </div>
                  <div className="max-h-52 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-100 sticky top-0">
                        <tr>
                          <th className="px-3 py-1.5 text-left">Chasis</th>
                          <th className="px-3 py-1.5 text-right">P. Compra</th>
                          <th className="px-3 py-1.5 text-right">IVA</th>
                          <th className="px-3 py-1.5 text-right">IPOC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {costosPreview.actualizadas?.map((r, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-3 py-1.5 font-mono font-semibold text-[#0F2A5C] text-[10px]">{r.chasis}</td>
                            <td className="px-3 py-1.5 text-right">{formatCOP(r.precio_compra || 0)}</td>
                            <td className="px-3 py-1.5 text-right">{formatCOP(r.iva_compra || 0)}</td>
                            <td className="px-3 py-1.5 text-right">{formatCOP(r.ipoc_compra || 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="px-4 py-3 bg-emerald-50 border-t border-slate-200">
                    <button onClick={handleConfirmCostos} disabled={confirming} data-testid="confirm-costos-btn"
                      className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50">
                      {confirming ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                      Confirmar y guardar {costosPreview.actualizadas?.length} costos
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
