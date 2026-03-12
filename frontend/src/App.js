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
import "./App.css";

const ProtectedRoute = ({ children }) => {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" replace />;
};

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
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
          <Route path="facturacion-venta" element={<FacturacionVenta />} />
          <Route path="facturacion-compra" element={<FacturacionCompra />} />
          <Route path="causacion-ingresos" element={<CausacionIngresos />} />
          <Route path="causacion-egresos" element={<CausacionEgresos />} />
          <Route path="conciliacion-bancaria" element={<ConciliacionBancaria />} />
          <Route path="configuracion" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
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
