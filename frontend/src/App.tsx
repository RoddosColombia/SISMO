import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { AlegraProvider } from "./contexts/AlegraContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AgentChatPage from "./pages/AgentChatPage";
import CFOEstrategico from "./pages/CFOEstrategico";
import Settings from "./pages/Settings";
import InventarioAuteco from "./pages/InventarioAuteco";
import Impuestos from "./pages/Impuestos";
import Presupuesto from "./pages/Presupuesto";
import Loanbook from "./pages/Loanbook";
import CRMList from "./pages/CRMList";
import CRMCliente from "./pages/CRMCliente";
import CFO from "./pages/CFO";
import Proveedores from "./pages/Proveedores";
import Radar from "./pages/Radar";
import "./App.css";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { token, loading } = useAuth();
  if (loading) return (
    <div className="h-screen flex items-center justify-center bg-[#F8FAFC]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-4 border-[#0F2A5C] border-t-[#C9A84C] rounded-full animate-spin" />
        <span className="text-sm text-slate-500">Cargando RODDOS...</span>
      </div>
    </div>
  );
  return token ? (children as React.ReactElement) : <Navigate to="/login" replace />;
};

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={<ProtectedRoute><Layout /></ProtectedRoute>}
        >
          <Route index element={<Navigate to="/agente-contable" replace />} />
          <Route path="agente-contable" element={<AgentChatPage />} />
          <Route path="cfo-estrategico" element={<CFOEstrategico />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="cfo" element={<CFO />} />
          <Route path="presupuesto" element={<Presupuesto />} />
          <Route path="impuestos" element={<Impuestos />} />
          <Route path="inventario-auteco" element={<InventarioAuteco />} />
          <Route path="loanbook" element={<Loanbook />} />
          <Route path="crm" element={<CRMList />} />
          <Route path="crm/:id" element={<CRMCliente />} />
          <Route path="radar" element={<Radar />} />
          <Route path="configuracion" element={<Settings />} />
          <Route path="proveedores" element={<Proveedores />} />
          {/* Módulos eliminados del menú — redirigen al chat con contexto */}
          <Route path="facturacion-venta" element={<Navigate to="/agente-contable?hint=factura-venta" replace />} />
          <Route path="facturacion-compra" element={<Navigate to="/agente-contable?hint=factura-compra" replace />} />
          <Route path="causacion-ingresos" element={<Navigate to="/agente-contable?hint=causacion" replace />} />
          <Route path="causacion-egresos" element={<Navigate to="/agente-contable?hint=causacion" replace />} />
          <Route path="conciliacion-bancaria" element={<Navigate to="/agente-contable?hint=conciliacion" replace />} />
        </Route>
        <Route path="*" element={<ProtectedRoute><Navigate to="/agente-contable" replace /></ProtectedRoute>} />
      </Routes>
      <Toaster richColors position="top-right" />
    </BrowserRouter>
  );
}

function App() {
  return (
    <AuthProvider>
      <AlegraProvider>
        <AppRoutes />
      </AlegraProvider>
    </AuthProvider>
  );
}

export default App;
