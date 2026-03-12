import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { AlegraProvider } from "./contexts/AlegraContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import FacturacionVenta from "./pages/FacturacionVenta";
import FacturacionCompra from "./pages/FacturacionCompra";
import CausacionIngresos from "./pages/CausacionIngresos";
import CausacionEgresos from "./pages/CausacionEgresos";
import ConciliacionBancaria from "./pages/ConciliacionBancaria";
import Settings from "./pages/Settings";
import InventarioAuteco from "./pages/InventarioAuteco";
import RegistroCuotas from "./pages/RegistroCuotas";
import Impuestos from "./pages/Impuestos";
import Retenciones from "./pages/Retenciones";
import Nomina from "./pages/Nomina";
import Prestaciones from "./pages/Prestaciones";
import EstadoResultados from "./pages/EstadoResultados";
import EgresosClasificados from "./pages/EgresosClasificados";
import Presupuesto from "./pages/Presupuesto";
import "./App.css";

const ProtectedRoute = ({ children }) => {
  const { token, loading } = useAuth();
  if (loading) return (
    <div className="h-screen flex items-center justify-center bg-[#F8FAFC]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-4 border-[#0F2A5C] border-t-[#C9A84C] rounded-full animate-spin" />
        <span className="text-sm text-slate-500">Cargando RODDOS...</span>
      </div>
    </div>
  );
  return token ? children : <Navigate to="/login" replace />;
};

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Only public route is /login */}
        <Route path="/login" element={<Login />} />

        {/* All other routes require authentication */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          {/* Facturación */}
          <Route path="facturacion-venta" element={<FacturacionVenta />} />
          <Route path="facturacion-compra" element={<FacturacionCompra />} />
          <Route path="registro-cuotas" element={<RegistroCuotas />} />
          {/* Causaciones */}
          <Route path="causacion-ingresos" element={<CausacionIngresos />} />
          <Route path="causacion-egresos" element={<CausacionEgresos />} />
          <Route path="conciliacion-bancaria" element={<ConciliacionBancaria />} />
          {/* Inventario */}
          <Route path="inventario-auteco" element={<InventarioAuteco />} />
          {/* Fiscal */}
          <Route path="impuestos" element={<Impuestos />} />
          <Route path="retenciones" element={<Retenciones />} />
          {/* RRHH */}
          <Route path="nomina" element={<Nomina />} />
          <Route path="prestaciones" element={<Prestaciones />} />
          {/* Reportes */}
          <Route path="estado-resultados" element={<EstadoResultados />} />
          <Route path="egresos-clasificados" element={<EgresosClasificados />} />
          <Route path="presupuesto" element={<Presupuesto />} />
          {/* Config */}
          <Route path="configuracion" element={<Settings />} />
        </Route>

        {/* Catch-all → require login */}
        <Route path="*" element={<ProtectedRoute><Navigate to="/dashboard" replace /></ProtectedRoute>} />
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
