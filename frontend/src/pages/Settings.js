import React, { useState, useEffect } from "react";
import { Save, TestTube2, RefreshCw, Loader2, ToggleLeft, ToggleRight } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import AlegraAccountSelector from "../components/AlegraAccountSelector";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { toast } from "sonner";

const DEFAULT_ACCOUNT_TYPES = [
  { section: "INGRESOS", items: [
    { key: "ingreso_operacional", label: "Ingreso operacional", filterType: "income" },
    { key: "ingreso_no_operacional", label: "Ingreso no operacional", filterType: "income" },
    { key: "iva_generado", label: "IVA generado (por pagar)", allowedCodes: ["24"] },
    { key: "retencion_fuente_recibida", label: "Ret. fuente recibida", allowedCodes: ["135"] },
  ]},
  { section: "EGRESOS", items: [
    { key: "gasto_admin", label: "Gasto de administración", filterType: "expense" },
    { key: "gasto_ventas", label: "Gasto de ventas", filterType: "expense" },
    { key: "costo_venta", label: "Costo de ventas", filterType: "cost" },
    { key: "gasto_financiero", label: "Gasto financiero", filterType: "expense" },
    { key: "iva_descontable", label: "IVA descontable", allowedCodes: ["24"] },
    { key: "retencion_fuente_pasivo", label: "Ret. fuente practicada (pasivo)", allowedCodes: ["23"] },
  ]},
  { section: "BANCOS Y CAJA", items: [
    { key: "banco_principal", label: "Banco / caja principal", allowedCodes: ["11"] },
    { key: "cuenta_cobrar", label: "Cuenta por cobrar principal", allowedCodes: ["13"] },
    { key: "proveedor_principal", label: "Proveedor principal (por pagar)", allowedCodes: ["22"] },
    { key: "nomina_por_pagar", label: "Nómina por pagar", allowedCodes: ["25"] },
  ]},
];

