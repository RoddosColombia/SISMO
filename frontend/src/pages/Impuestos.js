import React, { useState } from "react";
import { Calendar, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { formatCOP } from "../utils/formatters";

const UVT_2025 = 49799;

const CALENDAR = [
  { mes: "Enero", evento: "Declaración Renta personas naturales (últimos dígitos)", tipo: "renta", fecha: "Hasta agosto según dígito" },
  { mes: "Febrero", evento: "IVA bimestral (Nov–Dic)", tipo: "iva", fecha: "Hasta 10 feb" },
  { mes: "Abril", evento: "IVA bimestral (Ene–Feb)", tipo: "iva", fecha: "Hasta 10 abr" },
  { mes: "Junio", evento: "IVA bimestral (Mar–Abr)", tipo: "iva", fecha: "Hasta 10 jun" },
  { mes: "Julio", evento: "ReteFuente mes anterior", tipo: "retefte", fecha: "Hasta día 20" },
  { mes: "Agosto", evento: "IVA bimestral (May–Jun)", tipo: "iva", fecha: "Hasta 10 ago" },
  { mes: "Octubre", evento: "IVA bimestral (Jul–Ago)", tipo: "iva", fecha: "Hasta 10 oct" },
  { mes: "Noviembre", evento: "Declaración Renta personas jurídicas", tipo: "renta", fecha: "Según calendario DIAN" },
  { mes: "Diciembre", evento: "IVA bimestral (Sep–Oct)", tipo: "iva", fecha: "Hasta 10 dic" },
  { mes: "Mensual", evento: "ReteFuente (declaración y pago)", tipo: "retefte", fecha: "Día 20 del mes siguiente" },
  { mes: "Mensual", evento: "ReteICA Bogotá", tipo: "ica", fecha: "Día 20 del mes siguiente" },
  { mes: "Mensual", evento: "Seguridad Social empleados (PILA)", tipo: "nomina", fecha: "Según último dígito NIT" },
];

const TIPO_COLORS = {
  iva: "bg-blue-100 text-blue-700 border-blue-200",
  retefte: "bg-amber-100 text-amber-700 border-amber-200",
  ica: "bg-purple-100 text-purple-700 border-purple-200",
  renta: "bg-red-100 text-red-700 border-red-200",
  nomina: "bg-green-100 text-green-700 border-green-200",
};

function IVACalculator() {
  const [ventas, setVentas] = useState("");
  const [compras, setCompras] = useState("");
  const ivaCobrado = parseFloat(ventas || 0) * 0.19;
  const ivaDescontable = parseFloat(compras || 0) * 0.19;
  const ivaPagar = Math.max(0, ivaCobrado - ivaDescontable);
  const ivaSaldoFavor = Math.max(0, ivaDescontable - ivaCobrado);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <h3 className="text-base font-bold text-[#0F2A5C] mb-4 flex items-center gap-2">
        <CheckCircle2 size={16} className="text-[#C9A84C]" />
        Calculadora IVA del Período
      </h3>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1 block">Base ventas gravadas (19%)</label>
          <input
            type="number"
            value={ventas}
            onChange={(e) => setVentas(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
            placeholder="0"
            data-testid="iva-ventas-input"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1 block">Base compras gravadas (19%)</label>
          <input
            type="number"
            value={compras}
            onChange={(e) => setCompras(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
            placeholder="0"
            data-testid="iva-compras-input"
          />
        </div>
      </div>
      <div className="bg-[#F0F4FF] rounded-xl p-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">IVA cobrado (ventas)</span>
          <span className="font-semibold text-[#0F2A5C]">{formatCOP(ivaCobrado)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">IVA descontable (compras)</span>
          <span className="font-semibold text-[#0F2A5C]">{formatCOP(ivaDescontable)}</span>
        </div>
        <div className="border-t border-[#C7D7FF] pt-2 mt-2">
          {ivaPagar > 0 ? (
            <div className="flex justify-between text-sm font-bold">
              <span className="text-red-600">IVA a PAGAR</span>
              <span className="text-red-600">{formatCOP(ivaPagar)}</span>
            </div>
          ) : (
            <div className="flex justify-between text-sm font-bold">
              <span className="text-emerald-600">Saldo a favor</span>
              <span className="text-emerald-600">{formatCOP(ivaSaldoFavor)}</span>
            </div>
          )}
        </div>
      </div>
      <p className="text-[10px] text-slate-400 mt-2">* UVT 2025: {formatCOP(UVT_2025)}</p>
    </div>
  );
}

export default function Impuestos() {
  const [filterTipo, setFilterTipo] = useState("");

  const filtered = filterTipo ? CALENDAR.filter(c => c.tipo === filterTipo) : CALENDAR;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Impuestos y Alertas</h2>
        <p className="text-sm text-slate-500 mt-1">Calendario fiscal Colombia 2025 — UVT ${UVT_2025.toLocaleString("es-CO")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Calendar */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
              <Calendar size={16} className="text-[#C9A84C]" /> Calendario Fiscal 2025
            </h3>
            <div className="flex gap-1">
              {["", "iva", "retefte", "ica", "renta", "nomina"].map((t) => (
                <button key={t} onClick={() => setFilterTipo(t)}
                  className={`text-[10px] px-2 py-0.5 rounded-full border transition ${filterTipo === t ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "border-slate-200 text-slate-600 hover:border-[#0F2A5C]"}`}>
                  {t || "Todo"}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            {filtered.map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <Clock size={14} className="text-[#C9A84C] mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-[#0F2A5C]">{item.mes}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${TIPO_COLORS[item.tipo]}`}>{item.tipo.toUpperCase()}</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">{item.evento}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">{item.fecha}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* IVA Calculator */}
        <div className="space-y-4">
          <IVACalculator />

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
