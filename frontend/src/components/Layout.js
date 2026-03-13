import React, { useState, useEffect, useCallback } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, FileText, ShoppingCart, TrendingUp, TrendingDown,
  Building2, Settings, LogOut, ChevronLeft, Menu, Bell, User,
  CreditCard, Receipt, Calculator, Users, Gift, BarChart2, Tag, Target, Bike, X,
  Wrench, BookOpen, Wallet
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import AIChatWidget from "./AIChatWidget";

const MODULES = [
  { path: "/dashboard",            label: "Dashboard",             icon: LayoutDashboard, group: null },
  { path: "/facturacion-venta",    label: "Facturación Venta",     icon: FileText,        group: "Facturación" },
  { path: "/facturacion-compra",   label: "Facturación Compra",    icon: ShoppingCart,    group: "Facturación" },
  { path: "/registro-cuotas",      label: "Registro de Cuotas",    icon: CreditCard,      group: "Facturación" },
  { path: "/causacion-ingresos",   label: "Causación Ingresos",    icon: TrendingUp,      group: "Causaciones" },
  { path: "/causacion-egresos",    label: "Causación Egresos",     icon: TrendingDown,    group: "Causaciones" },
  { path: "/conciliacion-bancaria",label: "Conciliación Bancaria", icon: Building2,       group: "Causaciones" },
  { path: "/inventario-auteco",    label: "Motos",                 icon: Bike,            group: "Inventario" },
  { path: "/repuestos",            label: "Repuestos",             icon: Wrench,          group: "Inventario" },
  { path: "/loanbook",             label: "Loanbook",              icon: BookOpen,        group: "Cartera" },
  { path: "/cartera",              label: "Cartera",               icon: Wallet,          group: "Cartera" },
  { path: "/impuestos",            label: "Impuestos y Alertas",   icon: Receipt,         group: "Fiscal" },
  { path: "/retenciones",          label: "Retenciones",           icon: Calculator,      group: "Fiscal" },
  { path: "/nomina",               label: "Nómina",                icon: Users,           group: "RRHH" },
  { path: "/prestaciones",         label: "Prestaciones Sociales", icon: Gift,            group: "RRHH" },
  { path: "/estado-resultados",    label: "Estado de Resultados",  icon: BarChart2,       group: "Reportes" },
  { path: "/egresos-clasificados", label: "Egresos Clasificados",  icon: Tag,             group: "Reportes" },
  { path: "/presupuesto",          label: "Presupuesto",           icon: Target,          group: "Reportes" },
  { path: "/configuracion",        label: "Configuración",         icon: Settings,        group: null },
];

function AlegraStatusBadge({ status }) {
  if (status === "demo") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse-dot" />
      Modo Demo
    </span>
  );
  if (status === "connected") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-[#00C853]/10 text-[#00C853] border border-[#00C853]/30 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-[#00C853]" />
      Alegra conectado
    </span>
  );
  if (status === "token_invalid") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/30 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
      Token expirado
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/30 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      Sin conexión
    </span>
  );
}

/* Radar "O" icon — matches RODDOS logo */
function RoddosIcon({ size = 32 }) {
  const r = size / 2;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="3"   stroke="#00E5FF" strokeWidth="2" />
      <path d="M16 16 m-6.5 0 a6.5 6.5 0 0 1 6.5-6.5" stroke="#00C853" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M16 16 m-6.5 0 a6.5 6.5 0 0 0 6.5 6.5" stroke="#00E5FF" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M16 16 m-10.5 0 a10.5 10.5 0 0 1 10.5-10.5" stroke="#00C853" strokeWidth="1.6" strokeLinecap="round" opacity="0.7" />
      <path d="M16 16 m-10.5 0 a10.5 10.5 0 0 0 10.5 10.5" stroke="#00E5FF" strokeWidth="1.6" strokeLinecap="round" opacity="0.7" />
      <path d="M16 16 m-14 0 a14 14 0 0 1 14-14" stroke="#00C853" strokeWidth="1.2" strokeLinecap="round" opacity="0.45" />
      <path d="M16 16 m-14 0 a14 14 0 0 0 14 14" stroke="#00E5FF" strokeWidth="1.2" strokeLinecap="round" opacity="0.45" />
    </svg>
  );
}