export default function Settings() {
  const { api } = useAuth();
  const { connectionStatus, checkConnection, loadAccounts, setIsDemoMode, setConnectionStatus } = useAlegra();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [isDemoMode, setLocalDemoMode] = useState(true);
  const [testing, setTesting] = useState(false);
  const [savingCreds, setSavingCreds] = useState(false);
  const [accountMap, setAccountMap] = useState({});
  const [savingAccounts, setSavingAccounts] = useState(false);

  // Load current settings
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [credResp, demoResp, accsResp] = await Promise.all([
          api.get("/settings/credentials"),
          api.get("/settings/demo-mode"),
          api.get("/settings/default-accounts"),
        ]);
        setEmail(credResp.data.email || "");
        setLocalDemoMode(demoResp.data.is_demo_mode);
        const map = {};
        for (const item of accsResp.data) {
          map[item.operation_type] = { id: item.account_id, code: item.account_code, name: item.account_name };
        }
        setAccountMap(map);
      } catch (e) {
        console.error("Error loading settings", e);
      }
    };
    loadSettings();
  }, []); // eslint-disable-line

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const resp = await api.post("/alegra/test-connection");
      if (resp.data.status === "connected") {
        toast.success(`Conexión exitosa — Empresa: ${resp.data.company?.name}`);
      } else if (resp.data.status === "demo") {
        toast.info("Modo demo activo — datos simulados");
      } else {
        toast.error(resp.data.message || "Error de conexión");
      }
      checkConnection();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al conectar");
    } finally { setTesting(false); }
  };

  const handleSaveCredentials = async () => {
    setSavingCreds(true);
    try {
      await api.post("/settings/credentials", { email, token });
      toast.success("Credenciales guardadas correctamente");
      handleTestConnection();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al guardar");
    } finally { setSavingCreds(false); }
  };

  const handleToggleDemo = async () => {
    const newVal = !isDemoMode;
    try {
      await api.put("/settings/demo-mode", { is_demo_mode: newVal });
      setLocalDemoMode(newVal);
      setIsDemoMode(newVal);
      setConnectionStatus(newVal ? "demo" : "unknown");
      toast.success(newVal ? "Modo demo activado" : "Modo demo desactivado — se usará la API real de Alegra");
    } catch { toast.error("Error al cambiar modo demo"); }
  };

  const handleAccountChange = (operationType, account) => {
    setAccountMap(prev => ({ ...prev, [operationType]: account }));
  };

  const handleSaveAccounts = async () => {
    setSavingAccounts(true);
    try {
      const accounts = Object.entries(accountMap)
        .filter(([, acc]) => acc)
        .map(([key, acc]) => ({
          operation_type: key, account_id: acc.id,
          account_code: acc.code, account_name: acc.name,
        }));
      await api.post("/settings/default-accounts", { accounts });
      toast.success(`${accounts.length} cuentas predeterminadas guardadas`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error al guardar");
    } finally { setSavingAccounts(false); }
  };

  const handleSyncAccounts = async () => {
    toast.info("Sincronizando cuentas desde Alegra...");
    await loadAccounts();
    toast.success("Cuentas actualizadas");
  };

  const statusColor = connectionStatus === "connected" ? "text-green-600" : connectionStatus === "demo" ? "text-amber-600" : "text-red-600";
  const statusLabel = connectionStatus === "connected" ? "Conectado" : connectionStatus === "demo" ? "Modo Demo" : "Sin conexión";

  return (
    <div className="max-w-4xl space-y-5" data-testid="settings-page">
      <div>
        <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Configuración</h2>
        <p className="text-sm text-slate-500">Gestiona la integración con Alegra y las cuentas predeterminadas</p>
      </div>

      <Tabs defaultValue="alegra">
        <TabsList className="bg-slate-100">
          <TabsTrigger value="alegra" data-testid="tab-alegra">Integración Alegra</TabsTrigger>
          <TabsTrigger value="accounts" data-testid="tab-accounts">Cuentas Predeterminadas</TabsTrigger>
        </TabsList>

        {/* Alegra Connection Tab */}
        <TabsContent value="alegra" className="mt-5 space-y-5">
          {/* Status banner */}
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${connectionStatus === "connected" ? "bg-green-50 border-green-200" : connectionStatus === "demo" ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"}`}>
            <span className={`w-2.5 h-2.5 rounded-full ${connectionStatus === "connected" ? "bg-green-500" : connectionStatus === "demo" ? "bg-amber-400" : "bg-red-500"}`} />
            <span className={`text-sm font-semibold ${statusColor}`}>Estado: {statusLabel}</span>
          </div>

          {/* Demo Mode Toggle */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Modo Demo</h3>
                <p className="text-xs text-slate-500 mt-0.5">Usa datos simulados en lugar de la API real de Alegra</p>
              </div>
              <button onClick={handleToggleDemo} className="flex items-center gap-2 text-sm font-medium" data-testid="demo-mode-toggle">
                {isDemoMode ? (
                  <><ToggleRight size={32} className="text-[#C9A84C]" /><span className="text-amber-600">Activo</span></>
                ) : (
                  <><ToggleLeft size={32} className="text-slate-400" /><span className="text-slate-500">Inactivo</span></>
                )}
              </button>
            </div>
            {isDemoMode && (
              <div className="mt-3 p-3 bg-amber-50 rounded-lg text-xs text-amber-700">
                El modo demo muestra datos de una empresa ficticia. Actívalo para probar la plataforma sin conexión a Alegra.
              </div>
            )}
          </div>

          {/* API Credentials */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 space-y-4">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Credenciales de la API de Alegra</h3>
            <p className="text-xs text-slate-500">Obtén tu token en Alegra → Mi Perfil → Token de API</p>

            <div>
              <Label className="text-sm font-semibold text-slate-700">Email de tu cuenta Alegra</Label>
              <Input
                type="email"
                placeholder="usuario@empresa.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="mt-1.5"
                data-testid="alegra-email-input"
              />
            </div>
            <div>
              <Label className="text-sm font-semibold text-slate-700">Token de API de Alegra</Label>
              <Input
                type="password"
                placeholder="Token de API..."
                value={token}
                onChange={e => setToken(e.target.value)}
                className="mt-1.5"
                data-testid="alegra-token-input"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <Button onClick={handleTestConnection} disabled={testing} variant="outline" className="flex items-center gap-2" data-testid="test-connection-btn">
                {testing ? <Loader2 size={14} className="animate-spin" /> : <TestTube2 size={14} />}
                Probar conexión
              </Button>
              <Button onClick={handleSaveCredentials} disabled={savingCreds} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white flex items-center gap-2" data-testid="save-credentials-btn">
                {savingCreds ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                Guardar credenciales
              </Button>
            </div>
          </div>

          {/* Sync button */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat mb-2">Plan de cuentas</h3>
            <p className="text-xs text-slate-500 mb-3">Actualiza el árbol de cuentas desde Alegra (caché de 30 min)</p>
            <Button onClick={handleSyncAccounts} variant="outline" className="flex items-center gap-2" data-testid="sync-accounts-btn">
              <RefreshCw size={14} /> Sincronizar cuentas desde Alegra
            </Button>
          </div>
        </TabsContent>

        {/* Default Accounts Tab */}
        <TabsContent value="accounts" className="mt-5">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Cuentas Contables Predeterminadas</h3>
                <p className="text-xs text-slate-500 mt-0.5">Estas cuentas se precargan en los formularios. El usuario puede cambiarlas antes de guardar.</p>
              </div>
              <Button onClick={handleSaveAccounts} disabled={savingAccounts} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="save-default-accounts-btn">
                {savingAccounts ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
                Guardar configuración
              </Button>
            </div>

            {DEFAULT_ACCOUNT_TYPES.map(section => (
              <div key={section.section}>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 pb-1 border-b border-slate-100">{section.section}</h4>
                <div className="space-y-3">
                  {section.items.map(item => (
                    <AlegraAccountSelector
                      key={item.key}
                      label={item.label}
                      value={accountMap[item.key] || null}
                      onChange={acc => handleAccountChange(item.key, acc)}
                      filterType={item.filterType || "all"}
                      allowedCodes={item.allowedCodes || null}
                      placeholder="Sin cuenta predeterminada"
                    />
                  ))}
                </div>
              </div>
            ))}

            <div className="p-3 bg-blue-50 rounded-lg text-xs text-blue-700 border border-blue-100">
              <strong>Nota:</strong> Estas cuentas son sugerencias. En cada formulario el usuario puede cambiarlas para esa operación específica.
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
