import React, { useState, useEffect, useCallback } from "react";
import { Save, TestTube2, RefreshCw, Loader2, ToggleLeft, ToggleRight, Shield, Activity, Globe, QrCode, Download, Check, MessageCircle } from "lucide-react";
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
  const { api, user } = useAuth();
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

  const statusColor = connectionStatus === "connected" ? "text-green-600" : connectionStatus === "demo" ? "text-amber-600" : connectionStatus === "token_invalid" ? "text-orange-600" : "text-red-600";
  const statusLabel = connectionStatus === "connected" ? "Conectado" : connectionStatus === "demo" ? "Modo Demo" : connectionStatus === "token_invalid" ? "Token expirado" : "Sin conexión";

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
          {user?.role === "admin" && <TabsTrigger value="security" data-testid="tab-security">Seguridad</TabsTrigger>}
          <TabsTrigger value="audit" data-testid="tab-audit">Auditoría</TabsTrigger>
          <TabsTrigger value="webhooks" data-testid="tab-webhooks">Webhooks</TabsTrigger>
          {user?.role === "admin" && <TabsTrigger value="mercately" data-testid="tab-mercately">Mercately (WhatsApp)</TabsTrigger>}
        </TabsList>

        {/* Alegra Connection Tab */}
        <TabsContent value="alegra" className="mt-5 space-y-5">
          {/* Status banner */}
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
            connectionStatus === "connected" ? "bg-green-50 border-green-200"
            : connectionStatus === "demo" ? "bg-amber-50 border-amber-200"
            : connectionStatus === "token_invalid" ? "bg-orange-50 border-orange-200"
            : "bg-red-50 border-red-200"
          }`}>
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
              connectionStatus === "connected" ? "bg-green-500"
              : connectionStatus === "demo" ? "bg-amber-400"
              : connectionStatus === "token_invalid" ? "bg-orange-400"
              : "bg-red-500"
            }`} />
            <span className={`text-sm font-semibold ${statusColor}`}>Estado: {statusLabel}</span>
            {connectionStatus === "token_invalid" && (
              <a href="https://app.alegra.com/user/profile#token" target="_blank" rel="noreferrer"
                className="ml-auto text-xs font-bold text-orange-600 hover:underline flex items-center gap-1">
                Generar nuevo token en Alegra →
              </a>
            )}
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
            <p className="text-xs text-slate-500">Obtén o renueva tu token en <a href="https://app.alegra.com/user/profile#token" target="_blank" rel="noreferrer" className="text-[#0F2A5C] underline">Alegra → Mi Perfil → API</a>. Después de cambiar de plan, genera un nuevo token.</p>

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

        {/* SECURITY TAB */}
        <SecurityTab api={api} user={user} />

        {/* AUDIT TAB */}
        <AuditTab api={api} />

        {/* WEBHOOKS TAB */}
        <WebhooksTab api={api} />

        {/* MERCATELY TAB */}
        {user?.role === "admin" && <MercatelyTab api={api} />}
      </Tabs>
    </div>
  );
}


// ─── SECURITY TAB ─────────────────────────────────────────────────────────────