export default function Layout() {
  const { user, logout, api } = useAuth();
  const { connectionStatus } = useAlegra();
  const [collapsed, setCollapsed]     = useState(false);
  const [mobileOpen, setMobileOpen]   = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [showNotifs, setShowNotifs]   = useState(false);
  const location  = useLocation();
  const navigate  = useNavigate();

  const currentModule = MODULES.find(m => location.pathname.startsWith(m.path));

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get("/notifications", { params: { unread_only: true } });
      setNotifications(res.data || []);
    } catch {}
  }, [api]);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const markAllRead = async () => {
    try { await api.put("/notifications/read-all"); setNotifications([]); } catch {}
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#F8FAFC" }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-20 bg-black/70 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <aside
        className={`
          fixed top-0 left-0 h-full flex flex-col z-30
          transition-all duration-300
          ${collapsed ? "w-[68px]" : "w-[240px]"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        style={{ background: "#121212", borderRight: "1px solid #1E1E1E" }}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div
          className={`flex items-center border-b ${collapsed ? "p-4 justify-center" : "px-4 py-4 gap-3"}`}
          style={{ borderColor: "#1E1E1E" }}
        >
          <RoddosIcon size={collapsed ? 30 : 34} />
          {!collapsed && (
            <div>
              <div className="text-sm font-black text-white font-montserrat leading-tight tracking-wide">RODDOS</div>
              <div className="text-[10px] font-medium" style={{ color: "#00E5FF" }}>Contable IA</div>
            </div>
          )}
        </div>

        {/* Collapse toggle (desktop) */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center w-5 h-5 absolute -right-2.5 top-16 rounded-full shadow-lg"
          style={{ background: "#1E1E1E", border: "1px solid #2A2A2A", color: "#888" }}
          data-testid="sidebar-collapse-btn"
        >
          <ChevronLeft size={11} className={`transition-transform ${collapsed ? "rotate-180" : ""}`} />
        </button>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-0.5">
          {(() => {
            const items = [];
            let lastGroup = undefined;
            MODULES.forEach((mod) => {
              if (mod.group !== lastGroup) {
                if (mod.group && !collapsed) {
                  items.push(
                    <div key={`grp-${mod.group}`} className="px-3 pt-4 pb-1.5">
                      <span className="text-[9px] uppercase tracking-[0.12em] font-bold" style={{ color: "#444" }}>
                        {mod.group}
                      </span>
                    </div>
                  );
                }
                lastGroup = mod.group;
              }
              items.push(
                <NavLink
                  key={mod.path}
                  to={mod.path}
                  data-testid={`nav-${mod.path.replace("/", "")}`}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all duration-150
                    ${collapsed ? "justify-center" : ""}
                    ${isActive ? "nav-active" : "nav-default"}`
                  }
                  style={({ isActive }) => isActive
                    ? { background: "rgba(0,229,255,0.1)", color: "#00E5FF", borderLeft: "2px solid #00E5FF", paddingLeft: "10px" }
                    : { color: "#888", borderLeft: "2px solid transparent" }
                  }
                >
                  <mod.icon size={16} className="flex-shrink-0" />
                  {!collapsed && <span className="text-[12.5px] font-medium">{mod.label}</span>}
                </NavLink>
              );
            });
            return items;
          })()}
        </nav>

        {/* User section */}
        <div className={`p-3 ${collapsed ? "flex justify-center" : ""}`} style={{ borderTop: "1px solid #1E1E1E" }}>
          {collapsed ? (
            <button onClick={logout} className="p-1.5 rounded-lg hover:bg-white/5 transition" style={{ color: "#666" }} data-testid="logout-btn">
              <LogOut size={17} />
            </button>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: "linear-gradient(135deg, #00E5FF22, #00C85322)", border: "1px solid #00E5FF44" }}>
                  <span className="text-xs font-bold" style={{ color: "#00E5FF" }}>
                    {user?.name?.[0]?.toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold text-white truncate">{user?.name}</div>
                  <div className="text-[10px]" style={{ color: "#00C853" }}>
                    {user?.role === "admin" ? "Administrador" : "Usuario"}
                  </div>
                </div>
              </div>
              <button onClick={logout} className="p-1.5 rounded-lg hover:bg-white/5 transition flex-shrink-0"
                style={{ color: "#555" }} data-testid="logout-btn">
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${collapsed ? "lg:ml-[68px]" : "lg:ml-[240px]"}`}>

        {/* Header */}
        <header
          className="h-14 flex items-center justify-between px-4 lg:px-5 sticky top-0 z-20"
          style={{ background: "#121212", borderBottom: "1px solid #1E1E1E" }}
          data-testid="app-header"
        >
          <div className="flex items-center gap-3">
            <button className="lg:hidden" style={{ color: "#888" }} onClick={() => setMobileOpen(!mobileOpen)}>
              <Menu size={20} />
            </button>
            <h1 className="text-sm font-bold text-white font-montserrat">
              {currentModule?.label || "RODDOS Contable IA"}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <AlegraStatusBadge status={connectionStatus} />

            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setShowNotifs(!showNotifs)}
                className="relative p-1.5 rounded-lg transition hover:bg-white/5"
                style={{ color: "#666" }}
                data-testid="notifications-bell"
              >
                <Bell size={17} />
                {notifications.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-4 h-4 text-[9px] font-bold rounded-full flex items-center justify-center"
                    style={{ background: "#FF4444", color: "#fff" }}>
                    {notifications.length > 9 ? "9+" : notifications.length}
                  </span>
                )}
              </button>
              {showNotifs && (
                <div className="absolute right-0 top-10 w-72 rounded-xl shadow-2xl z-50 overflow-hidden"
                  style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}>
                  <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid #2A2A2A" }}>
                    <span className="text-xs font-bold text-white">Notificaciones</span>
                    <div className="flex gap-2 items-center">
                      {notifications.length > 0 && (
                        <button onClick={markAllRead} className="text-[10px] hover:underline" style={{ color: "#00E5FF" }}>
                          Marcar leídas
                        </button>
                      )}
                      <button onClick={() => setShowNotifs(false)} style={{ color: "#555" }}>
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-xs" style={{ color: "#555" }}>Sin notificaciones nuevas</div>
                  ) : (
                    <div className="max-h-60 overflow-y-auto">
                      {notifications.map((n, i) => (
                        <div key={i} className="px-4 py-3 hover:bg-white/5 transition" style={{ borderBottom: "1px solid #1E1E1E" }}>
                          <p className="text-xs font-semibold text-white">{n.event_type}</p>
                          <p className="text-[10px] mt-0.5" style={{ color: "#555" }}>
                            {n.created_at?.slice(0, 16).replace("T", " ")}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Avatar */}
            <div className="w-8 h-8 rounded-full flex items-center justify-center cursor-pointer"
              style={{ background: "linear-gradient(135deg, #00E5FF33, #00C85333)", border: "1px solid #00E5FF55" }}
              data-testid="user-avatar">
              <span className="text-[11px] font-black" style={{ color: "#00E5FF" }}>
                {user?.name?.[0]?.toUpperCase()}
              </span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6 overflow-auto animate-fadeInUp" style={{ background: "#F8FAFC" }}>
          <Outlet />
        </main>
      </div>

      <AIChatWidget />
    </div>
  );
}
