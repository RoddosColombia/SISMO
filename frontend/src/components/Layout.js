import React, { useState } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, FileText, ShoppingCart, TrendingUp, TrendingDown,
  Building2, Settings, LogOut, ChevronLeft, Menu, Bell, User,
  CreditCard, Receipt, Calculator, Users, Gift, BarChart2, Tag, Target, Bike
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import AIChatWidget from "./AIChatWidget";

const MODULES = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard, group: null },
  { path: "/facturacion-venta", label: "Facturación Venta", icon: FileText, group: "Facturación" },
  { path: "/facturacion-compra", label: "Facturación Compra", icon: ShoppingCart, group: "Facturación" },
  { path: "/registro-cuotas", label: "Registro de Cuotas", icon: CreditCard, group: "Facturación" },
  { path: "/causacion-ingresos", label: "Causación Ingresos", icon: TrendingUp, group: "Causaciones" },
  { path: "/causacion-egresos", label: "Causación Egresos", icon: TrendingDown, group: "Causaciones" },
  { path: "/conciliacion-bancaria", label: "Conciliación Bancaria", icon: Building2, group: "Causaciones" },
  { path: "/inventario-auteco", label: "Inventario Auteco", icon: Bike, group: "Inventario" },
  { path: "/impuestos", label: "Impuestos y Alertas", icon: Receipt, group: "Fiscal" },
  { path: "/retenciones", label: "Retenciones", icon: Calculator, group: "Fiscal" },
  { path: "/nomina", label: "Nómina", icon: Users, group: "RRHH" },
  { path: "/prestaciones", label: "Prestaciones Sociales", icon: Gift, group: "RRHH" },
  { path: "/estado-resultados", label: "Estado de Resultados", icon: BarChart2, group: "Reportes" },
  { path: "/egresos-clasificados", label: "Egresos Clasificados", icon: Tag, group: "Reportes" },
  { path: "/presupuesto", label: "Presupuesto", icon: Target, group: "Reportes" },
  { path: "/configuracion", label: "Configuración", icon: Settings, group: null },
];

function AlegraStatusBadge({ status }) {
  if (status === "demo") return (
    <span className="flex items-center gap-1.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse-dot" />
      Modo Demo
    </span>
  );
  if (status === "connected") return (
    <span className="flex items-center gap-1.5 text-xs font-medium bg-green-50 text-green-700 border border-green-200 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
      Alegra conectado
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 text-xs font-medium bg-red-50 text-red-700 border border-red-200 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      Sin conexión
    </span>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { connectionStatus } = useAlegra();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const currentModule = MODULES.find(m => location.pathname.startsWith(m.path));

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-20 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full bg-[#0F2A5C] text-white flex flex-col z-30
          transition-all duration-300
          ${collapsed ? "w-[70px]" : "w-[260px]"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className={`flex items-center border-b border-[#163A7A] ${collapsed ? "p-4 justify-center" : "p-5 gap-3"}`}>
          {!collapsed && (
            <div>
              <div className="text-base font-bold text-white font-montserrat leading-tight">RODDOS Contable IA</div>
              <div className="text-xs text-slate-400">Powered by Alegra</div>
            </div>
          )}
          {collapsed && <div className="text-lg font-bold text-[#C9A84C]">RC</div>}
        </div>

        {/* Collapse toggle (desktop) */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center w-6 h-6 absolute -right-3 top-16 bg-white border border-slate-200 rounded-full shadow-sm text-slate-500 hover:text-[#0F2A5C]"
          data-testid="sidebar-collapse-btn"
        >
          <ChevronLeft size={12} className={`transition-transform ${collapsed ? "rotate-180" : ""}`} />
        </button>

        {/* Navigation */}
        <nav className="flex-1 py-2 px-2 space-y-0 overflow-y-auto">
          {(() => {
            const groups = [];
            let lastGroup = undefined;
            MODULES.forEach((mod, idx) => {
              if (mod.group !== lastGroup) {
                if (mod.group && !collapsed) {
                  groups.push(<div key={`grp-${mod.group}`} className="px-3 pt-3 pb-1"><span className="text-[9px] uppercase tracking-widest text-slate-500 font-semibold">{mod.group}</span></div>);
                }
                lastGroup = mod.group;
              }
              groups.push(
                <NavLink
                  key={mod.path}
                  to={mod.path}
                  data-testid={`nav-${mod.path.replace("/", "")}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-sm
                    ${isActive
                      ? "bg-[#C9A84C] text-[#0F2A5C] font-semibold shadow-md"
                      : "text-slate-300 hover:text-white hover:bg-white/10"
                    }
                    ${collapsed ? "justify-center" : ""}`
                  }
                >
                  <mod.icon size={17} className="flex-shrink-0" />
                  {!collapsed && <span className="text-[13px]">{mod.label}</span>}
                </NavLink>
              );
            });
            return groups;
          })()}
        </nav>

        {/* User */}
        <div className={`border-t border-[#163A7A] p-3 ${collapsed ? "flex justify-center" : ""}`}>
          {collapsed ? (
            <button onClick={logout} className="text-slate-400 hover:text-white p-1" data-testid="logout-btn">
              <LogOut size={18} />
            </button>
          ) : (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-full bg-[#C9A84C] flex items-center justify-center flex-shrink-0">
                  <User size={14} className="text-[#0F2A5C]" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white truncate">{user?.name}</div>
                  <div className="text-xs text-slate-400">{user?.role === "admin" ? "Administrador" : "Usuario"}</div>
                </div>
              </div>
              <button onClick={logout} className="text-slate-400 hover:text-white p-1 flex-shrink-0" data-testid="logout-btn">
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${collapsed ? "lg:ml-[70px]" : "lg:ml-[260px]"}`}>
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-100 flex items-center justify-between px-4 lg:px-6 sticky top-0 z-20 shadow-sm" data-testid="app-header">
          <div className="flex items-center gap-3">
            <button className="lg:hidden text-slate-500" onClick={() => setMobileOpen(!mobileOpen)}>
              <Menu size={20} />
            </button>
            <h1 className="text-lg font-semibold text-[#0F172A] font-montserrat">
              {currentModule?.label || "RODDOS Contable IA"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <AlegraStatusBadge status={connectionStatus} />
            <button className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-50">
              <Bell size={18} />
            </button>
            <div className="w-8 h-8 rounded-full bg-[#0F2A5C] flex items-center justify-center cursor-pointer" data-testid="user-avatar">
              <span className="text-xs font-bold text-white">{user?.name?.[0]?.toUpperCase()}</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6 overflow-auto animate-fadeInUp">
          <Outlet />
        </main>
      </div>

      <AIChatWidget />
    </div>
  );
}
