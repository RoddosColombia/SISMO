import React, { useState } from "react";
import { Users, Plus, Trash2, Send, Loader2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP, todayStr } from "../utils/formatters";

const SMLMV = 1423500;
const AUX_TRANSPORTE = 200000;

function calcNomina(emp) {
  const salario = parseFloat(emp.salario || 0);
  const diasTrabajados = parseInt(emp.dias || 30);
  const salarioProporcional = Math.round(salario * diasTrabajados / 30);
  const auxTransporte = salario <= 2 * SMLMV ? Math.round(AUX_TRANSPORTE * diasTrabajados / 30) : 0;

  // Deducciones empleado
  const saludEmpleado = Math.round(salarioProporcional * 0.04);
  const pensionEmpleado = Math.round(salarioProporcional * 0.04);
  const fondoSolidaridad = salarioProporcional >= 4 * SMLMV ? Math.round(salarioProporcional * 0.01) : 0;
  const totalDeducciones = saludEmpleado + pensionEmpleado + fondoSolidaridad;
  const neto = salarioProporcional + auxTransporte - totalDeducciones;

  // Aportes empleador
  const saludEmpleador = Math.round(salarioProporcional * 0.085);
  const pensionEmpleador = Math.round(salarioProporcional * 0.12);
  const arl = Math.round(salarioProporcional * 0.00522);
  const cajaCompensacion = Math.round(salarioProporcional * 0.04);
  const icbf = Math.round(salarioProporcional * 0.03);
  const sena = Math.round(salarioProporcional * 0.02);
  const totalEmpleador = saludEmpleador + pensionEmpleador + arl + cajaCompensacion + icbf + sena;
  const costoTotal = salarioProporcional + auxTransporte + totalEmpleador;

  return { salarioProporcional, auxTransporte, saludEmpleado, pensionEmpleado, fondoSolidaridad, totalDeducciones, neto, saludEmpleador, pensionEmpleador, arl, cajaCompensacion, icbf, sena, totalEmpleador, costoTotal };
}

const EMPTY_EMP = { nombre: "", cedula: "", cargo: "", salario: SMLMV, dias: 30 };