function SecurityTab({ api, user }) {
  const [status2fa, setStatus2fa] = useState(null);
  const [qr, setQr] = useState(null);
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [loadingSetup, setLoadingSetup] = useState(false);
  const [loadingEnable, setLoadingEnable] = useState(false);

  useEffect(() => {
    api.get("/auth/2fa/status").then(res => setStatus2fa(res.data.totp_enabled)).catch(() => {});
  }, [api]);

  const handleSetup = async () => {
    setLoadingSetup(true);
    try {
      const res = await api.post("/auth/2fa/setup");
      setQr(res.data.qr_code);
      setSecret(res.data.secret);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error generando QR");
    } finally { setLoadingSetup(false); }
  };

  const handleEnable = async () => {
    setLoadingEnable(true);
    try {
      await api.post("/auth/2fa/enable", { code, secret });
      toast.success("2FA activado — Tu cuenta está protegida");
      setStatus2fa(true);
      setQr(null); setCode(""); setSecret("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Código incorrecto");
      setCode("");
    } finally { setLoadingEnable(false); }
  };

  const handleDisable = async () => {
    if (!window.confirm("¿Desactivar 2FA? Tu cuenta quedará menos protegida.")) return;
    try {
      await api.post("/auth/2fa/disable");
      toast.success("2FA desactivado");
      setStatus2fa(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error");
    }
  };

  return (
    <TabsContent value="security" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-lg">
        <h3 className="text-base font-bold text-[#0F2A5C] mb-1 flex items-center gap-2">
          <Shield size={16} className="text-[#C9A84C]" /> Autenticación de Dos Factores (2FA)
        </h3>
        <p className="text-sm text-slate-500 mb-4">Compatible con Google Authenticator y Authy</p>

        {status2fa === true && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Check size={16} className="text-emerald-600" />
              <span className="text-sm font-semibold text-emerald-700">2FA activo</span>
            </div>
            <button onClick={handleDisable} className="text-xs text-red-500 hover:text-red-700 border border-red-200 px-3 py-1 rounded-lg hover:bg-red-50">
              Desactivar
            </button>
          </div>
        )}

        {status2fa === false && !qr && (
          <button onClick={handleSetup} disabled={loadingSetup}
            className="flex items-center gap-2 bg-[#0F2A5C] text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[#163A7A] disabled:opacity-50"
            data-testid="setup-2fa-btn">
            {loadingSetup ? <Loader2 size={14} className="animate-spin" /> : <QrCode size={14} />}
            Activar 2FA — Mostrar QR
          </button>
        )}

        {qr && (
          <div className="space-y-4">
            <div className="bg-[#F0F4FF] rounded-xl p-4 text-center">
              <p className="text-xs text-slate-600 mb-3">Escanea este código con Google Authenticator:</p>
              <img src={qr} alt="QR 2FA" className="w-44 h-44 mx-auto rounded-lg border-4 border-white shadow" />
              <p className="text-[10px] text-slate-400 mt-2 font-mono break-all">{secret}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1 block">Ingresa el código de 6 dígitos para confirmar</label>
              <input type="text" inputMode="numeric" maxLength={6} value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="w-full border rounded-lg px-3 py-2 text-center text-xl font-mono tracking-widest focus:border-[#C9A84C] outline-none"
                placeholder="000000" data-testid="setup-2fa-code-input" />
            </div>
            <button onClick={handleEnable} disabled={loadingEnable || code.length !== 6}
              className="w-full bg-[#C9A84C] text-[#0F2A5C] font-bold py-2.5 rounded-xl text-sm hover:bg-[#b8903e] disabled:opacity-50"
              data-testid="enable-2fa-btn">
              {loadingEnable ? "Activando..." : "Confirmar y Activar 2FA"}
            </button>
          </div>
        )}
      </div>
    </TabsContent>
  );
}


// ─── AUDIT TAB ────────────────────────────────────────────────────────────────

