import React, { useState, useEffect, useCallback } from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { RefreshCw, Loader2, Tag } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP } from "../utils/formatters";

const FIXED_KEYWORDS = ["arrendamiento", "nomina", "salario", "seguro", "servicios publicos", "internet", "telefono", "administracion"];
const COLORS = ["#0F2A5C", "#C9A84C", "#3B82F6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

function classifyBill(bill) {
  const desc = (bill.description || bill.vendor?.name || "").toLowerCase();
  const isFixed = FIXED_KEYWORDS.some(k => desc.includes(k));
  return isFixed ? "Fijo" : "Variable";
}

export default function EgresosClasificados() {
  const { api } = useAuth();
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState({ start: new Date().getFullYear() + "-01-01", end: new Date().toISOString().split("T")[0] });
  const [view, setView] = useState("todos");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/alegra/bills", { params: { date_start: period.start, date_end: period.end } });
      setBills(Array.isArray(res.data) ? res.data : []);
    } catch { toast.error("Error cargando egresos"); }
    finally { setLoading(false); }
  }, [api, period]);

  useEffect(() => { loadData(); }, [loadData]);

  const classified = bills.map(b => ({ ...b, tipo: classifyBill(b) }));
  const fijos = classified.filter(b => b.tipo === "Fijo");
  const variables = classified.filter(b => b.tipo === "Variable");
  const totalFijo = fijos.reduce((s, b) => s + parseFloat(b.total || 0), 0);
  const totalVariable = variables.reduce((s, b) => s + parseFloat(b.total || 0), 0);
  const totalAll = totalFijo + totalVariable;

  const pieData = [
    { name: "Fijos", value: totalFijo },
    { name: "Variables", value: totalVariable },
  ];

  // Group by vendor
  const byVendor = {};
  classified.forEach(b => {
    const name = b.vendor?.name || "Sin proveedor";
    if (!byVendor[name]) byVendor[name] = { name, total: 0, tipo: b.tipo, count: 0 };
    byVendor[name].total += parseFloat(b.total || 0);
    byVendor[name].count++;
  });
  const vendorList = Object.values(byVendor).sort((a, b) => b.total - a.total);

  const displayed = view === "fijos" ? fijos : view === "variables" ? variables : classified;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Egresos Clasificados</h2>
          <p className="text-sm text-slate-500 mt-1">Análisis de gastos fijos y variables</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })}
            className="border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" />
          <span className="text-slate-400 text-sm">a</span>
          <input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })}
            className="border rounded-lg px-3 py-2 text-sm focus:border-[#C9A84C] outline-none" />
          <button onClick={loadData} disabled={loading}
            className="flex items-center gap-1.5 text-xs bg-[#0F2A5C] text-white px-3 py-2 rounded-lg hover:bg-[#163A7A]">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Egresos", value: formatCOP(totalAll), color: "text-[#0F2A5C]" },
          { label: "Gastos Fijos", value: formatCOP(totalFijo), sub: `${totalAll > 0 ? ((totalFijo / totalAll) * 100).toFixed(1) : 0}%`, color: "text-blue-700" },
          { label: "Gastos Variables", value: formatCOP(totalVariable), sub: `${totalAll > 0 ? ((totalVariable / totalAll) * 100).toFixed(1) : 0}%`, color: "text-amber-700" },
        ].map((k, i) => (
          <div key={i} className="bg-white rounded-xl border p-4 shadow-sm">
            <span className="text-xs text-slate-500 uppercase">{k.label}</span>
            <div className={`text-2xl font-bold mt-1 ${k.color}`}>{k.value}</div>
            {k.sub && <span className="text-xs text-slate-400">{k.sub} del total</span>}
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-[#0F2A5C]" /></div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Pie chart */}
          {totalAll > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="text-sm font-bold text-[#0F2A5C] mb-3">Distribución Fijo vs Variable</h3>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`} labelLine={false}>
                    {pieData.map((entry, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => formatCOP(v)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Top vendors */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="text-sm font-bold text-[#0F2A5C] mb-3">Top Proveedores</h3>
            <div className="space-y-2">
              {vendorList.slice(0, 8).map((v, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-700 truncate">{v.name}</span>
                      <span className="font-bold text-[#0F2A5C] ml-2 flex-shrink-0">{formatCOP(v.total)}</span>
                    </div>
                    <div className="mt-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${totalAll > 0 ? (v.total / totalAll) * 100 : 0}%`, background: COLORS[i % COLORS.length] }} />
                    </div>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 ${v.tipo === "Fijo" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{v.tipo}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Detail table */}
      {!loading && displayed.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
            <span className="text-sm font-semibold text-[#0F2A5C]">Detalle por Factura</span>
            <div className="flex gap-1 ml-auto">
              {["todos", "fijos", "variables"].map((v) => (
                <button key={v} onClick={() => setView(v)}
                  className={`text-xs px-3 py-1 rounded-full border transition capitalize ${view === v ? "bg-[#0F2A5C] text-white border-[#0F2A5C]" : "border-slate-200 text-slate-600 hover:border-[#0F2A5C]"}`}>
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="bg-[#0F2A5C] text-white text-[10px] uppercase">
                <th className="px-3 py-2.5 text-left">Factura</th>
                <th className="px-3 py-2.5 text-left">Proveedor</th>
                <th className="px-3 py-2.5 text-left">Fecha</th>
                <th className="px-3 py-2.5 text-right">Total</th>
                <th className="px-3 py-2.5 text-center">Tipo</th>
              </tr></thead>
              <tbody>
                {displayed.map((b, i) => (
                  <tr key={b.id} className={`border-b border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/40"}`}>
                    <td className="px-3 py-2 font-mono">{b.numberTemplate?.fullNumber || b.number || b.id}</td>
                    <td className="px-3 py-2">{b.vendor?.name || "—"}</td>
                    <td className="px-3 py-2">{b.date}</td>
                    <td className="px-3 py-2 text-right font-medium">{formatCOP(b.total)}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${b.tipo === "Fijo" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{b.tipo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
