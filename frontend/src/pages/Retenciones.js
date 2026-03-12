import React, { useState } from "react";
import { Calculator, Info } from "lucide-react";
import { formatCOP } from "../utils/formatters";

const UVT = 49799;

const TABLA_RETEFTE = [
  { concepto: "Servicios generales", tarifa: 4, base_uvt: 4, base_cop: 4 * 49799 },
  { concepto: "Servicios técnicos / especializados", tarifa: 6, base_uvt: 4, base_cop: 4 * 49799 },
  { concepto: "Honorarios personas naturales", tarifa: 10, base_uvt: 0, base_cop: 0 },
  { concepto: "Honorarios personas jurídicas", tarifa: 11, base_uvt: 0, base_cop: 0 },
  { concepto: "Arrendamiento inmuebles", tarifa: 3.5, base_uvt: 0, base_cop: 0 },
  { concepto: "Arrendamiento muebles", tarifa: 4, base_uvt: 0, base_cop: 0 },
  { concepto: "Compras generales", tarifa: 2.5, base_uvt: 27, base_cop: 27 * 49799 },
  { concepto: "Transporte de carga", tarifa: 3.5, base_uvt: 4, base_cop: 4 * 49799 },
  { concepto: "Transporte internacional", tarifa: 3.5, base_uvt: 0, base_cop: 0 },
  { concepto: "Loterías y rifas", tarifa: 20, base_uvt: 48, base_cop: 48 * 49799 },
  { concepto: "Comisiones", tarifa: 11, base_uvt: 0, base_cop: 0 },
  { concepto: "Intereses", tarifa: 7, base_uvt: 0, base_cop: 0 },
];

const TABLA_ICA = [
  { actividad: "Servicios", bogota: 0.966, medellin: 0.9, cali: 1.0 },
  { actividad: "Industria", bogota: 0.414, medellin: 0.4, cali: 0.5 },
  { actividad: "Comercio", bogota: 0.345, medellin: 0.35, cali: 0.4 },
  { actividad: "Transporte", bogota: 0.55, medellin: 0.55, cali: 0.7 },
];

