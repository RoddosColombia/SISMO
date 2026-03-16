import React, { useState, useEffect, useCallback } from "react";
import {
  Calendar, AlertTriangle, CheckCircle2, Clock, Settings2,
  Save, Loader2, RefreshCw, TrendingDown, ChevronDown, ChevronUp, Info,
  ArrowRight, FileText
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { formatCOP } from "../utils/formatters";
import { FiltroFecha, loadRange } from "../components/FiltroFecha";

const UVT_2025 = 49799;

const TIPO_COLORS = {
  iva: "bg-blue-100 text-blue-700 border-blue-200",
  retefte: "bg-amber-100 text-amber-700 border-amber-200",
  ica: "bg-purple-100 text-purple-700 border-purple-200",
  renta: "bg-red-100 text-red-700 border-red-200",
  nomina: "bg-green-100 text-green-700 border-green-200",
};

function buildCalendar(tipo, periodos) {
  const ivaEvents = periodos.map((p) => {
    const mesLim = p.fin_mes + (p.mes_limite_offset || 1);
    const MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
      "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
    const mes = mesLim > 12 ? MESES_ES[mesLim - 12] : MESES_ES[mesLim];
    return {
      mes,
      evento: `IVA ${tipo} (${p.nombre})`,
      tipo: "iva",
      fecha: `Hasta el ${p.dia_limite} de ${mes}`,
    };
  });

  const fixed = [
    { mes: "Noviembre", evento: "Declaración Renta personas jurídicas", tipo: "renta", fecha: "Según calendario DIAN" },
    { mes: "Agosto", evento: "Declaración Renta personas naturales", tipo: "renta", fecha: "Según dígito NIT" },
    { mes: "Mensual", evento: "ReteFuente (declaración y pago)", tipo: "retefte", fecha: "Día 20 del mes siguiente" },
    { mes: "Mensual", evento: "ReteICA Bogotá", tipo: "ica", fecha: "Día 20 del mes siguiente" },
    { mes: "Mensual", evento: "Seguridad Social (PILA)", tipo: "nomina", fecha: "Según último dígito NIT" },
  ];

  return [...ivaEvents, ...fixed];
}

function ReteFuenteCard({ status }) {
  if (!status?.retefuente) return null;
  const { acumulada, facturas_con_retencion, nota } = status.retefuente;
  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm p-5" data-testid="retefuente-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
          <FileText size={15} className="text-amber-500" />
          ReteFuente Practicada
        </h3>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
          {status.periodo?.nombre}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-amber-50 rounded-lg p-3">
          <p className="text-[10px] text-slate-500 mb-0.5">Total retenido período</p>
          <p className="text-lg font-bold text-amber-700">{formatCOP(acumulada)}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-[10px] text-slate-500 mb-0.5">Facturas con retención</p>
          <p className="text-lg font-bold text-[#0F2A5C]">{facturas_con_retencion}</p>
        </div>
      </div>
      <p className="text-[10px] text-slate-400">{nota}</p>
      <p className="text-[10px] text-slate-400 mt-1">
        Vence declaración: día 20 del mes siguiente al período
      </p>
    </div>
  );
}

function ReteICACard({ status, onGoProveedores }) {
  if (!status?.retica) return null;
  const { acumulada, proyectada_periodo, tarifa_pct, base_ingresos, nota } = status.retica;
  return (
    <div className="bg-white rounded-xl border border-purple-200 shadow-sm p-5" data-testid="retica-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
          <FileText size={15} className="text-purple-500" />
          ReteICA Bogotá
        </h3>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
          {tarifa_pct}% por operación gravada
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-purple-50 rounded-lg p-3">
          <p className="text-[10px] text-slate-500 mb-0.5">Acumulado al mes {status.meses_transcurridos}</p>
          <p className="text-lg font-bold text-purple-700">{formatCOP(acumulada)}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-[10px] text-slate-500 mb-0.5">Proyección período completo</p>
          <p className="text-lg font-bold text-[#0F2A5C]">{formatCOP(proyectada_periodo)}</p>
        </div>
      </div>
      <div className="text-[10px] text-slate-400 space-y-0.5">
        <p>Base ingresos gravables: {formatCOP(base_ingresos)}</p>
        <p>{nota}</p>
        <p>Vence declaración: día 20 del mes siguiente</p>
      </div>
    </div>
  );
}