function AuditTab({ api }) {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ user_email: "", date_start: "", date_end: "", only_errors: false, page: 1 });

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/audit-logs", { params: { ...filters, limit: 50 } });
      setLogs(res.data.logs || []);
      setTotal(res.data.total || 0);
    } catch { toast.error("Error cargando auditoría"); }
    finally { setLoading(false); }
  }, [api, filters]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const exportCSV = () => {
    const cols = ["Fecha", "Usuario", "Método", "Endpoint", "Estado"];
    const rows = logs.map(l => [l.timestamp?.slice(0, 19), l.user_email, l.method, l.endpoint, l.response_status]);
    const csv = [cols, ...rows].map(r => r.join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <TabsContent value="audit" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
            <Activity size={15} className="text-[#C9A84C]" /> Registro de Auditoría ({total} entradas)
          </span>
          <button onClick={exportCSV} className="flex items-center gap-1 text-xs border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50">
            <Download size={12} /> Exportar CSV
          </button>
        </div>

        {/* Filters */}
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap gap-3 items-end bg-slate-50">
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Usuario</label>
            <input className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none w-40"
              value={filters.user_email} onChange={e => setFilters(f => ({ ...f, user_email: e.target.value, page: 1 }))} placeholder="email..." />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Desde</label>
            <input type="date" className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none"
              value={filters.date_start} onChange={e => setFilters(f => ({ ...f, date_start: e.target.value, page: 1 }))} />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Hasta</label>
            <input type="date" className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none"
              value={filters.date_end} onChange={e => setFilters(f => ({ ...f, date_end: e.target.value, page: 1 }))} />
          </div>
          <label className="flex items-center gap-1.5 text-xs cursor-pointer">
            <input type="checkbox" checked={filters.only_errors}
              onChange={e => setFilters(f => ({ ...f, only_errors: e.target.checked, page: 1 }))} />
            Solo errores
          </label>
          <button onClick={loadLogs} disabled={loading}
            className="flex items-center gap-1 text-xs bg-[#0F2A5C] text-white px-3 py-1.5 rounded-lg hover:bg-[#163A7A] disabled:opacity-50">
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} /> Filtrar
          </button>
        </div>

        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-xs">
            <thead><tr className="bg-[#0F2A5C] text-white text-[10px] uppercase sticky top-0">
              <th className="px-3 py-2.5 text-left">Fecha / Hora</th>
              <th className="px-3 py-2.5 text-left">Usuario</th>
              <th className="px-3 py-2.5 text-left">Método</th>
              <th className="px-3 py-2.5 text-left">Endpoint</th>
              <th className="px-3 py-2.5 text-center">Estado</th>
            </tr></thead>
            <tbody>
              {logs.map((log, i) => (
                <tr key={i} className={`border-b border-slate-50 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/40"} ${(log.response_status || 0) >= 400 ? "bg-red-50" : ""}`}>
                  <td className="px-3 py-2 font-mono text-[11px]">{log.timestamp?.slice(0, 19).replace("T", " ")}</td>
                  <td className="px-3 py-2">{log.user_email}</td>
                  <td className="px-3 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${log.method === "GET" ? "bg-blue-100 text-blue-700" : log.method === "POST" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                      {log.method}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-600 max-w-[200px] truncate">{log.endpoint}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`text-[10px] font-bold ${(log.response_status || 200) < 400 ? "text-emerald-600" : "text-red-600"}`}>
                      {log.response_status || 200}
                    </span>
                  </td>
                </tr>
              ))}
              {logs.length === 0 && !loading && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Sin registros con los filtros actuales</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 py-3 flex items-center justify-between border-t border-slate-100 bg-slate-50">
          <span className="text-xs text-slate-500">Página {filters.page} — {logs.length} de {total}</span>
          <div className="flex gap-2">
            <button disabled={filters.page <= 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
              className="text-xs px-3 py-1 border rounded hover:bg-white disabled:opacity-40">Anterior</button>
            <button disabled={logs.length < 50} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
              className="text-xs px-3 py-1 border rounded hover:bg-white disabled:opacity-40">Siguiente</button>
          </div>
        </div>
      </div>
    </TabsContent>
  );
}


// ─── MERCATELY TAB ────────────────────────────────────────────────────────────

