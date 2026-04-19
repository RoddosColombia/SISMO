import React, { useState, useEffect, useCallback } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Settings, LogOut, ChevronLeft, Menu, Bell, User,
  CreditCard, Receipt, BarChart2, Bike, X,
  BookOpen, Wallet, Bot, BriefcaseBusiness, Brain, TrendingUp, Target, Upload, Inbox,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";

const MODULES = [
  { path: "/agente-contable",  label: "Agente Contador",    icon: Bot,              group: null,  badge: "active" },
  { path: "/cargar-extracto",  label: "Cargar Extracto",    icon: Upload,           group: null  },
  { path: "/backlog",          label: "Backlog",             icon: Inbox,            group: null, badgeKey: "backlog" },
  { path: "/cfo-estrategico",  label: "CFO Estratégico",    icon: Brain,            group: null  },
  { path: "/dashboard",        label: "Dashboard",           icon: LayoutDashboard,  group: null  },
  { path: "/cfo",              label: "Panel CFO",           icon: TrendingUp,       group: null  },
  { path: "/presupuesto",      label: "Presupuesto",         icon: Wallet,           group: null  },
  { path: "/impuestos",        label: "Impuestos",           icon: Receipt,          group: null  },
  { path: "/inventario-auteco",label: "Motos",               icon: Bike,             group: null  },
  { path: "/loanbook",         label: "Loanbook",            icon: BookOpen,         group: null  },
  { path: "/cartera-legacy",   label: "Cartera Legacy",      icon: CreditCard,       group: null  },
  { path: "/radar",             label: "RADAR",               icon: Target,           group: null  },
  { path: "/perfil",            label: "Mi perfil",           icon: User,             group: null  },
  { path: "/configuracion",    label: "Configuración",       icon: Settings,         group: null  },
];

function AlegraStatusBadge({ status }) {
  if (status === "demo") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-amber-50 text-amber-700 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse-dot" />
      Modo Demo
    </span>
  );
  if (status === "connected") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      Alegra conectado
    </span>
  );
  if (status === "token_invalid") return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-orange-50 text-orange-700 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
      Token expirado
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 text-xs font-semibold bg-red-50 text-red-700 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      Sin conexión
    </span>
  );
}

