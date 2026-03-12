import React, { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, DollarSign, Clock, ChevronRight, RefreshCw } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { formatCOP, formatShortDate, getStatusInfo, getMonthName } from "../utils/formatters";
import { toast } from "sonner";
import ProactiveAlerts from "../components/ProactiveAlerts";

const CHART_DATA = [
  { month: "May", ingresos: 12500000, gastos: 9200000 },
  { month: "Jun", ingresos: 15800000, gastos: 11100000 },
  { month: "Jul", ingresos: 13200000, gastos: 10500000 },
  { month: "Ago", ingresos: 18900000, gastos: 12300000 },
  { month: "Sep", ingresos: 16400000, gastos: 11800000 },
  { month: "Oct", ingresos: 23865000, gastos: 17258000 },
];

function KpiCard({ title, value, subtitle, icon: Icon, iconColor, borderColor, delta, testId }) {
  return (
    <div className={`bg-white rounded-xl p-5 border-l-4 ${borderColor} shadow-sm hover:shadow-md transition-shadow`} data-testid={testId}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold text-[#0F172A] font-montserrat mt-1">{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl ${iconColor} flex items-center justify-center flex-shrink-0`}>
          <Icon size={20} />
        </div>
      </div>
      {delta !== undefined && (
        <div className={`flex items-center gap-1 mt-3 text-xs font-medium ${delta >= 0 ? "text-green-600" : "text-red-600"}`}>
          {delta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {Math.abs(delta)}% vs mes anterior
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const info = getStatusInfo(status);
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${info.className}`}>{info.label}</span>;
}

export default function Dashboard() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [invResp, billResp] = await Promise.all([
        api.get("/alegra/invoices"),
        api.get("/alegra/bills"),
      ]);
      setInvoices(invResp.data.slice(0, 5));
      setBills(billResp.data.slice(0, 5));
    } catch (e) {
      toast.error("Error cargando datos del dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []); // eslint-disable-line

  const totalVentas = invoices.reduce((s, i) => s + (i.total || 0), 0);
  const totalGastos = bills.reduce((s, b) => s + (b.total || 0), 0);
  const pendientes = invoices.filter(i => i.status === "open" || i.status === "overdue").reduce((s, i) => s + (i.total || 0), 0);
  const flujoCaja = totalVentas - totalGastos;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-lg text-sm">
        <p className="font-semibold text-slate-700 mb-2">{label}</p>
        {payload.map(p => (
          <p key={p.name} style={{ color: p.color }} className="font-medium">{p.name}: {formatCOP(p.value)}</p>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Dashboard Financiero</h2>
          <p className="text-sm text-slate-500">Octubre 2025 — Datos en tiempo real de Alegra</p>
        </div>
        <button onClick={loadData} className="flex items-center gap-2 text-sm text-slate-500 hover:text-[#0F2A5C] border border-slate-200 px-3 py-2 rounded-lg hover:border-[#0F2A5C] transition-colors" data-testid="refresh-dashboard-btn">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Actualizar
        </button>
      </div>

      {/* Proactive Alerts */}
      <ProactiveAlerts />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-cards">
        <KpiCard title="Ventas del Mes" value={formatCOP(totalVentas)} subtitle="5 facturas emitidas" icon={TrendingUp} iconColor="bg-blue-50 text-blue-600" borderColor="border-[#0F2A5C]" delta={12} testId="kpi-ventas" />
        <KpiCard title="Gastos del Mes" value={formatCOP(totalGastos)} subtitle="5 facturas de compra" icon={TrendingDown} iconColor="bg-red-50 text-red-500" borderColor="border-red-400" delta={-3} testId="kpi-gastos" />
        <KpiCard title="Flujo de Caja" value={formatCOP(flujoCaja)} subtitle={flujoCaja >= 0 ? "Positivo" : "Negativo"} icon={DollarSign} iconColor="bg-green-50 text-green-600" borderColor="border-green-500" testId="kpi-flujo" />
        <KpiCard title="Por Cobrar" value={formatCOP(pendientes)} subtitle="Facturas pendientes y vencidas" icon={Clock} iconColor="bg-amber-50 text-amber-600" borderColor="border-[#C9A84C]" testId="kpi-por-cobrar" />
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5" data-testid="revenue-chart">
        <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat mb-4">Ingresos vs Gastos — Últimos 6 meses</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={CHART_DATA} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
            <defs>
              <linearGradient id="colorIngresos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0F2A5C" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#0F2A5C" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorGastos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#C9A84C" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#C9A84C" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="month" tick={{ fontSize: 12, fill: "#64748B" }} />
            <YAxis tickFormatter={(v) => `$${(v / 1000000).toFixed(1)}M`} tick={{ fontSize: 11, fill: "#64748B" }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
            <Area type="monotone" dataKey="ingresos" name="Ingresos" stroke="#0F2A5C" strokeWidth={2} fill="url(#colorIngresos)" />
            <Area type="monotone" dataKey="gastos" name="Gastos" stroke="#C9A84C" strokeWidth={2} fill="url(#colorGastos)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Invoices */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="recent-invoices">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Últimas Facturas de Venta</h3>
            <button onClick={() => navigate("/facturacion-venta")} className="text-xs text-[#0F2A5C] hover:text-[#C9A84C] flex items-center gap-1 font-medium">
              Ver todas <ChevronRight size={13} />
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="text-left px-4 py-2.5">Número</th>
                <th className="text-left px-4 py-2.5">Cliente</th>
                <th className="text-right px-4 py-2.5">Total</th>
                <th className="text-center px-4 py-2.5">Estado</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-400">Cargando...</td></tr>
              ) : invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-slate-50 hover:bg-[#F0F4FF]/30 transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{inv.number}</td>
                  <td className="px-4 py-2.5 text-slate-700 max-w-[120px] truncate">{inv.client?.name}</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-[#0F172A] num-right">{formatCOP(inv.total)}</td>
                  <td className="px-4 py-2.5 text-center"><StatusBadge status={inv.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bills */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden" data-testid="recent-bills">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Últimas Facturas de Compra</h3>
            <button onClick={() => navigate("/facturacion-compra")} className="text-xs text-[#0F2A5C] hover:text-[#C9A84C] flex items-center gap-1 font-medium">
              Ver todas <ChevronRight size={13} />
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="text-left px-4 py-2.5">Número</th>
                <th className="text-left px-4 py-2.5">Proveedor</th>
                <th className="text-right px-4 py-2.5">Total</th>
                <th className="text-center px-4 py-2.5">Estado</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-400">Cargando...</td></tr>
              ) : bills.map((bill) => (
                <tr key={bill.id} className="border-t border-slate-50 hover:bg-[#F0F4FF]/30 transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{bill.number}</td>
                  <td className="px-4 py-2.5 text-slate-700 max-w-[120px] truncate">{bill.provider?.name}</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-[#0F172A] num-right">{formatCOP(bill.total)}</td>
                  <td className="px-4 py-2.5 text-center"><StatusBadge status={bill.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gradient-to-r from-[#0F2A5C] to-[#163A7A] rounded-xl p-5 text-white" data-testid="quick-actions">
        <h3 className="text-sm font-bold mb-3 font-montserrat">Acciones Rápidas</h3>
        <div className="flex flex-wrap gap-2">
          {[
            { label: "Nueva Factura Venta", path: "/facturacion-venta" },
            { label: "Registrar Compra", path: "/facturacion-compra" },
            { label: "Causar Ingreso", path: "/causacion-ingresos" },
            { label: "Causar Egreso", path: "/causacion-egresos" },
          ].map(a => (
            <button
              key={a.path}
              onClick={() => navigate(a.path)}
              className="text-xs font-semibold bg-white/10 hover:bg-[#C9A84C] hover:text-[#0F2A5C] px-4 py-2 rounded-lg transition-colors border border-white/20"
              data-testid={`quick-action-${a.path.replace("/", "")}`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
