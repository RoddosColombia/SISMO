import React, { useState, useEffect, useCallback } from "react";
import { Plus, Trash2, Save, Loader2, Building2, ShieldCheck, ShieldOff, RefreshCw, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

const EMPTY = { nombre: "", nit: "", es_autoretenedor: false, tipo_retencion: "compras_2.5", notas: "" };

function Badge({ active }) {
  return active ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
      <ShieldCheck size={10} /> Autoretenedor
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200">
      <ShieldOff size={10} /> Normal
    </span>
  );
}

function ProveedorModal({ proveedor, onClose, onSave, saving }) {
  const [form, setForm] = useState(proveedor || EMPTY);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-[#0F2A5C]">
            {proveedor ? "Editar Proveedor" : "Nuevo Proveedor"}
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg"><X size={16} /></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1 block">Razón Social *</label>
            <input
              value={form.nombre}
              onChange={e => set("nombre", e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
              placeholder="Ej: AUTECO KAWASAKI S.A.S."
              data-testid="proveedor-nombre-input"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1 block">NIT</label>
            <input
              value={form.nit}
              onChange={e => set("nit", e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
              placeholder="Ej: 860024781"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1 block">Tipo de Retención</label>
            <select
              value={form.tipo_retencion}
              onChange={e => set("tipo_retencion", e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
            >
              <option value="ninguna">Ninguna (autoretenedor)</option>
              <option value="compras_2.5">Compras 2.5%</option>
              <option value="servicios_4">Servicios 4%</option>
              <option value="honorarios_10">Honorarios 10%</option>
              <option value="honorarios_11">Honorarios PN 11%</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1 block">Notas</label>
            <input
              value={form.notas}
              onChange={e => set("notas", e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
              placeholder="Observaciones internas"
            />
          </div>

          {/* Autoretenedor toggle */}
          <div
            onClick={() => set("es_autoretenedor", !form.es_autoretenedor)}
            className={`flex items-center justify-between p-3 rounded-xl border-2 cursor-pointer transition ${
              form.es_autoretenedor ? "border-emerald-400 bg-emerald-50" : "border-slate-200 bg-slate-50"
            }`}
            data-testid="toggle-autoretenedor"
          >
            <div>
              <p className="text-sm font-semibold text-[#0F2A5C]">Es Autoretenedor</p>
              <p className="text-[10px] text-slate-500">NO se aplica ReteFuente a este proveedor</p>
            </div>
            <div className={`w-10 h-6 rounded-full transition-colors relative ${form.es_autoretenedor ? "bg-emerald-500" : "bg-slate-300"}`}>
              <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.es_autoretenedor ? "translate-x-5" : "translate-x-1"}`} />
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 border border-slate-200 text-slate-600 py-2.5 rounded-xl text-sm font-semibold hover:bg-slate-50">
            Cancelar
          </button>
          <button
            onClick={() => onSave(form)}
            disabled={saving || !form.nombre.trim()}
            className="flex-1 bg-[#0F2A5C] text-white py-2.5 rounded-xl text-sm font-semibold hover:bg-[#163A7A] disabled:opacity-50 flex items-center justify-center gap-2"
            data-testid="save-proveedor-btn"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Proveedores() {
  const { api } = useAuth();
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState(null); // null | {mode: 'new'|'edit', data?}
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/proveedores/config");
      setProveedores(res.data.proveedores || []);
    } catch { toast.error("Error cargando proveedores"); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (form) => {
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      await api.post("/proveedores/config", form);
      toast.success(`${form.nombre} guardado correctamente`);
      setModal(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando proveedor");
    } finally { setSaving(false); }
  };

  const handleDelete = async (nombre) => {
    if (!window.confirm(`¿Eliminar ${nombre} de la configuración?`)) return;
    try {
      // Delete by posting with es_autoretenedor=false and empty NIT as a soft-clear,
      // or call a delete endpoint if available. For now, we'll mark as inactive via notes.
      await api.post("/proveedores/config", { nombre, nit: "", es_autoretenedor: false, notas: "ELIMINADO" });
      toast.success(`${nombre} eliminado`);
      load();
    } catch { toast.error("Error eliminando proveedor"); }
  };

  const filtered = proveedores.filter(p =>
    !p.notas?.includes("ELIMINADO") &&
    (search ? p.nombre.toLowerCase().includes(search.toLowerCase()) || (p.nit || "").includes(search) : true)
  );

  const autoretenedores = filtered.filter(p => p.es_autoretenedor);
  const normales = filtered.filter(p => !p.es_autoretenedor);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Proveedores</h2>
          <p className="text-sm text-slate-500 mt-1">
            Configuración de retenciones y autoretenedores · {autoretenedores.length} autoretenedor{autoretenedores.length !== 1 ? "es" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="p-2 rounded-lg border border-slate-200 hover:bg-slate-50 transition text-slate-500">
            <RefreshCw size={15} />
          </button>
          <button
            onClick={() => setModal({ mode: "new" })}
            className="flex items-center gap-2 bg-[#0F2A5C] text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-[#163A7A] transition"
            data-testid="add-proveedor-btn"
          >
            <Plus size={15} /> Agregar Proveedor
          </button>
        </div>
      </div>

      {/* Search */}
      <div>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar por nombre o NIT..."
          className="w-full max-w-sm border rounded-xl px-4 py-2 text-sm focus:border-[#C9A84C] outline-none"
          data-testid="search-proveedores"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-[#0F2A5C]" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Autoretenedores */}
          {autoretenedores.length > 0 && (
            <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3 border-b border-emerald-100 flex items-center gap-2">
                <ShieldCheck size={15} className="text-emerald-600" />
                <span className="text-sm font-bold text-[#0F2A5C]">Autoretenedores</span>
                <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-semibold">
                  NO se aplica ReteFuente
                </span>
              </div>
              <div className="divide-y divide-slate-50">
                {autoretenedores.map((p, i) => (
                  <ProveedorRow key={i} p={p} onEdit={() => setModal({ mode: "edit", data: p })} onDelete={() => handleDelete(p.nombre)} />
                ))}
              </div>
            </div>
          )}

          {/* Normales */}
          {normales.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
                <Building2 size={15} className="text-slate-500" />
                <span className="text-sm font-bold text-[#0F2A5C]">Con Retención Estándar</span>
              </div>
              <div className="divide-y divide-slate-50">
                {normales.map((p, i) => (
                  <ProveedorRow key={i} p={p} onEdit={() => setModal({ mode: "edit", data: p })} onDelete={() => handleDelete(p.nombre)} />
                ))}
              </div>
            </div>
          )}

          {filtered.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              <Building2 size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">No hay proveedores configurados</p>
              <button onClick={() => setModal({ mode: "new" })} className="mt-2 text-xs text-[#0F2A5C] underline">
                Agregar el primero
              </button>
            </div>
          )}
        </div>
      )}

      {modal && (
        <ProveedorModal
          proveedor={modal.mode === "edit" ? modal.data : null}
          onClose={() => setModal(null)}
          onSave={handleSave}
          saving={saving}
        />
      )}
    </div>
  );
}

function ProveedorRow({ p, onEdit, onDelete }) {
  return (
    <div className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition" data-testid="proveedor-row">
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${p.es_autoretenedor ? "bg-emerald-100" : "bg-slate-100"}`}>
          <Building2 size={14} className={p.es_autoretenedor ? "text-emerald-600" : "text-slate-400"} />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#0F2A5C] truncate">{p.nombre}</p>
          <p className="text-[10px] text-slate-400">
            {p.nit ? `NIT ${p.nit}` : "Sin NIT"} · {p.tipo_retencion?.replace(/_/g, " ")}
            {p.notas ? ` · ${p.notas}` : ""}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <Badge active={p.es_autoretenedor} />
        <button onClick={onEdit} className="text-xs text-[#0F2A5C] border border-[#0F2A5C]/30 px-2 py-0.5 rounded-lg hover:bg-[#0F2A5C] hover:text-white transition">
          Editar
        </button>
        <button onClick={onDelete} className="p-1 text-red-400 hover:text-red-600 transition">
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