/* RODDOS logo mark — updated to design system palette */
function RoddosIcon({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="3"   stroke="#006875" strokeWidth="2" />
      <path d="M16 16 m-6.5 0 a6.5 6.5 0 0 1 6.5-6.5" stroke="#006e2a" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M16 16 m-6.5 0 a6.5 6.5 0 0 0 6.5 6.5" stroke="#006875" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M16 16 m-10.5 0 a10.5 10.5 0 0 1 10.5-10.5" stroke="#006e2a" strokeWidth="1.6" strokeLinecap="round" opacity="0.65" />
      <path d="M16 16 m-10.5 0 a10.5 10.5 0 0 0 10.5 10.5" stroke="#006875" strokeWidth="1.6" strokeLinecap="round" opacity="0.65" />
      <path d="M16 16 m-14 0 a14 14 0 0 1 14-14" stroke="#006e2a" strokeWidth="1.2" strokeLinecap="round" opacity="0.35" />
      <path d="M16 16 m-14 0 a14 14 0 0 0 14 14" stroke="#006875" strokeWidth="1.2" strokeLinecap="round" opacity="0.35" />
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
  // BUILD 9 — Badge alertas CFO en sidebar
  const [cfoAlertCount, setCfoAlertCount] = useState(0);
  // BUILD 23 — Badge backlog pendientes
  const [backlogCount, setBacklogCount] = useState(0);
  const location  = useLocation();
  const navigate  = useNavigate();

  const isChatPage = location.pathname.startsWith("/agente-contable");
  const currentModule = MODULES.find(m => location.pathname.startsWith(m.path));

  const fetchNotifications = useCallback(async () => {
    if (!navigator.onLine) return; // Don't poll when offline
    try {
      const res = await api.get("/notifications", { params: { unread_only: true } });
      setNotifications(res.data || []);
    } catch (err) {
      // Silent for notifications — fallback to empty
      console.warn("⚠️  Error fetching notifications:", err?.message);
      setNotifications([]);
    }
  }, [api]);

  // Poll CFO alerts every 60s for sidebar badge
  const fetchCfoAlerts = useCallback(async () => {
    if (!navigator.onLine) return; // Don't poll when offline
    try {
      const res = await api.get("/cfo/alertas");
      const activas = (res.data || []).filter((a) => a.estado === "nueva");
      setCfoAlertCount(activas.length);
    } catch (err) {
      // Silent for alerts — fallback to 0
      console.warn("⚠️  Error fetching CFO alerts:", err?.message);
      setCfoAlertCount(0);
    }
  }, [api]);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  useEffect(() => {
    fetchCfoAlerts();
    const cfoPoll = setInterval(fetchCfoAlerts, 60000);
    return () => clearInterval(cfoPoll);
  }, [fetchCfoAlerts]);

  // Poll backlog stats every 60s
  const fetchBacklogStats = useCallback(async () => {
    if (!navigator.onLine) return;
    try {
      const res = await api.get("/contabilidad_pendientes/backlog/stats");
      setBacklogCount(res.data?.total_pendientes ?? 0);
    } catch {
      // silent
    }
  }, [api]);

  useEffect(() => {
    fetchBacklogStats();
    const poll = setInterval(fetchBacklogStats, 60000);
    return () => clearInterval(poll);
  }, [fetchBacklogStats]);

  const markAllRead = async () => {
    try { await api.put("/notifications/read-all"); setNotifications([]); } catch {}
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#fcf9f8" }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-20 bg-black/40 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* ── Sidebar — surface-container-low, no border, tonal separation ───────── */}
      <aside
        className={`
          fixed top-0 left-0 h-full flex flex-col z-30
          transition-all duration-300
          ${collapsed ? "w-[68px]" : "w-[240px]"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        style={{ background: "#f6f3f2" }}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div
          className={`flex items-center ${collapsed ? "p-4 justify-center" : "px-4 py-4 gap-3"}`}
          style={{ paddingBottom: "16px" }}
        >
          <RoddosIcon size={collapsed ? 30 : 34} />
          {!collapsed && (
            <div>
              <div className="text-sm font-black font-public-sans leading-tight tracking-wide" style={{ color: "#1c1b1f" }}>
                RODDOS
              </div>
              <div className="text-[10px] font-medium" style={{ color: "#006875" }}>Contable IA</div>
            </div>
          )}
        </div>

        {/* Collapse toggle (desktop) — ambient shadow, no border */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center w-5 h-5 absolute -right-2.5 top-16 rounded-full"
          style={{
            background: "#ffffff",
            boxShadow: "0 2px 8px rgba(28,27,31,0.10)",
            color: "#49454f",
          }}
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
                      <span className="text-[9px] uppercase tracking-[0.12em] font-bold" style={{ color: "#9e9a97" }}>
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
                    ${isActive ? "nav-active" : "nav-default hover:bg-black/[0.03]"}`
                  }
                  style={({ isActive }) => isActive
                    ? { background: "rgba(0,110,42,0.08)", color: "#006e2a" }
                    : { color: "#49454f" }
                  }
                >
                  <div className="relative flex-shrink-0">
                    <mod.icon size={16} />
                    {/* BUILD 9: Badge rojo para CFO cuando hay alertas activas */}
                    {mod.path === "/cfo" && cfoAlertCount > 0 && (
                      <span
                        className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full text-[8px] font-bold flex items-center justify-center"
                        style={{ background: "#FF4444", color: "#fff" }}
                        data-testid="cfo-alert-badge"
                      >
                        {cfoAlertCount > 9 ? "9+" : cfoAlertCount}
                      </span>
                    )}
                    {/* BUILD 23: Badge ámbar para backlog pendientes */}
                    {mod.path === "/backlog" && backlogCount > 0 && (
                      <span
                        className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full text-[8px] font-bold flex items-center justify-center"
                        style={{ background: "#d97706", color: "#fff" }}
                        data-testid="backlog-badge"
                      >
                        {backlogCount > 9 ? "9+" : backlogCount}
                      </span>
                    )}
                  </div>
                  {!collapsed && (
                    <span className="text-[12.5px] font-medium flex-1">{mod.label}</span>
                  )}
                  {!collapsed && mod.badge === "active" && (
                    <span className="w-2 h-2 rounded-full flex-shrink-0 animate-pulse" style={{ background: "#006e2a" }} />
                  )}
                </NavLink>
              );
            });
            return items;
          })()}
        </nav>

        {/* User section — ghost border top */}
        <div
          className={`p-3 ${collapsed ? "flex justify-center" : ""}`}
          style={{ borderTop: "1px solid rgba(28,27,31,0.07)" }}
        >
          {collapsed ? (
            <button
              onClick={logout}
              className="p-1.5 rounded-lg hover:bg-black/[0.04] transition"
              style={{ color: "#49454f" }}
              data-testid="logout-btn"
            >
              <LogOut size={17} />
            </button>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{
                    background: "linear-gradient(135deg, rgba(0,110,42,0.12), rgba(0,104,117,0.12))",
                  }}
                >
                  <span className="text-xs font-bold" style={{ color: "#006e2a" }}>
                    {user?.name?.[0]?.toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold truncate" style={{ color: "#1c1b1f" }}>{user?.name}</div>
                  <div className="text-[10px]" style={{ color: "#006875" }}>
                    {user?.role === "admin" ? "Administrador" : "Usuario"}
                  </div>
                </div>
              </div>
              <button
                onClick={logout}
                className="p-1.5 rounded-lg hover:bg-black/[0.04] transition flex-shrink-0"
                style={{ color: "#49454f" }}
                data-testid="logout-btn"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${collapsed ? "lg:ml-[68px]" : "lg:ml-[240px]"}`}>

        {/* Header — glassmorphism */}
        <header
          className="h-14 flex items-center justify-between px-4 lg:px-5 sticky top-0 z-20"
          style={{
            background: "rgba(252,249,248,0.85)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            boxShadow: "0 1px 0 rgba(28,27,31,0.05)",
          }}
          data-testid="app-header"
        >
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden"
              style={{ color: "#49454f" }}
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <Menu size={20} />
            </button>
            <h1 className="text-sm font-bold font-public-sans" style={{ color: "#1c1b1f" }}>
              {currentModule?.label || "RODDOS Contable IA"}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <AlegraStatusBadge status={connectionStatus} />

            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setShowNotifs(!showNotifs)}
                className="relative p-1.5 rounded-lg transition hover:bg-black/[0.04]"
                style={{ color: "#49454f" }}
                data-testid="notifications-bell"
              >
                <Bell size={17} />
                {notifications.length > 0 && (
                  <span
                    className="absolute -top-0.5 -right-0.5 w-4 h-4 text-[9px] font-bold rounded-full flex items-center justify-center"
                    style={{ background: "#FF4444", color: "#fff" }}
                  >
                    {notifications.length > 9 ? "9+" : notifications.length}
                  </span>
                )}
              </button>
              {showNotifs && (
                <div
                  className="absolute right-0 top-10 w-72 rounded-xl overflow-hidden z-50"
                  style={{
                    background: "rgba(255,255,255,0.92)",
                    backdropFilter: "blur(20px)",
                    WebkitBackdropFilter: "blur(20px)",
                    boxShadow: "0 8px 40px rgba(28,27,31,0.08)",
                  }}
                >
                  <div
                    className="flex items-center justify-between px-4 py-3"
                    style={{ borderBottom: "1px solid rgba(28,27,31,0.06)" }}
                  >
                    <span className="text-xs font-bold" style={{ color: "#1c1b1f" }}>Notificaciones</span>
                    <div className="flex gap-2 items-center">
                      {notifications.length > 0 && (
                        <button
                          onClick={markAllRead}
                          className="text-[10px] hover:underline"
                          style={{ color: "#006875" }}
                        >
                          Marcar leídas
                        </button>
                      )}
                      <button onClick={() => setShowNotifs(false)} style={{ color: "#49454f" }}>
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-xs" style={{ color: "#9e9a97" }}>
                      Sin notificaciones nuevas
                    </div>
                  ) : (
                    <div className="max-h-60 overflow-y-auto">
                      {notifications.map((n, i) => (
                        <div
                          key={i}
                          className="px-4 py-3 hover:bg-black/[0.02] transition"
                          style={{ borderBottom: "1px solid rgba(28,27,31,0.04)" }}
                        >
                          <p className="text-xs font-semibold" style={{ color: "#1c1b1f" }}>{n.event_type}</p>
                          <p className="text-[10px] mt-0.5" style={{ color: "#9e9a97" }}>
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
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center cursor-pointer"
              style={{
                background: "linear-gradient(135deg, rgba(0,110,42,0.15), rgba(0,104,117,0.15))",
              }}
              data-testid="user-avatar"
            >
              <span className="text-[11px] font-black" style={{ color: "#006e2a" }}>
                {user?.name?.[0]?.toUpperCase()}
              </span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main
          className={`flex-1 ${isChatPage ? "overflow-hidden" : "p-4 lg:p-6 overflow-auto animate-fadeInUp"}`}
          style={{ background: "#fcf9f8" }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