function MercatelyTab({ api }) {
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/settings/mercately")
      .then(res => setStatus(res.data))
      .catch(() => {});
  }, [api]);

  const handleSave = async () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      toast.error("Ingresa la API Key y el API Secret de Mercately");
      return;
    }
    setSaving(true);
    try {
      await api.post("/settings/mercately", { api_key: apiKey, api_secret: apiSecret });
      toast.success("Credenciales Mercately guardadas correctamente");
      setStatus({ has_credentials: true, api_key_masked: "*".repeat(8) + apiKey.slice(-4), configured_at: new Date().toISOString() });
      setApiKey("");
      setApiSecret("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error guardando credenciales");
    } finally { setSaving(false); }
  };

  return (
    <TabsContent value="mercately" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-lg space-y-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
            <MessageCircle size={18} className="text-green-600" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#0F2A5C]">Mercately — WhatsApp Business API</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Conecta con Mercately para enviar notificaciones automáticas de cobro por WhatsApp a los clientes en mora.
            </p>
          </div>
        </div>

        {status?.has_credentials ? (
          <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
            <Check size={15} className="text-emerald-600 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-emerald-700">Credenciales configuradas</p>
              <p className="text-[11px] text-slate-500 font-mono">API Key: {status.api_key_masked}</p>
              {status.configured_at && (
                <p className="text-[10px] text-slate-400">Actualizado: {status.configured_at.slice(0, 10)}</p>
              )}
            </div>
          </div>
        ) : (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
            No hay credenciales configuradas. Ingresa las credenciales de tu cuenta Mercately para habilitar notificaciones WhatsApp.
          </div>
        )}

        <div className="bg-[#F8FAFF] rounded-xl p-4 text-xs space-y-1.5 border border-slate-100">
          <p className="font-semibold text-[#0F2A5C] mb-2">¿Cómo obtener las credenciales?</p>
          <p className="text-slate-600">1. Accede a <a href="https://app.mercately.com" target="_blank" rel="noreferrer" className="text-[#0F2A5C] underline font-medium">app.mercately.com</a></p>
          <p className="text-slate-600">2. Ve a Configuración → API Keys</p>
          <p className="text-slate-600">3. Copia tu API Key y API Secret</p>
        </div>

        <div className="space-y-4">
          <div>
            <Label className="text-sm font-semibold text-slate-700">API Key de Mercately</Label>
            <Input
              type="password"
              placeholder="mercately_api_key_..."
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              className="mt-1.5"
              data-testid="mercately-api-key-input"
            />
          </div>
          <div>
            <Label className="text-sm font-semibold text-slate-700">API Secret de Mercately</Label>
            <Input
              type="password"
              placeholder="mercately_api_secret_..."
              value={apiSecret}
              onChange={e => setApiSecret(e.target.value)}
              className="mt-1.5"
              data-testid="mercately-api-secret-input"
            />
          </div>
          <Button
            onClick={handleSave}
            disabled={saving || !apiKey.trim() || !apiSecret.trim()}
            className="w-full bg-green-600 hover:bg-green-700 text-white flex items-center justify-center gap-2"
            data-testid="save-mercately-btn"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Guardar credenciales Mercately
          </Button>
        </div>

        <div className="bg-slate-50 rounded-xl p-3 text-[11px] text-slate-500 border border-slate-100">
          <strong className="text-slate-600">Estado de integración:</strong> Las notificaciones automáticas de WhatsApp estarán disponibles en el módulo Cartera una vez configuradas las credenciales.
        </div>
      </div>
    </TabsContent>
  );
}


// ─── WEBHOOKS TAB ─────────────────────────────────────────────────────────────

function WebhooksTab({ api }) {
  const [webhookStatus, setWebhookStatus] = useState(null);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    api.get("/settings/webhooks/status").then(res => setWebhookStatus(res.data)).catch(() => {});
  }, [api]);

  const handleRegister = async () => {
    setRegistering(true);
    try {
      const res = await api.post("/settings/webhooks/register");
      toast.success("Webhook registrado en Alegra");
      setWebhookStatus({ webhook_id: res.data.webhook_id, url: res.data.url, registered_at: new Date().toISOString() });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error registrando webhook");
    } finally { setRegistering(false); }
  };

  return (
    <TabsContent value="webhooks" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-lg space-y-4">
        <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
          <Globe size={16} className="text-[#C9A84C]" /> Webhooks de Alegra
        </h3>
        <p className="text-sm text-slate-500">
          Registra RODDOS como receptor de eventos en Alegra para recibir notificaciones en tiempo real cuando se creen facturas o pagos.
        </p>

        <div className="bg-[#F0F4FF] rounded-xl p-4 space-y-2 text-xs">
          <p className="font-semibold text-[#0F2A5C]">Eventos suscritos:</p>
          {["invoice.created", "invoice.voided", "bill.created", "payment.created"].map(e => (
            <div key={e} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#C9A84C]" />
              <span className="text-slate-600">{e}</span>
            </div>
          ))}
        </div>

        {webhookStatus?.webhook_id ? (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-1">
            <div className="flex items-center gap-2">
              <Check size={14} className="text-emerald-600" />
              <span className="text-sm font-semibold text-emerald-700">Webhook registrado</span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono break-all">{webhookStatus.url}</p>
            <p className="text-[10px] text-slate-400">ID: {webhookStatus.webhook_id} — {webhookStatus.registered_at?.slice(0, 10)}</p>
          </div>
        ) : (
          <button onClick={handleRegister} disabled={registering}
            className="flex items-center gap-2 bg-[#0F2A5C] text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[#163A7A] disabled:opacity-50"
            data-testid="register-webhook-btn">
            {registering ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
            Registrar Webhook en Alegra
          </button>
        )}

        <p className="text-[10px] text-slate-400">
          * Requiere que las credenciales de Alegra estén configuradas y el modo demo esté desactivado.
        </p>
      </div>
    </TabsContent>
  );
}
