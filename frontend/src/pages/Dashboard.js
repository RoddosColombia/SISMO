import React, { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown, DollarSign, Clock, ChevronRight, RefreshCw, Calendar } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { formatCOP, getStatusInfo, getDocNumber, getVendorName, getMonthRange, formatMonthYear } from "../utils/formatters";
import { toast } from "sonner";
import ProactiveAlerts from "../components/ProactiveAlerts";

function buildChartData(invoices, bills) {
  const months = {};
  for (let i = 5; i >= 0; i--) {
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() - i);
    const key = d.toISOString().slice(0, 7);
    const label = d.toLocaleDateString("es-CO", { month: "short" });
    months[key] = { month: label.charAt(0).toUpperCase() + label.slice(1, 3), ingresos: 0, gastos: 0 };
  }
  (invoices || []).forEach(inv => {
    const m = (inv.date || "").slice(0, 7);
    if (months[m]) months[m].ingresos += parseFloat(inv.total || 0);
  });
  (bills || []).forEach(b => {
    const m = (b.date || "").slice(0, 7);
    if (months[m]) months[m].gastos += parseFloat(b.total || 0);
  });
  return Object.values(months);
}

function KpiCard({ title, value, subtitle, icon: Icon, accentColor, delta, testId }) {
  return (
    <div
      className="rounded-xl p-5 transition-all hover:scale-[1.01]"
      style={{
        background: "#1A1A1A",
        border: `1px solid #1E1E1E`,
        borderLeft: `3px solid ${accentColor}`,
      }}
      data-testid={testId}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#555" }}>{title}</p>
          <p className="text-2xl font-black font-montserrat" style={{ color: "#E8E8E8" }}>{value}</p>
          {subtitle && <p className="text-xs mt-1" style={{ color: "#555" }}>{subtitle}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: `${accentColor}15` }}>
          <Icon size={18} style={{ color: accentColor }} />
        </div>
      </div>
      {delta !== undefined && (
        <div className="flex items-center gap-1 mt-3 text-xs font-semibold"
          style={{ color: delta >= 0 ? "#00C853" : "#FF4444" }}>
          {delta >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
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
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  const { from: defaultFrom, to: defaultTo } = getMonthRange();
  const [dateFrom, setDateFrom] = useState(defaultFrom);
  const [dateTo, setDateTo] = useState(defaultTo);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // 6-month range for chart
      const sixMonthsAgo = new Date();
      sixMonthsAgo.setDate(1);
      sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 5);
      const chartStart = sixMonthsAgo.toISOString().split("T")[0];
      const chartEnd = new Date().toISOString().split("T")[0];

      const [invResp, billResp, allInvResp, allBillResp] = await Promise.all([
        api.get("/alegra/invoices", { params: { date_start: dateFrom, date_end: dateTo } }),
        api.get("/alegra/bills", { params: { date_start: dateFrom, date_end: dateTo } }),
        api.get("/alegra/invoices", { params: { date_start: chartStart, date_end: chartEnd } }),
        api.get("/alegra/bills", { params: { date_start: chartStart, date_end: chartEnd } }),
      ]);
      setInvoices(invResp.data.slice(0, 5));
      setBills(billResp.data.slice(0, 5));
      setChartData(buildChartData(allInvResp.data, allBillResp.data));
    } catch (e) {
      toast.error("Error cargando datos del dashboard");
    } finally {
      setLoading(false);
    }
  }, [api, dateFrom, dateTo]); // eslint-disable-line

  useEffect(() => { loadData(); }, [loadData]);

  const totalVentas = invoices.reduce((s, i) => s + (i.total || 0), 0);
  const totalGastos = bills.reduce((s, b) => s + (b.total || 0), 0);
  const pendientes = invoices.filter(i => i.status === "open" || i.status === "overdue").reduce((s, i) => s + (i.total || 0), 0);
  const flujoCaja = totalVentas - totalGastos;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-xl p-3 shadow-xl text-sm" style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}>
        <p className="font-bold text-white mb-2">{label}</p>
        {payload.map(p => (
          <p key={p.name} style={{ color: p.color }} className="font-medium">{p.name}: {formatCOP(p.value)}</p>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white font-montserrat">Dashboard Financiero</h2>
          <p className="text-xs mt-1" style={{ color: "#555" }}>
            {formatMonthYear(dateFrom)} — {dateFrom !== dateTo ? formatMonthYear(dateTo) : ""} — Datos en tiempo real de Alegra
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Date filter */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium" style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#888" }}>
            <Calendar size={13} style={{ color: "#00E5FF" }} />
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="bg-transparent outline-none text-xs" style={{ color: "#CCC", width: 130 }} data-testid="dashboard-date-from" />
            <span style={{ color: "#444" }}>—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="bg-transparent outline-none text-xs" style={{ color: "#CCC", width: 130 }} data-testid="dashboard-date-to" />
          </div>
          <button onClick={loadData}
            className="flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-lg transition"
            style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#888" }}
            data-testid="refresh-dashboard-btn">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} style={{ color: "#00E5FF" }} />
            Actualizar
          </button>
        </div>
      </div>

      {/* Proactive Alerts */}
      <ProactiveAlerts />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-cards">
        <KpiCard title="Ventas del Período" value={formatCOP(totalVentas)} subtitle={`${invoices.length} facturas emitidas`} icon={TrendingUp} accentColor="#00E5FF" testId="kpi-ventas" />
        <KpiCard title="Gastos del Período" value={formatCOP(totalGastos)} subtitle={`${bills.length} facturas de compra`} icon={TrendingDown} accentColor="#FF4444" testId="kpi-gastos" />
        <KpiCard title="Flujo de Caja" value={formatCOP(flujoCaja)} subtitle={flujoCaja >= 0 ? "Positivo" : "Negativo"} icon={DollarSign} accentColor="#00C853" testId="kpi-flujo" />
        <KpiCard title="Por Cobrar" value={formatCOP(pendientes)} subtitle="Facturas pendientes y vencidas" icon={Clock} accentColor="#FFB300" testId="kpi-por-cobrar" />
      </div>

      {/* Chart */}
      <div className="rounded-xl p-5" style={{ background: "#1A1A1A", border: "1px solid #1E1E1E" }} data-testid="revenue-chart">
        <h3 className="text-sm font-bold text-white font-montserrat mb-4">Ingresos vs Gastos — Últimos 6 meses</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
            <defs>
              <linearGradient id="colorIngresos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00E5FF" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#00E5FF" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorGastos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#FF4444" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#FF4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#555" }} />
            <YAxis tickFormatter={(v) => `$${(v / 1000000).toFixed(1)}M`} tick={{ fontSize: 10, fill: "#555" }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "12px", color: "#888" }} />
            <Area type="monotone" dataKey="ingresos" name="Ingresos" stroke="#00E5FF" strokeWidth={2} fill="url(#colorIngresos)" />
            <Area type="monotone" dataKey="gastos"   name="Gastos"   stroke="#FF4444"  strokeWidth={2} fill="url(#colorGastos)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Invoices */}
        <div className="rounded-xl overflow-hidden" style={{ background: "#1A1A1A", border: "1px solid #1E1E1E" }} data-testid="recent-invoices">
          <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid #1E1E1E" }}>
            <h3 className="text-sm font-bold text-white font-montserrat">Últimas Facturas de Venta</h3>
            <button onClick={() => navigate("/facturacion-venta")} className="text-xs flex items-center gap-1 font-medium" style={{ color: "#00E5FF" }}>
              Ver todas <ChevronRight size={13} />
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-wider" style={{ background: "#161616", color: "#555" }}>
                <th className="text-left px-4 py-2.5">Número</th>
                <th className="text-left px-4 py-2.5">Cliente</th>
                <th className="text-right px-4 py-2.5">Total</th>
                <th className="text-center px-4 py-2.5">Estado</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "#444" }}>Cargando...</td></tr>
              ) : invoices.map((inv) => (
                <tr key={inv.id} className="transition-colors" style={{ borderTop: "1px solid #161616" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#1E1E1E"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "#888" }}>{getDocNumber(inv)}</td>
                  <td className="px-4 py-2.5 max-w-[120px] truncate" style={{ color: "#E8E8E8" }}>{inv.client?.name}</td>
                  <td className="px-4 py-2.5 text-right font-bold num-right" style={{ color: "#00E5FF" }}>{formatCOP(inv.total)}</td>
                  <td className="px-4 py-2.5 text-center"><StatusBadge status={inv.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bills */}
        <div className="rounded-xl overflow-hidden" style={{ background: "#1A1A1A", border: "1px solid #1E1E1E" }} data-testid="recent-bills">
          <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid #1E1E1E" }}>
            <h3 className="text-sm font-bold text-white font-montserrat">Últimas Facturas de Compra</h3>
            <button onClick={() => navigate("/facturacion-compra")} className="text-xs flex items-center gap-1 font-medium" style={{ color: "#00E5FF" }}>
              Ver todas <ChevronRight size={13} />
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-wider" style={{ background: "#161616", color: "#555" }}>
                <th className="text-left px-4 py-2.5">Número</th>
                <th className="text-left px-4 py-2.5">Proveedor</th>
                <th className="text-right px-4 py-2.5">Total</th>
                <th className="text-center px-4 py-2.5">Estado</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "#444" }}>Cargando...</td></tr>
              ) : bills.map((bill) => (
                <tr key={bill.id} className="transition-colors" style={{ borderTop: "1px solid #161616" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#1E1E1E"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "#888" }}>{getDocNumber(bill)}</td>
                  <td className="px-4 py-2.5 max-w-[120px] truncate" style={{ color: "#E8E8E8" }}>{bill.provider?.name}</td>
                  <td className="px-4 py-2.5 text-right font-bold num-right" style={{ color: "#FF4444" }}>{formatCOP(bill.total)}</td>
                  <td className="px-4 py-2.5 text-center"><StatusBadge status={bill.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl p-5" style={{ background: "linear-gradient(135deg, #121212, #1A1A1A)", border: "1px solid #00E5FF20" }} data-testid="quick-actions">
        <h3 className="text-sm font-bold text-white mb-3 font-montserrat">Acciones Rápidas</h3>
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
              className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-[1.03]"
              style={{
                background: "#1A1A1A",
                border: "1px solid #00E5FF30",
                color: "#00E5FF",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = "#00E5FF15";
                e.currentTarget.style.borderColor = "#00E5FF";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "#1A1A1A";
                e.currentTarget.style.borderColor = "#00E5FF30";
              }}
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