function IVAStatusCard({ status, loading, onRefresh }) {
  if (loading) return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex items-center justify-center gap-2 min-h-[180px]">
      <Loader2 size={20} className="animate-spin text-[#0F2A5C]" />
      <span className="text-sm text-slate-500">Calculando desde Alegra...</span>
    </div>
  );

  if (!status) return null;

  const urgente = status.dias_restantes !== null && status.dias_restantes <= 30;
  const pagar = status.iva_pagar_neto;
  const hayFavor = status.saldo_favor_dian > 0;

  return (
    <div className={`rounded-xl border-2 shadow-sm p-5 ${urgente && pagar > 0 ? "bg-red-50 border-red-300" : pagar > 0 ? "bg-white border-[#0F2A5C]" : "bg-emerald-50 border-emerald-300"}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
          <AlertTriangle size={16} className={urgente && pagar > 0 ? "text-red-500" : "text-[#C9A84C]"} />
          Estado IVA — Período Actual
        </h3>
        <div className="flex items-center gap-2">
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${urgente && pagar > 0 ? "bg-red-200 text-red-700" : "bg-blue-100 text-blue-700"}`}>
            {status.periodo?.nombre || "Período actual"}
          </span>
          <button onClick={onRefresh} className="p-1 text-slate-400 hover:text-[#0F2A5C]"><RefreshCw size={13} /></button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>Avance del período: Mes {status.meses_transcurridos} de {status.meses_periodo}</span>
          <span className="font-semibold">{status.pct_avance}%</span>
        </div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-[#C9A84C] rounded-full transition-all" style={{ width: `${status.pct_avance}%` }} />
        </div>
        <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
          <span>{status.date_start}</span>
          <span className={`font-semibold ${urgente && pagar > 0 ? "text-red-600" : "text-slate-500"}`}>
            Vence: {status.fecha_limite} ({status.dias_restantes !== null ? `${status.dias_restantes} días` : "—"})
          </span>
        </div>
      </div>

      {/* Values grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        {[
          { label: "IVA cobrado (ventas)", value: formatCOP(status.iva_cobrado), color: "text-[#0F2A5C]" },
          { label: "IVA descontable (compras)", value: formatCOP(status.iva_descontable), color: "text-emerald-700" },
          { label: "IVA bruto período", value: formatCOP(status.iva_bruto), color: "text-[#0F2A5C]" },
          { label: "Saldo a favor DIAN", value: `- ${formatCOP(status.saldo_favor_dian)}`, color: hayFavor ? "text-emerald-700" : "text-slate-400" },
        ].map((item, i) => (
          <div key={i} className="bg-white/70 rounded-lg px-3 py-2">
            <p className="text-[10px] text-slate-500">{item.label}</p>
            <p className={`text-sm font-bold ${item.color}`}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* Bottom: pagar / saldo favor */}
      <div className={`rounded-lg p-3 flex justify-between items-center ${pagar > 0 ? "bg-red-100" : "bg-emerald-100"}`}>
        <div>
          <p className="text-xs font-semibold text-slate-700">{pagar > 0 ? "IVA a pagar en próxima declaración" : "Saldo a favor restante"}</p>
          <p className="text-[10px] text-slate-500">Acumulado a la fecha + saldo DIAN</p>
        </div>
        <span className={`text-2xl font-bold ${pagar > 0 ? "text-red-700" : "text-emerald-700"}`}>
          {pagar > 0 ? formatCOP(pagar) : `+${formatCOP(status.saldo_favor_restante)}`}
        </span>
      </div>

      {/* Projection */}
      {status.proyeccion && (
        <div className="mt-3 bg-slate-50 rounded-lg p-3">
          <p className="text-[10px] font-semibold text-slate-500 uppercase mb-1.5">Proyección al cierre del período</p>
          <div className="flex justify-between text-xs">
            <span className="text-slate-600">IVA cobrado proyectado</span>
            <span className="font-semibold text-[#0F2A5C]">{formatCOP(status.proyeccion.iva_cobrado)}</span>
          </div>
          <div className="flex justify-between text-xs mt-1">
            <span className="text-slate-600">IVA descontable proyectado</span>
            <span className="font-semibold text-emerald-700">{formatCOP(status.proyeccion.iva_descontable)}</span>
          </div>
          <div className="flex justify-between text-sm font-bold mt-2 pt-2 border-t border-slate-200">
            <span className="text-red-700">IVA proyectado a pagar</span>
            <span className="text-red-700">{formatCOP(status.proyeccion.iva_pagar)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function SugerenciasIVA({ status }) {
  const [open, setOpen] = useState(true);
  if (!status) return null;

  const descontablePct = status.iva_cobrado > 0
    ? Math.round((status.iva_descontable / status.iva_cobrado) * 100)
    : 0;
  const diasRestantes = status.dias_restantes ?? 60;

  const sugerencias = [];

  if (diasRestantes <= 45 && status.iva_pagar_neto > 0) {
    sugerencias.push({
      urgente: true,
      icon: "⚡",
      titulo: "Anticipar compras antes del cierre",
      detalle: `Quedan ${diasRestantes} días para declarar. Registra AHORA facturas de compras gravadas pendientes para aumentar el IVA descontable y reducir el monto a pagar.`,
    });
  }

  if (descontablePct < 40 && status.iva_cobrado > 0) {
    sugerencias.push({
      urgente: true,
      icon: "📑",
      titulo: "Verificar facturas de proveedores sin registrar",
      detalle: `Tu IVA descontable es solo el ${descontablePct}% del IVA cobrado. Es probable que haya facturas de compra con IVA sin registrar en Alegra. Cada factura sin registrar es dinero extra pagando a la DIAN.`,
    });
  }

  if (status.facturas_compra < status.facturas_venta * 0.5) {
    sugerencias.push({
      urgente: false,
      icon: "🏭",
      titulo: "Registrar gastos operacionales con IVA",
      detalle: "Gastos como arrendamiento de bodegas, servicios técnicos, publicidad, seguros y mantenimientos pueden tener IVA descontable. Verifica que estén registrados.",
    });
  }

  sugerencias.push({
    urgente: false,
    icon: "🏗️",
    titulo: "Revisar compras de activos fijos",
    detalle: "Los activos fijos (maquinaria, equipos, vehículos) generan IVA descontable en el período de compra. Si tienes activos adquiridos en el período, asegúrate de registrar el IVA.",
  });

  sugerencias.push({
    urgente: false,
    icon: "📅",
    titulo: "Coordinar pagos a proveedores antes del corte",
    detalle: `Si tienes proveedores a quienes aún no has pagado pero tienes las facturas, asegúrate de registrarlas en Alegra antes del ${status.fecha_limite} para que el IVA sea descontable en este período.`,
  });

  if (status.saldo_favor_dian === 0) {
    sugerencias.push({
      urgente: false,
      icon: "💳",
      titulo: "Registrar saldo a favor DIAN si lo tienes",
      detalle: "Si tienes saldo a favor de períodos anteriores en la DIAN, regístralo en la configuración de esta sección. Se aplicará automáticamente al IVA a pagar calculado.",
    });
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-slate-100 hover:bg-slate-50 transition"
      >
        <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
          <TrendingDown size={15} className="text-[#C9A84C]" />
          Sugerencias para Reducir IVA
          {sugerencias.filter(s => s.urgente).length > 0 && (
            <span className="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {sugerencias.filter(s => s.urgente).length} urgentes
            </span>
          )}
        </span>
        {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>
      {open && (
        <div className="p-4 space-y-2.5">
          {sugerencias.map((s, i) => (
            <div key={i} className={`rounded-lg p-3 border ${s.urgente ? "bg-red-50 border-red-200" : "bg-slate-50 border-slate-100"}`}>
              <div className="flex items-start gap-2">
                <span className="text-base leading-none mt-0.5">{s.icon}</span>
                <div>
                  <p className={`text-xs font-bold mb-0.5 ${s.urgente ? "text-red-700" : "text-[#0F2A5C]"}`}>
                    {s.urgente && "⚠️ URGENTE — "}{s.titulo}
                  </p>
                  <p className="text-xs text-slate-600 leading-relaxed">{s.detalle}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConfigPanel({ config, presets, onSave, saving }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(config);

  useEffect(() => { setForm(config); }, [config]);

  const applyPreset = (tipo) => {
    const ps = presets[tipo] || [];
    setForm(f => ({ ...f, tipo_periodo: tipo, periodos: ps }));
  };

  const updatePeriodo = (i, field, val) => {
    const updated = form.periodos.map((p, idx) =>
      idx === i ? { ...p, [field]: field.includes("mes") || field.includes("dia") ? parseInt(val) : val } : p
    );
    setForm(f => ({ ...f, periodos: updated }));
  };

  const addPeriodo = () => {
    setForm(f => ({
      ...f,
      tipo_periodo: "personalizado",
      periodos: [...f.periodos, { nombre: "Nuevo", inicio_mes: 1, fin_mes: 2, dia_limite: 30, mes_limite_offset: 1 }],
    }));
  };

  const removePeriodo = (i) => {
    setForm(f => ({ ...f, periodos: f.periodos.filter((_, idx) => idx !== i) }));
  };

  const MESES_CORTOS = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-slate-100 hover:bg-slate-50 transition"
      >
        <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
          <Settings2 size={15} className="text-[#C9A84C]" /> Configuración IVA RODDOS
          <span className="text-[11px] font-normal text-slate-500 ml-1">({config.tipo_periodo})</span>
        </span>
        {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>

      {open && (
        <div className="p-5 space-y-5">
          {/* Preset selector */}
          <div>
            <label className="text-xs font-medium text-slate-700 mb-2 block">Periodicidad de declaración IVA</label>
            <div className="flex gap-2 flex-wrap">
              {["bimestral", "cuatrimestral", "anual"].map((t) => (
                <button
                  key={t}
                  onClick={() => applyPreset(t)}
                  className={`text-xs px-4 py-2 rounded-lg border transition capitalize font-medium ${form.tipo_periodo === t ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "bg-white text-slate-600 border-slate-200 hover:border-[#0F2A5C]"}`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Periods table */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-slate-700">Períodos y fechas límite</label>
              <button onClick={addPeriodo} className="text-[10px] text-[#0F2A5C] border border-[#0F2A5C] px-2 py-0.5 rounded hover:bg-[#0F2A5C] hover:text-white transition">
                + Agregar período
              </button>
            </div>
            <div className="space-y-2">
              {form.periodos.map((p, i) => (
                <div key={i} className="grid grid-cols-6 gap-2 items-center bg-slate-50 rounded-lg p-2">
                  <input
                    className="col-span-1 border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none"
                    value={p.nombre} onChange={(e) => updatePeriodo(i, "nombre", e.target.value)}
                    placeholder="Nombre"
                  />
                  <div className="col-span-1 flex items-center gap-1">
                    <select className="border rounded px-1 py-1 text-xs focus:border-[#C9A84C] outline-none flex-1"
                      value={p.inicio_mes} onChange={(e) => updatePeriodo(i, "inicio_mes", e.target.value)}>
                      {MESES_CORTOS.slice(1).map((m, idx) => <option key={idx + 1} value={idx + 1}>{m}</option>)}
                    </select>
                    <span className="text-slate-400 text-xs">–</span>
                    <select className="border rounded px-1 py-1 text-xs focus:border-[#C9A84C] outline-none flex-1"
                      value={p.fin_mes} onChange={(e) => updatePeriodo(i, "fin_mes", e.target.value)}>
                      {MESES_CORTOS.slice(1).map((m, idx) => <option key={idx + 1} value={idx + 1}>{m}</option>)}
                    </select>
                  </div>
                  <div className="col-span-2 flex items-center gap-1">
                    <span className="text-[10px] text-slate-400">Vence día</span>
                    <input type="number" className="w-12 border rounded px-1 py-1 text-xs text-center focus:border-[#C9A84C] outline-none"
                      value={p.dia_limite} onChange={(e) => updatePeriodo(i, "dia_limite", e.target.value)} min="1" max="31" />
                    <span className="text-[10px] text-slate-400">mes sig. +</span>
                    <input type="number" className="w-10 border rounded px-1 py-1 text-xs text-center focus:border-[#C9A84C] outline-none"
                      value={p.mes_limite_offset} onChange={(e) => updatePeriodo(i, "mes_limite_offset", e.target.value)} min="0" max="3" />
                  </div>
                  <div className="col-span-2 flex justify-end">
                    {form.periodos.length > 1 && (
                      <button onClick={() => removePeriodo(i)} className="text-[10px] text-red-400 hover:text-red-600 px-2 py-0.5">
                        Eliminar
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Saldo a favor */}
          <div className="bg-[#F0F4FF] rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-[#0F2A5C] flex items-center gap-1.5">
              <Info size={13} className="text-[#C9A84C]" /> Saldo a Favor DIAN
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Valor saldo a favor ($)</label>
                <input
                  type="number"
                  value={form.saldo_favor_dian}
                  onChange={(e) => setForm(f => ({ ...f, saldo_favor_dian: parseFloat(e.target.value) || 0 }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                  placeholder="0"
                  data-testid="saldo-favor-input"
                />
                <p className="text-[10px] text-slate-400 mt-0.5">Se aplica automáticamente al IVA a pagar</p>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Fecha del saldo a favor</label>
                <input
                  type="date"
                  value={form.fecha_saldo_favor || ""}
                  onChange={(e) => setForm(f => ({ ...f, fecha_saldo_favor: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Notas (opcional)</label>
              <input
                value={form.nota_saldo_favor || ""}
                onChange={(e) => setForm(f => ({ ...f, nota_saldo_favor: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                placeholder="Ej: Saldo según declaración IVA Sep-Dic 2024"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => onSave(form)}
              disabled={saving}
              className="flex items-center gap-2 bg-[#0F2A5C] text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[#163A7A] disabled:opacity-50"
              data-testid="save-iva-config-btn"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Guardar Configuración
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Impuestos() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [presets, setPresets] = useState({});
  const [status, setStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filterTipo, setFilterTipo] = useState("");
  const [filtroFecha, setFiltroFecha] = useState(() => loadRange("impuestos"));

  const loadAll = useCallback(async () => {
    try {
      const [cfgRes, presetsRes] = await Promise.all([
        api.get("/impuestos/config"),
        api.get("/impuestos/periodos-preset"),
      ]);
      setConfig(cfgRes.data);
      setPresets(presetsRes.data);
    } catch {
      toast.error("Error cargando configuración");
    }
  }, [api]);

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const res = await api.get("/impuestos/iva-status");
      setStatus(res.data);
    } catch {
      toast.error("Error calculando estado IVA");
    } finally {
      setLoadingStatus(false);
    }
  }, [api]);

  useEffect(() => { loadAll(); loadStatus(); }, [loadAll, loadStatus]);

  const handleSaveConfig = async (form) => {
    setSaving(true);
    try {
      await api.post("/impuestos/config", form);
      setConfig(form);
      toast.success("Configuración IVA guardada");
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando configuración");
    } finally {
      setSaving(false);
    }
  };

  const calendar = config ? buildCalendar(config.tipo_periodo, config.periodos) : [];
  const filtered = filterTipo ? calendar.filter((c) => c.tipo === filterTipo) : calendar;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Impuestos y Alertas</h2>
            <p className="text-sm text-slate-500 mt-1">
              Calendario fiscal Colombia 2025 — UVT ${UVT_2025.toLocaleString("es-CO")} | IVA cuatrimestral configurable
            </p>
          </div>
          <div className="flex items-center gap-2">
            <FiltroFecha moduleKey="impuestos" onChange={setFiltroFecha} compact />
            <button
              onClick={() => navigate("/proveedores")}
              className="flex items-center gap-1.5 text-xs border border-[#0F2A5C]/30 text-[#0F2A5C] px-3 py-1.5 rounded-lg hover:bg-[#0F2A5C] hover:text-white transition"
              data-testid="go-proveedores-btn"
            >
              <ArrowRight size={12} /> Gestionar Proveedores
            </button>
          </div>
        </div>
      </div>

      {/* Configuration panel */}
      {config && (
        <ConfigPanel config={config} presets={presets} onSave={handleSaveConfig} saving={saving} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column: IVA Status + Suggestions + ReteFuente + ReteICA */}
        <div className="space-y-4">
          <IVAStatusCard status={status} loading={loadingStatus} onRefresh={loadStatus} />
          {status && <SugerenciasIVA status={status} />}
          {status && <ReteFuenteCard status={status} />}
          {status && <ReteICACard status={status} onGoProveedores={() => navigate("/proveedores")} />}
        </div>

        {/* Right column: Calendar + Rates */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
                <Calendar size={16} className="text-[#C9A84C]" /> Calendario Fiscal 2025
              </h3>
              <div className="flex gap-1 flex-wrap">
                {["", "iva", "retefte", "ica", "renta", "nomina"].map((t) => (
                  <button key={t} onClick={() => setFilterTipo(t)}
                    className={`text-[10px] px-2 py-0.5 rounded-full border transition ${filterTipo === t ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "border-slate-200 text-slate-600 hover:border-[#0F2A5C]"}`}>
                    {t || "Todo"}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {filtered.map((item, i) => (
                <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <Clock size={14} className="text-[#C9A84C] mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-[#0F2A5C]">{item.mes}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${TIPO_COLORS[item.tipo] || "bg-slate-100 text-slate-600 border-slate-200"}`}>
                        {item.tipo.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5">{item.evento}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{item.fecha}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Key rates */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="text-base font-bold text-[#0F2A5C] mb-3 flex items-center gap-2">
              <AlertTriangle size={16} className="text-[#C9A84C]" />
              Tarifas Vigentes Colombia 2025
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                ["IVA General", "19%"], ["IVA Bienes básicos", "5%"],
                ["ReteFuente Servicios", "4%"], ["ReteFuente Honorarios PN", "10%"],
                ["ReteFuente Compras", "2.5%"], ["ReteIVA", "15% del IVA"],
                ["ReteICA Servicios Bogotá", "0.966‰"], ["ReteICA Comercio Bogotá", "0.345‰"],
                ["SMLMV 2025", formatCOP(1423500)], ["Auxilio Transporte", formatCOP(200000)],
                ["IPOC motos 125cc", "8%"], ["IPOC motos >125cc", "16%"],
                [`UVT 2025`, formatCOP(UVT_2025)], ["Base mínima compras", "27 UVT"],
              ].map(([label, val], i) => (
                <div key={i} className={`flex justify-between px-2.5 py-1.5 rounded ${i % 2 === 0 ? "bg-[#F0F4FF]" : "bg-slate-50"}`}>
                  <span className="text-slate-600">{label}</span>
                  <span className="font-bold text-[#0F2A5C]">{val}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