export default function Retenciones() {
  const [base, setBase] = useState("");
  const [tipoRete, setTipoRete] = useState(TABLA_RETEFTE[0]);
  const [tipoICA, setTipoICA] = useState(TABLA_ICA[0]);
  const [ciudad, setCiudad] = useState("bogota");

  const baseNum = parseFloat(base || 0);
  const tarifaICA = tipoICA[ciudad] || 0;

  const reteFuente = baseNum >= tipoRete.base_cop ? Math.round(baseNum * (tipoRete.tarifa / 100)) : 0;
  const reteIVA = Math.round(baseNum * 0.19 * 0.15);
  const reteICA = Math.round(baseNum * (tarifaICA / 1000));
  const totalRetenciones = reteFuente + reteIVA + reteICA;
  const neto = baseNum - totalRetenciones;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Calculadora de Retenciones</h2>
        <p className="text-sm text-slate-500 mt-1">Tarifas DIAN vigentes Colombia 2025 — UVT: {formatCOP(UVT)}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Calculator */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-base font-bold text-[#0F2A5C] mb-4 flex items-center gap-2">
            <Calculator size={16} className="text-[#C9A84C]" /> Calculadora Rápida
          </h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Valor base del pago *</label>
              <input
                type="number"
                value={base}
                onChange={(e) => setBase(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                placeholder="0"
                data-testid="retencion-base-input"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Tipo de transacción (ReteFuente)</label>
              <select
                value={tipoRete.concepto}
                onChange={(e) => setTipoRete(TABLA_RETEFTE.find(r => r.concepto === e.target.value))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                data-testid="tipo-retencion-select"
              >
                {TABLA_RETEFTE.map((r) => <option key={r.concepto} value={r.concepto}>{r.concepto} ({r.tarifa}%)</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Actividad ICA</label>
                <select
                  value={tipoICA.actividad}
                  onChange={(e) => setTipoICA(TABLA_ICA.find(r => r.actividad === e.target.value))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                >
                  {TABLA_ICA.map((r) => <option key={r.actividad} value={r.actividad}>{r.actividad}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1 block">Ciudad</label>
                <select
                  value={ciudad}
                  onChange={(e) => setCiudad(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                >
                  <option value="bogota">Bogotá</option>
                  <option value="medellin">Medellín</option>
                  <option value="cali">Cali</option>
                </select>
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="bg-[#F0F4FF] rounded-xl p-4 mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Valor bruto</span>
              <span className="font-semibold text-[#0F2A5C]">{formatCOP(baseNum)}</span>
            </div>
            <div className="border-t border-[#C7D7FF] pt-2 space-y-1.5">
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">
                  ReteFuente ({tipoRete.tarifa}%)
                  {tipoRete.base_cop > 0 && baseNum < tipoRete.base_cop && (
                    <span className="text-[10px] text-amber-600 ml-1">(no aplica, base &lt; {Math.round(tipoRete.base_uvt)} UVT)</span>
                  )}
                </span>
                <span className={`font-semibold ${reteFuente > 0 ? "text-red-600" : "text-slate-400"}`}>{formatCOP(reteFuente)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">ReteIVA (15% del IVA 19%)</span>
                <span className={`font-semibold ${reteIVA > 0 ? "text-red-600" : "text-slate-400"}`}>{formatCOP(reteIVA)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">ReteICA ({tarifaICA}‰ {ciudad})</span>
                <span className={`font-semibold ${reteICA > 0 ? "text-red-600" : "text-slate-400"}`}>{formatCOP(reteICA)}</span>
              </div>
            </div>
            <div className="border-t border-[#C7D7FF] pt-2 flex justify-between text-sm font-bold">
              <span className="text-red-600">Total retenciones</span>
              <span className="text-red-600">{formatCOP(totalRetenciones)}</span>
            </div>
            <div className="flex justify-between text-sm font-bold">
              <span className="text-[#0F2A5C]">Neto a pagar</span>
              <span className="text-[#0F2A5C]">{formatCOP(neto)}</span>
            </div>
          </div>
        </div>

        {/* Tabla Retefte */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-base font-bold text-[#0F2A5C] mb-4 flex items-center gap-2">
            <Info size={16} className="text-[#C9A84C]" /> Tabla ReteFuente 2025
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-[#0F2A5C] text-white">
                  <th className="px-3 py-2 text-left">Concepto</th>
                  <th className="px-3 py-2 text-center">Tarifa</th>
                  <th className="px-3 py-2 text-right">Base mínima</th>
                </tr>
              </thead>
              <tbody>
                {TABLA_RETEFTE.map((r, i) => (
                  <tr key={i} className={`border-b border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50"} ${tipoRete.concepto === r.concepto ? "bg-[#F0F4FF] font-semibold" : ""}`}>
                    <td className="px-3 py-2">{r.concepto}</td>
                    <td className="px-3 py-2 text-center font-bold text-[#0F2A5C]">{r.tarifa}%</td>
                    <td className="px-3 py-2 text-right">{r.base_uvt > 0 ? `${r.base_uvt} UVT (${formatCOP(r.base_cop)})` : "Cualquier valor"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="text-base font-bold text-[#0F2A5C] mt-5 mb-3">Tabla ReteICA (por mil ‰)</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[#0F2A5C] text-white">
                <th className="px-3 py-2 text-left">Actividad</th>
                <th className="px-3 py-2 text-center">Bogotá</th>
                <th className="px-3 py-2 text-center">Medellín</th>
                <th className="px-3 py-2 text-center">Cali</th>
              </tr>
            </thead>
            <tbody>
              {TABLA_ICA.map((r, i) => (
                <tr key={i} className={`border-b border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                  <td className="px-3 py-2 font-medium">{r.actividad}</td>
                  <td className="px-3 py-2 text-center">{r.bogota}‰</td>
                  <td className="px-3 py-2 text-center">{r.medellin}‰</td>
                  <td className="px-3 py-2 text-center">{r.cali}‰</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