export default function Nomina() {
  const { api } = useAuth();
  const [empleados, setEmpleados] = useState([{ ...EMPTY_EMP, id: "1" }]);
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7));
  const [saving, setSaving] = useState(false);

  const addEmp = () => setEmpleados([...empleados, { ...EMPTY_EMP, id: Date.now().toString() }]);
  const removeEmp = (id) => setEmpleados(empleados.filter(e => e.id !== id));
  const updateEmp = (id, field, val) => setEmpleados(empleados.map(e => e.id === id ? { ...e, [field]: val } : e));

  const totals = empleados.map(e => calcNomina(e));
  const grandTotal = totals.reduce((s, t) => ({
    neto: (s.neto || 0) + t.neto,
    costoTotal: (s.costoTotal || 0) + t.costoTotal,
    totalEmpleador: (s.totalEmpleador || 0) + t.totalEmpleador,
  }), {});

  const handleCausar = async () => {
    setSaving(true);
    try {
      const items = [];
      empleados.forEach((emp, i) => {
        const c = totals[i];
        items.push({ account: { id: "5105" }, debit: c.salarioProporcional, credit: 0, description: `Salario ${emp.nombre}` });
        if (c.auxTransporte > 0) items.push({ account: { id: "5106" }, debit: c.auxTransporte, credit: 0, description: `Aux transporte ${emp.nombre}` });
        items.push({ account: { id: "5109" }, debit: c.totalEmpleador, credit: 0, description: `Aportes patronales ${emp.nombre}` });
        items.push({ account: { id: "2370" }, credit: c.neto, debit: 0, description: `Nómina a pagar ${emp.nombre}` });
        items.push({ account: { id: "2350" }, credit: c.saludEmpleado + c.saludEmpleador, debit: 0, description: `Salud ${emp.nombre}` });
        items.push({ account: { id: "2360" }, credit: c.pensionEmpleado + c.pensionEmpleador, debit: 0, description: `Pensión ${emp.nombre}` });
      });
      const payload = {
        date: todayStr(),
        description: `Nómina ${mes} — ${empleados.length} empleado(s)`,
        items,
      };
      await api.post("/alegra/journal-entries", payload);
      toast.success(`Nómina ${mes} causada en Alegra`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error causando nómina");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Liquidación de Nómina</h2>
          <p className="text-sm text-slate-500 mt-1">SMLMV 2025: {formatCOP(SMLMV)} | Aux. Transporte: {formatCOP(AUX_TRANSPORTE)}</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" />
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Empleados</span>
          <div className="text-2xl font-bold text-[#0F2A5C] mt-1">{empleados.length}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Neto a Pagar</span>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{formatCOP(grandTotal.neto || 0)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <span className="text-xs text-slate-500 uppercase">Costo Total Empresa</span>
          <div className="text-2xl font-bold text-[#C9A84C] mt-1">{formatCOP(grandTotal.costoTotal || 0)}</div>
        </div>
      </div>

      {/* Employee table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <span className="text-sm font-semibold text-[#0F2A5C]">Empleados</span>
          <button onClick={addEmp} className="flex items-center gap-1 text-xs bg-[#0F2A5C] text-white px-3 py-1.5 rounded-lg hover:bg-[#163A7A]">
            <Plus size={12} /> Agregar
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-[10px]">
                <th className="px-3 py-2.5 text-left">Nombre</th>
                <th className="px-3 py-2.5 text-left">Cédula</th>
                <th className="px-3 py-2.5 text-left">Cargo</th>
                <th className="px-3 py-2.5 text-right">Salario Base</th>
                <th className="px-3 py-2.5 text-center">Días</th>
                <th className="px-3 py-2.5 text-right">Aux. Transp.</th>
                <th className="px-3 py-2.5 text-right">Deducciones</th>
                <th className="px-3 py-2.5 text-right font-bold">Neto</th>
                <th className="px-3 py-2.5 text-right">Aport. Patr.</th>
                <th className="px-3 py-2.5 text-right font-bold">Costo Total</th>
                <th className="px-3 py-2.5 text-center">Acc.</th>
              </tr>
            </thead>
            <tbody>
              {empleados.map((emp, i) => {
                const c = totals[i];
                return (
                  <tr key={emp.id} className="border-b border-slate-100 hover:bg-[#F0F4FF]/30">
                    <td className="px-3 py-2">
                      <input className="w-32 border rounded px-1.5 py-1 text-xs focus:border-[#C9A84C] outline-none"
                        value={emp.nombre} onChange={(e) => updateEmp(emp.id, "nombre", e.target.value)} placeholder="Nombre completo" />
                    </td>
                    <td className="px-3 py-2">
                      <input className="w-24 border rounded px-1.5 py-1 text-xs focus:border-[#C9A84C] outline-none"
                        value={emp.cedula} onChange={(e) => updateEmp(emp.id, "cedula", e.target.value)} placeholder="Cédula" />
                    </td>
                    <td className="px-3 py-2">
                      <input className="w-24 border rounded px-1.5 py-1 text-xs focus:border-[#C9A84C] outline-none"
                        value={emp.cargo} onChange={(e) => updateEmp(emp.id, "cargo", e.target.value)} placeholder="Cargo" />
                    </td>
                    <td className="px-3 py-2">
                      <input type="number" className="w-28 border rounded px-1.5 py-1 text-xs text-right focus:border-[#C9A84C] outline-none"
                        value={emp.salario} onChange={(e) => updateEmp(emp.id, "salario", e.target.value)} />
                    </td>
                    <td className="px-3 py-2">
                      <input type="number" className="w-12 border rounded px-1.5 py-1 text-xs text-center focus:border-[#C9A84C] outline-none"
                        value={emp.dias} onChange={(e) => updateEmp(emp.id, "dias", e.target.value)} min="1" max="30" />
                    </td>
                    <td className="px-3 py-2 text-right">{formatCOP(c.auxTransporte)}</td>
                    <td className="px-3 py-2 text-right text-red-600">-{formatCOP(c.totalDeducciones)}</td>
                    <td className="px-3 py-2 text-right font-bold text-emerald-600">{formatCOP(c.neto)}</td>
                    <td className="px-3 py-2 text-right">{formatCOP(c.totalEmpleador)}</td>
                    <td className="px-3 py-2 text-right font-bold text-[#C9A84C]">{formatCOP(c.costoTotal)}</td>
                    <td className="px-3 py-2 text-center">
                      {empleados.length > 1 && (
                        <button onClick={() => removeEmp(emp.id)} className="text-red-400 hover:text-red-600"><Trash2 size={13} /></button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleCausar}
          disabled={saving}
          className="flex items-center gap-2 bg-[#0F2A5C] text-white px-6 py-3 rounded-xl font-semibold hover:bg-[#163A7A] transition disabled:opacity-50"
          data-testid="causar-nomina-btn"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          Causar Nómina en Alegra ({mes})
        </button>
      </div>
    </div>
  );
}
