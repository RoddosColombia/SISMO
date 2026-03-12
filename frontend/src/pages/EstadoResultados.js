import React, { useState, useEffect, useCallback } from "react";
import { BarChart2, TrendingUp, TrendingDown, RefreshCw, Loader2 } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from "recharts";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { formatCOP, formatDate } from "../utils/formatters";

export default function EstadoResultados() {
  const { api } = useAuth();
  const [invoices, setInvoices] = useState([]);
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState({ start: new Date().getFullYear() + "-01-01", end: new Date().toISOString().split("T")[0] });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [invRes, billsRes] = await Promise.all([
        api.get("/alegra/invoices", { params: { date_start: period.start, date_end: period.end } }),
        api.get("/alegra/bills", { params: { date_start: period.start, date_end: period.end } }),
      ]);
      setInvoices(Array.isArray(invRes.data) ? invRes.data : []);
      setBills(Array.isArray(billsRes.data) ? billsRes.data : []);
    } catch {
      toast.error("Error cargando datos");
    } finally {
      setLoading(false);
    }
  }, [api, period]);

  useEffect(() => { loadData(); }, [loadData]);

  // Aggregate by month
  const monthlyData = {};
  invoices.forEach(inv => {
    if (!inv.date) return;
    const month = inv.date.slice(0, 7);
    if (!monthlyData[month]) monthlyData[month] = { month, ingresos: 0, egresos: 0 };
    monthlyData[month].ingresos += parseFloat(inv.total || 0);
  });
  bills.forEach(bill => {
    if (!bill.date) return;
    const month = bill.date.slice(0, 7);
    if (!monthlyData[month]) monthlyData[month] = { month, ingresos: 0, egresos: 0 };
    monthlyData[month].egresos += parseFloat(bill.total || 0);
  });
  const chartData = Object.values(monthlyData).sort((a, b) => a.month.localeCompare(b.month));

  const totalIngresos = invoices.reduce((s, i) => s + parseFloat(i.total || 0), 0);
  const totalEgresos = bills.reduce((s, b) => s + parseFloat(b.total || 0), 0);
  const utilidadBruta = totalIngresos - totalEgresos;
  const margen = totalIngresos > 0 ? ((utilidadBruta / totalIngresos) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Estado de Resultados</h2>
          <p className="text-sm text-slate-500 mt-1">Ingresos vs egresos del período seleccionado</p>
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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Ingresos Totales", value: formatCOP(totalIngresos), color: "text-emerald-600", icon: TrendingUp },
          { label: "Egresos Totales", value: formatCOP(totalEgresos), color: "text-red-600", icon: TrendingDown },
          { label: "Utilidad Bruta", value: formatCOP(utilidadBruta), color: utilidadBruta >= 0 ? "text-[#0F2A5C]" : "text-red-600", icon: BarChart2 },
          { label: "Margen Bruto", value: `${margen}%`, color: parseFloat(margen) >= 0 ? "text-[#C9A84C]" : "text-red-600", icon: BarChart2 },
        ].map((kpi, i) => (
          <div key={i} className="bg-white rounded-xl border p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1">
              <kpi.icon size={14} className={kpi.color} />
              <span className="text-xs text-slate-500 uppercase tracking-wide">{kpi.label}</span>
            </div>
            <div className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-[#0F2A5C]" /></div>
      ) : (
        <>
          {/* Chart */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="text-sm font-bold text-[#0F2A5C] mb-4">Ingresos vs Egresos por Mes</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000000).toFixed(1)}M`} />
                  <Tooltip formatter={(v) => formatCOP(v)} />
                  <Legend />
                  <Bar dataKey="ingresos" name="Ingresos" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="egresos" name="Egresos" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Detalle */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Ingresos */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 bg-emerald-50 border-b border-emerald-100 flex items-center gap-2">
                <TrendingUp size={14} className="text-emerald-600" />
                <span className="text-sm font-bold text-emerald-700">Ingresos ({invoices.length} facturas)</span>
              </div>
              <div className="overflow-y-auto max-h-60">
                <table className="w-full text-xs">
                  <thead><tr className="bg-slate-50"><th className="px-3 py-2 text-left">Factura</th><th className="px-3 py-2 text-left">Cliente</th><th className="px-3 py-2 text-right">Total</th></tr></thead>
                  <tbody>
                    {invoices.map((inv, i) => (
                      <tr key={inv.id} className={`border-b border-slate-50 ${i % 2 === 0 ? "" : "bg-slate-50/50"}`}>
                        <td className="px-3 py-2 font-mono">{inv.numberTemplate?.fullNumber || inv.number || inv.id}</td>
                        <td className="px-3 py-2">{inv.client?.name || "—"}</td>
                        <td className="px-3 py-2 text-right font-medium text-emerald-700">{formatCOP(inv.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            {/* Egresos */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 bg-red-50 border-b border-red-100 flex items-center gap-2">
                <TrendingDown size={14} className="text-red-600" />
                <span className="text-sm font-bold text-red-700">Egresos ({bills.length} facturas)</span>
              </div>
              <div className="overflow-y-auto max-h-60">
                <table className="w-full text-xs">
                  <thead><tr className="bg-slate-50"><th className="px-3 py-2 text-left">Factura</th><th className="px-3 py-2 text-left">Proveedor</th><th className="px-3 py-2 text-right">Total</th></tr></thead>
                  <tbody>
                    {bills.map((bill, i) => (
                      <tr key={bill.id} className={`border-b border-slate-50 ${i % 2 === 0 ? "" : "bg-slate-50/50"}`}>
                        <td className="px-3 py-2 font-mono">{bill.numberTemplate?.fullNumber || bill.number || bill.id}</td>
                        <td className="px-3 py-2">{bill.vendor?.name || "—"}</td>
                        <td className="px-3 py-2 text-right font-medium text-red-700">{formatCOP(bill.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
