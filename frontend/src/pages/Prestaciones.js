import React, { useState } from "react";
import { Gift, Calculator } from "lucide-react";
import { formatCOP } from "../utils/formatters";

const SMLMV = 1423500;

function calcPrestaciones(salario, diasTrabajados, inicio) {
  const base = parseFloat(salario || 0);
  const dias = parseInt(diasTrabajados || 0);
  const meses = dias / 30;

  // Cesantías: salario/360 * días
  const cesantias = Math.round((base / 360) * dias);
  const interesCesantias = Math.round(cesantias * 0.12 * (dias / 360));

  // Prima de servicios: salario/360 * días (misma fórmula)
  const prima = Math.round((base / 360) * dias);

  // Vacaciones: salario/720 * días trabajados
  const vacaciones = Math.round((base / 720) * dias);

  // Provisión mensual (por 30 días)
  const provCesantias = Math.round(base / 12);
  const provPrima = Math.round(base / 12);
  const provVacaciones = Math.round(base / 24);
  const provIntCesantias = Math.round(provCesantias * 0.12 / 12);
  const provTotal = provCesantias + provPrima + provVacaciones + provIntCesantias;

  return {
    cesantias, interesCesantias, prima, vacaciones,
    total: cesantias + interesCesantias + prima + vacaciones,
    provCesantias, provPrima, provVacaciones, provIntCesantias, provTotal,
  };
}

export default function Prestaciones() {
  const [salario, setSalario] = useState(SMLMV);
  const [dias, setDias] = useState(365);
  const [inicio, setInicio] = useState("");

  const c = calcPrestaciones(salario, dias, inicio);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Prestaciones Sociales</h2>
        <p className="text-sm text-slate-500 mt-1">Calculadora de cesantías, prima, vacaciones e intereses</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-base font-bold text-[#0F2A5C] mb-4 flex items-center gap-2">
            <Calculator size={16} className="text-[#C9A84C]" /> Datos del Empleado
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Salario mensual</label>
              <input type="number" value={salario} onChange={(e) => setSalario(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                data-testid="prestaciones-salario-input" />
              <p className="text-[10px] text-slate-400 mt-1">SMLMV 2025: {formatCOP(SMLMV)}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Días trabajados en el período</label>
              <input type="number" value={dias} onChange={(e) => setDias(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none"
                placeholder="360 = 1 año" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Fecha inicio contrato (opcional)</label>
              <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" />
            </div>
          </div>

          {/* Monthly provision box */}
          <div className="mt-5 bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-xs font-bold text-amber-800 mb-2">Provisión Mensual Recomendada</p>
            <div className="space-y-1 text-xs">
              {[
                ["Cesantías (8.33%)", c.provCesantias],
                ["Interés cesantías (1%)", c.provIntCesantias],
                ["Prima de servicios (8.33%)", c.provPrima],
                ["Vacaciones (4.17%)", c.provVacaciones],
              ].map(([label, val], i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-amber-700">{label}</span>
                  <span className="font-semibold text-amber-900">{formatCOP(val)}</span>
                </div>
              ))}
              <div className="border-t border-amber-300 pt-1 flex justify-between font-bold text-amber-900">
                <span>Total provisión/mes</span>
                <span>{formatCOP(c.provTotal)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-base font-bold text-[#0F2A5C] mb-4 flex items-center gap-2">
            <Gift size={16} className="text-[#C9A84C]" /> Liquidación por {dias} días
          </h3>
          <div className="space-y-3">
            {[
              { label: "Cesantías", formula: "Salario / 360 × días", value: c.cesantias, color: "text-[#0F2A5C]", bg: "bg-[#F0F4FF]" },
              { label: "Interés cesantías (12%)", formula: "Cesantías × 12% × (días/360)", value: c.interesCesantias, color: "text-blue-700", bg: "bg-blue-50" },
              { label: "Prima de servicios", formula: "Salario / 360 × días", value: c.prima, color: "text-purple-700", bg: "bg-purple-50" },
              { label: "Vacaciones", formula: "Salario / 720 × días", value: c.vacaciones, color: "text-emerald-700", bg: "bg-emerald-50" },
            ].map((item, i) => (
              <div key={i} className={`${item.bg} rounded-xl p-4`}>
                <div className="flex justify-between items-start">
                  <div>
                    <p className={`text-sm font-bold ${item.color}`}>{item.label}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{item.formula}</p>
                  </div>
                  <span className={`text-xl font-bold ${item.color}`}>{formatCOP(item.value)}</span>
                </div>
              </div>
            ))}
            <div className="bg-[#0F2A5C] rounded-xl p-4 flex justify-between items-center">
              <span className="text-white font-bold">Total Prestaciones</span>
              <span className="text-[#C9A84C] text-2xl font-bold">{formatCOP(c.total)}</span>
            </div>
          </div>
          <p className="text-[10px] text-slate-400 mt-3">
            * Fórmulas según Código Sustantivo del Trabajo Colombia. No incluye liquidación de contrato.
          </p>
        </div>
      </div>
    </div>
  );
}
