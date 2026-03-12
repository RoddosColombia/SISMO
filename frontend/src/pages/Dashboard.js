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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white font-montserrat">Dashboard Financiero</h2>
          <p className="text-xs mt-1" style={{ color: "#555" }}>Octubre 2025 — Datos en tiempo real de Alegra</p>
        </div>
        <button onClick={loadData}
          className="flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-lg transition"
          style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#888" }}
          data-testid="refresh-dashboard-btn">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} style={{ color: "#00E5FF" }} />
          Actualizar
        </button>
      </div>

      {/* Proactive Alerts */}
      <ProactiveAlerts />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-cards">
        <KpiCard title="Ventas del Mes"  value={formatCOP(totalVentas)} subtitle="5 facturas emitidas"         icon={TrendingUp}   accentColor="#00E5FF" delta={12}  testId="kpi-ventas" />
        <KpiCard title="Gastos del Mes"  value={formatCOP(totalGastos)} subtitle="5 facturas de compra"        icon={TrendingDown}  accentColor="#FF4444" delta={-3}  testId="kpi-gastos" />
        <KpiCard title="Flujo de Caja"   value={formatCOP(flujoCaja)}   subtitle={flujoCaja >= 0 ? "Positivo" : "Negativo"} icon={DollarSign} accentColor="#00C853" testId="kpi-flujo" />
        <KpiCard title="Por Cobrar"      value={formatCOP(pendientes)}  subtitle="Facturas pendientes y vencidas" icon={Clock}       accentColor="#FFB300" testId="kpi-por-cobrar" />
      </div>

      {/* Chart */}
      <div className="rounded-xl p-5" style={{ background: "#1A1A1A", border: "1px solid #1E1E1E" }} data-testid="revenue-chart">
        <h3 className="text-sm font-bold text-white font-montserrat mb-4">Ingresos vs Gastos — Últimos 6 meses</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={CHART_DATA} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
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
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "#888" }}>{inv.number}</td>
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
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "#888" }}>{bill.number}</td>
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
