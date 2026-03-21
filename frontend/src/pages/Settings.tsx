import React, { useState, useEffect, useCallback } from "react";
import {
  Save, TestTube2, RefreshCw, Loader2, ToggleLeft, ToggleRight,
  Shield, Activity, Globe, QrCode, Download, Check, MessageCircle,
  Plus, Pencil, X, Bike, Zap, AlertTriangle,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import AlegraAccountSelector from "../components/AlegraAccountSelector";
import { useAuth } from "../contexts/AuthContext";
import { useAlegra } from "../contexts/AlegraContext";
import { toast } from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PlanConfig {
  semanas: number;
  cuota: number;
}

interface CatalogoMoto {
  id: string;
  modelo: string;
  marca: string;
  costo: number;
  pvp: number;
  cuota_inicial: number;
  matricula: number;
  planes: {
    P39S: PlanConfig;
    P52S: PlanConfig;
    P78S: PlanConfig;
  };
  activo: boolean;
  actualizado_en?: string;
  actualizado_por?: string;
}

interface AccountMapEntry {
  id: string | number;
  code?: string;
  name?: string;
}

interface AuditFilters {
  user_email: string;
  date_start: string;
  date_end: string;
  only_errors: boolean;
  page: number;
}

interface AuditLog {
  timestamp?: string;
  user_email?: string;
  method?: string;
  endpoint?: string;
  response_status?: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

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

const fmt = (n: number) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Settings() {
  const { api, user } = useAuth();
  const { connectionStatus, checkConnection, loadAccounts, setIsDemoMode, setConnectionStatus } = useAlegra() as any;
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [isDemoMode, setLocalDemoMode] = useState(true);
  const [testing, setTesting] = useState(false);
  const [savingCreds, setSavingCreds] = useState(false);
  const [accountMap, setAccountMap] = useState<Record<string, AccountMapEntry | null>>({});
  const [savingAccounts, setSavingAccounts] = useState(false);

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
        const map: Record<string, AccountMapEntry> = {};
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
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Error al conectar");
    } finally { setTesting(false); }
  };

  const handleSaveCredentials = async () => {
    setSavingCreds(true);
    try {
      await api.post("/settings/credentials", { email, token });
      toast.success("Credenciales guardadas correctamente");
      handleTestConnection();
    } catch (e: any) {
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

  const handleAccountChange = (operationType: string, account: AccountMapEntry | null) => {
    setAccountMap(prev => ({ ...prev, [operationType]: account }));
  };

  const handleSaveAccounts = async () => {
    setSavingAccounts(true);
    try {
      const accounts = Object.entries(accountMap)
        .filter(([, acc]) => acc)
        .map(([key, acc]) => ({
          operation_type: key, account_id: acc!.id,
          account_code: acc!.code, account_name: acc!.name,
        }));
      await api.post("/settings/default-accounts", { accounts });
      toast.success(`${accounts.length} cuentas predeterminadas guardadas`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Error al guardar");
    } finally { setSavingAccounts(false); }
  };

  const handleSyncAccounts = async () => {
    toast.info("Sincronizando cuentas desde Alegra...");
    await loadAccounts();
    toast.success("Cuentas actualizadas");
  };

  const statusColor = connectionStatus === "connected" ? "text-green-600"
    : connectionStatus === "demo" ? "text-amber-600"
    : connectionStatus === "token_invalid" ? "text-orange-600"
    : "text-red-600";
  const statusLabel = connectionStatus === "connected" ? "Conectado"
    : connectionStatus === "demo" ? "Modo Demo"
    : connectionStatus === "token_invalid" ? "Token expirado"
    : "Sin conexión";

  return (
    <div className="max-w-5xl space-y-5" data-testid="settings-page">
      <div>
        <h2 className="text-xl font-bold text-[#0F172A] font-montserrat">Configuración</h2>
        <p className="text-sm text-slate-500">Gestiona la integración con Alegra, el catálogo de motos y las cuentas predeterminadas</p>
      </div>

      <Tabs defaultValue="alegra">
        <TabsList className="bg-slate-100 flex-wrap h-auto gap-1">
          <TabsTrigger value="alegra" data-testid="tab-alegra">Integración Alegra</TabsTrigger>
          <TabsTrigger value="catalogo" data-testid="tab-catalogo">Catálogo de Motos</TabsTrigger>
          <TabsTrigger value="accounts" data-testid="tab-accounts">Cuentas Predeterminadas</TabsTrigger>
          {user?.role === "admin" && <TabsTrigger value="security" data-testid="tab-security">Seguridad</TabsTrigger>}
          {user?.role === "admin" && <TabsTrigger value="audit" data-testid="tab-audit">Auditoría</TabsTrigger>}
          <TabsTrigger value="webhooks" data-testid="tab-webhooks">Webhooks</TabsTrigger>
          {user?.role === "admin" && <TabsTrigger value="mercately" data-testid="tab-mercately">Mercately (WhatsApp)</TabsTrigger>}
          <TabsTrigger value="dian" data-testid="tab-dian">DIAN</TabsTrigger>
          <TabsTrigger value="cfo" data-testid="tab-cfo">Agente CFO</TabsTrigger>
          <TabsTrigger value="scheduler" data-testid="tab-scheduler">Alertas Scheduler</TabsTrigger>
        </TabsList>

        {/* Alegra Connection Tab */}
        <TabsContent value="alegra" className="mt-5 space-y-5">
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

          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Modo Demo</h3>
                <p className="text-xs text-slate-500 mt-0.5">Usa datos simulados en lugar de la API real de Alegra</p>
              </div>
              <button onClick={handleToggleDemo} className="flex items-center gap-2 text-sm font-medium" data-testid="demo-mode-toggle">
                {isDemoMode
                  ? <><ToggleRight size={32} className="text-[#C9A84C]" /><span className="text-amber-600">Activo</span></>
                  : <><ToggleLeft size={32} className="text-slate-400" /><span className="text-slate-500">Inactivo</span></>}
              </button>
            </div>
            {isDemoMode && (
              <div className="mt-3 p-3 bg-amber-50 rounded-lg text-xs text-amber-700">
                El modo demo muestra datos de una empresa ficticia. Actívalo para probar la plataforma sin conexión a Alegra.
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 space-y-4">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Credenciales de la API de Alegra</h3>
            <p className="text-xs text-slate-500">
              Obtén o renueva tu token en{" "}
              <a href="https://app.alegra.com/user/profile#token" target="_blank" rel="noreferrer" className="text-[#0F2A5C] underline">
                Alegra → Mi Perfil → API
              </a>.
            </p>
            <div>
              <Label className="text-sm font-semibold text-slate-700">Email de tu cuenta Alegra</Label>
              <Input type="email" placeholder="usuario@empresa.com" value={email}
                onChange={e => setEmail(e.target.value)} className="mt-1.5" data-testid="alegra-email-input" />
            </div>
            <div>
              <Label className="text-sm font-semibold text-slate-700">Token de API de Alegra</Label>
              <Input type="password" placeholder="Token de API..." value={token}
                onChange={e => setToken(e.target.value)} className="mt-1.5" data-testid="alegra-token-input" />
            </div>
            <div className="flex gap-3 pt-2">
              <Button onClick={handleTestConnection} disabled={testing} variant="outline" className="flex items-center gap-2" data-testid="test-connection-btn">
                {testing ? <Loader2 size={14} className="animate-spin" /> : <TestTube2 size={14} />}
                Probar conexión
              </Button>
              <Button onClick={handleSaveCredentials} disabled={savingCreds}
                className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white flex items-center gap-2" data-testid="save-credentials-btn">
                {savingCreds ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                Guardar credenciales
              </Button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat mb-2">Plan de cuentas</h3>
            <p className="text-xs text-slate-500 mb-3">Actualiza el árbol de cuentas desde Alegra (caché de 30 min)</p>
            <Button onClick={handleSyncAccounts} variant="outline" className="flex items-center gap-2" data-testid="sync-accounts-btn">
              <RefreshCw size={14} /> Sincronizar cuentas desde Alegra
            </Button>
          </div>
        </TabsContent>

        {/* Catálogo de Motos Tab */}
        <CatalogoTab api={api} />

        {/* Default Accounts Tab */}
        <TabsContent value="accounts" className="mt-5">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0F2A5C] font-montserrat">Cuentas Contables Predeterminadas</h3>
                <p className="text-xs text-slate-500 mt-0.5">Estas cuentas se precargan en los formularios.</p>
              </div>
              <Button onClick={handleSaveAccounts} disabled={savingAccounts}
                className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white" data-testid="save-default-accounts-btn">
                {savingAccounts ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
                Guardar configuración
              </Button>
            </div>
            {DEFAULT_ACCOUNT_TYPES.map(section => (
              <div key={section.section}>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 pb-1 border-b border-slate-100">
                  {section.section}
                </h4>
                <div className="space-y-3">
                  {section.items.map(item => (
                    <AlegraAccountSelector key={item.key} label={item.label}
                      value={(accountMap[item.key] as any) || null}
                      onChange={(acc: any) => handleAccountChange(item.key, acc)}
                      filterType={item.filterType || "all"}
                      allowedCodes={item.allowedCodes || null}
                      placeholder="Sin cuenta predeterminada" />
                  ))}
                </div>
              </div>
            ))}
            <div className="p-3 bg-blue-50 rounded-lg text-xs text-blue-700 border border-blue-100">
              <strong>Nota:</strong> Estas cuentas son sugerencias. En cada formulario el usuario puede cambiarlas.
            </div>
          </div>
        </TabsContent>

        <SecurityTab api={api} user={user} />
        <AuditTab api={api} />
        <WebhooksTab api={api} />
        <CfoTab api={api} />
        {user?.role === "admin" && <MercatelyTab api={api} />}
        <DianTab api={api} />
        <TabsContent value="scheduler" className="mt-5">
          <SchedulerTab api={api} />
        </TabsContent>

      </Tabs>
    </div>
  );
}


// ─── CFO CONFIG TAB ──────────────────────────────────────────────────────────

function CfoTab({ api }: { api: any }) {
  const [cfg, setCfg] = useState({
    dia_informe:     1,
    umbral_mora_pct: 5,
    umbral_caja_cop: 5_000_000,
    whatsapp_activo: false,
    whatsapp_ceo:    "",
  });
  const [saving, setSaving]       = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    api.get("/cfo/config").then((r: any) => setCfg((prev) => ({ ...prev, ...r.data }))).catch(() => {});
  }, [api]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post("/cfo/config", cfg);
      toast.success("Configuración CFO guardada");
    } catch { toast.error("Error guardando configuración"); }
    finally { setSaving(false); }
  };

  const handleGenerar = async () => {
    setGenerating(true);
    try {
      await api.post("/cfo/generar");
      toast.success("Informe CFO generado — ve a la página CFO para verlo");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Error generando informe");
    } finally { setGenerating(false); }
  };

  return (
    <TabsContent value="cfo" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-lg space-y-5">
        <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
          <Zap size={16} className="text-[#C9A84C]" /> Configuración Agente CFO
        </h3>

        <div className="space-y-4">
          <div>
            <Label className="text-sm font-medium text-slate-700">Día del mes para informe automático</Label>
            <Input
              type="number" min={1} max={28}
              value={cfg.dia_informe}
              onChange={(e: any) => setCfg((p) => ({ ...p, dia_informe: Number(e.target.value) }))}
              className="mt-1.5 w-28"
              data-testid="cfo-dia-informe"
            />
            <p className="text-xs text-slate-400 mt-1">Se genera automáticamente ese día a las 08:00 AM (Bogotá)</p>
          </div>

          <div>
            <Label className="text-sm font-medium text-slate-700">Umbral alerta mora (%)</Label>
            <Input
              type="number" min={0} max={100} step={0.5}
              value={cfg.umbral_mora_pct}
              onChange={(e: any) => setCfg((p) => ({ ...p, umbral_mora_pct: Number(e.target.value) }))}
              className="mt-1.5 w-28"
              data-testid="cfo-umbral-mora"
            />
          </div>

          <div>
            <Label className="text-sm font-medium text-slate-700">Umbral alerta caja (COP)</Label>
            <Input
              type="number" min={0} step={1_000_000}
              value={cfg.umbral_caja_cop}
              onChange={(e: any) => setCfg((p) => ({ ...p, umbral_caja_cop: Number(e.target.value) }))}
              className="mt-1.5 w-44"
              data-testid="cfo-umbral-caja"
            />
          </div>

          <div>
            <Label className="text-sm font-medium text-slate-700">Enviar informe por WhatsApp al CEO</Label>
            <button
              onClick={() => setCfg((p) => ({ ...p, whatsapp_activo: !p.whatsapp_activo }))}
              data-testid="cfo-whatsapp-toggle"
              className="mt-1.5 block"
            >
              {cfg.whatsapp_activo
                ? <ToggleRight size={32} className="text-[#00C853]" />
                : <ToggleLeft  size={32} className="text-slate-400" />}
            </button>
          </div>

          {cfg.whatsapp_activo && (
            <div>
              <Label className="text-sm font-medium text-slate-700">Número WhatsApp CEO</Label>
              <Input
                type="tel"
                placeholder="+573001234567"
                value={cfg.whatsapp_ceo}
                onChange={(e: any) => setCfg((p) => ({ ...p, whatsapp_ceo: e.target.value }))}
                className="mt-1.5"
                data-testid="cfo-whatsapp-ceo"
              />
            </div>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <Button onClick={handleSave} disabled={saving} data-testid="cfo-save-btn"
            className="bg-[#0F2A5C] hover:bg-[#1a3d7a] text-white">
            {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
            Guardar
          </Button>
          <Button onClick={handleGenerar} disabled={generating} variant="outline" data-testid="cfo-generar-btn">
            {generating ? <Loader2 size={14} className="animate-spin mr-1" /> : <Zap size={14} className="mr-1" />}
            Generar Informe Ahora
          </Button>
        </div>
      </div>
    </TabsContent>
  );
}


const EMPTY_MOTO: Partial<CatalogoMoto> = {
  modelo: "", marca: "Auteco", costo: 0, pvp: 0,
  cuota_inicial: 0, matricula: 660000, activo: true,
  planes: { P39S: { semanas: 39, cuota: 0 }, P52S: { semanas: 52, cuota: 0 }, P78S: { semanas: 78, cuota: 0 } },
};

function CatalogoTab({ api }: { api: any }) {
  const [items, setItems] = useState<CatalogoMoto[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editRow, setEditRow] = useState<Partial<CatalogoMoto>>({});
  const [saving, setSaving] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [newMoto, setNewMoto] = useState<Partial<CatalogoMoto>>({ ...EMPTY_MOTO });

  const [showInactive, setShowInactive] = useState(false);

  const loadCatalogo = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/settings/catalogo?include_inactive=${showInactive}`);
      setItems(res.data);
    } catch { toast.error("Error cargando catálogo de motos"); }
    finally { setLoading(false); }
  }, [api, showInactive]);

  useEffect(() => { loadCatalogo(); }, [loadCatalogo]);

  const startEdit = (item: CatalogoMoto) => {
    setEditingId(item.id);
    setEditRow({ ...item, planes: { ...item.planes } });
  };

  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const setEditField = (field: keyof CatalogoMoto, val: any) =>
    setEditRow(r => ({ ...r, [field]: val }));

  const setEditPlan = (plan: "P39S" | "P52S" | "P78S", cuota: number) =>
    setEditRow(r => ({ ...r, planes: { ...(r.planes as any), [plan]: { ...(r.planes as any)?.[plan], cuota } } }));

  const saveRow = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      await api.put(`/settings/catalogo/${editingId}`, editRow);
      toast.success("Cambios guardados");
      cancelEdit();
      await loadCatalogo();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Error guardando cambios");
    } finally { setSaving(false); }
  };

  const toggleActivo = async (item: CatalogoMoto) => {
    try {
      await api.put(`/settings/catalogo/${item.id}`, { activo: !item.activo });
      toast.success(item.activo ? `"${item.modelo}" desactivado` : `"${item.modelo}" activado`);
      await loadCatalogo();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Error"); }
  };

  const createMoto = async () => {
    if (!newMoto.modelo?.trim()) { toast.error("El nombre del modelo es obligatorio"); return; }
    if (!newMoto.pvp || newMoto.pvp <= 0) { toast.error("El PVP debe ser mayor a 0"); return; }
    try {
      await api.post("/settings/catalogo", newMoto);
      toast.success(`Modelo "${newMoto.modelo}" agregado al catálogo`);
      setShowModal(false);
      setNewMoto({ ...EMPTY_MOTO });
      await loadCatalogo();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Error creando modelo"); }
  };

  const setNewField = (field: keyof CatalogoMoto, val: any) =>
    setNewMoto(r => ({ ...r, [field]: val }));

  const setNewPlan = (plan: "P39S" | "P52S" | "P78S", cuota: number) =>
    setNewMoto(r => ({ ...r, planes: { ...(r.planes as any), [plan]: { ...(r.planes as any)?.[plan], cuota } } }));

  return (
    <TabsContent value="catalogo" className="mt-5">
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bike size={16} className="text-[#C9A84C]" />
            <span className="text-sm font-bold text-[#0F2A5C]">Catálogo de Motos Auteco</span>
            <span className="text-xs text-slate-400 ml-1">({items.length} modelo{items.length !== 1 ? "s" : ""}{showInactive ? "" : " activos"})</span>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
              <input type="checkbox" checked={showInactive} onChange={e => setShowInactive(e.target.checked)}
                className="rounded" data-testid="toggle-inactive-filter" />
              Ver inactivos
            </label>
            <Button onClick={() => setShowModal(true)}
              className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white h-8 text-xs gap-1.5"
              data-testid="add-modelo-btn">
              <Plus size={13} /> Agregar Modelo
            </Button>
          </div>
        </div>

        {/* Warning */}
        <div className="px-5 py-2.5 bg-amber-50 border-b border-amber-100 text-xs text-amber-700">
          Los cambios de precio aplican <strong>solo a ventas nuevas</strong>. Los loanbooks existentes no se modifican.
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2 text-slate-400">
            <Loader2 size={16} className="animate-spin" /> Cargando catálogo...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="catalogo-table">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left font-semibold">Modelo</th>
                  <th className="px-4 py-3 text-right font-semibold">Costo</th>
                  <th className="px-4 py-3 text-right font-semibold">PVP</th>
                  <th className="px-4 py-3 text-right font-semibold">CI</th>
                  <th className="px-4 py-3 text-right font-semibold">Matrícula</th>
                  <th className="px-4 py-3 text-right font-semibold">P39S</th>
                  <th className="px-4 py-3 text-right font-semibold">P52S</th>
                  <th className="px-4 py-3 text-right font-semibold">P78S</th>
                  <th className="px-4 py-3 text-center font-semibold">Activo</th>
                  <th className="px-4 py-3 text-center font-semibold">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const isEditing = editingId === item.id;
                  const row = isEditing ? editRow : item;
                  return (
                    <tr key={item.id}
                      className={`border-t border-slate-50 transition-colors ${isEditing ? "bg-blue-50/40" : "hover:bg-slate-50/60"} ${!item.activo ? "opacity-50" : ""}`}
                      data-testid={`catalogo-row-${item.id}`}>
                      {/* Modelo */}
                      <td className="px-4 py-3 font-medium text-[#0F2A5C]">
                        {isEditing
                          ? <Input value={row.modelo || ""} onChange={e => setEditField("modelo", e.target.value)}
                              className="h-8 text-sm w-36" />
                          : item.modelo}
                      </td>
                      {/* Costo */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={row.costo || 0} onChange={e => setEditField("costo", Number(e.target.value))}
                              className="h-8 text-sm w-28 text-right" />
                          : <span className="text-slate-600 text-xs">{fmt(item.costo)}</span>}
                      </td>
                      {/* PVP */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={row.pvp || 0} onChange={e => setEditField("pvp", Number(e.target.value))}
                              className="h-8 text-sm w-28 text-right" />
                          : <span className="font-semibold text-[#0F2A5C]">{fmt(item.pvp)}</span>}
                      </td>
                      {/* Cuota Inicial */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={row.cuota_inicial || 0} onChange={e => setEditField("cuota_inicial", Number(e.target.value))}
                              className="h-8 text-sm w-28 text-right" />
                          : <span className="text-slate-600 text-xs">{fmt(item.cuota_inicial)}</span>}
                      </td>
                      {/* Matrícula */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={row.matricula || 0} onChange={e => setEditField("matricula", Number(e.target.value))}
                              className="h-8 text-sm w-24 text-right" />
                          : <span className="text-slate-600 text-xs">{fmt(item.matricula)}</span>}
                      </td>
                      {/* P39S */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={(row.planes as any)?.P39S?.cuota || 0}
                              onChange={e => setEditPlan("P39S", Number(e.target.value))}
                              className="h-8 text-sm w-24 text-right" />
                          : <span className="text-xs text-slate-600">{fmt(item.planes?.P39S?.cuota || 0)}</span>}
                      </td>
                      {/* P52S */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={(row.planes as any)?.P52S?.cuota || 0}
                              onChange={e => setEditPlan("P52S", Number(e.target.value))}
                              className="h-8 text-sm w-24 text-right" />
                          : <span className="text-xs text-slate-600">{fmt(item.planes?.P52S?.cuota || 0)}</span>}
                      </td>
                      {/* P78S */}
                      <td className="px-4 py-3 text-right">
                        {isEditing
                          ? <Input type="number" value={(row.planes as any)?.P78S?.cuota || 0}
                              onChange={e => setEditPlan("P78S", Number(e.target.value))}
                              className="h-8 text-sm w-24 text-right" />
                          : <span className="text-xs text-slate-600">{fmt(item.planes?.P78S?.cuota || 0)}</span>}
                      </td>
                      {/* Activo toggle */}
                      <td className="px-4 py-3 text-center">
                        <button onClick={() => toggleActivo(item)}
                          className="flex items-center justify-center mx-auto"
                          data-testid={`toggle-activo-${item.id}`}>
                          {item.activo
                            ? <ToggleRight size={26} className="text-[#0F2A5C]" />
                            : <ToggleLeft size={26} className="text-slate-300" />}
                        </button>
                      </td>
                      {/* Actions */}
                      <td className="px-4 py-3 text-center">
                        {isEditing ? (
                          <div className="flex items-center justify-center gap-1.5">
                            <button onClick={saveRow} disabled={saving}
                              className="flex items-center gap-1 text-xs bg-[#0F2A5C] text-white px-2.5 py-1.5 rounded-lg hover:bg-[#163A7A] disabled:opacity-50"
                              data-testid={`save-row-${item.id}`}>
                              {saving ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                              Guardar
                            </button>
                            <button onClick={cancelEdit}
                              className="flex items-center gap-1 text-xs border border-slate-200 text-slate-600 px-2.5 py-1.5 rounded-lg hover:bg-slate-50">
                              <X size={11} /> Cancelar
                            </button>
                          </div>
                        ) : (
                          <button onClick={() => startEdit(item)}
                            className="flex items-center justify-center mx-auto text-slate-400 hover:text-[#0F2A5C] p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                            data-testid={`edit-row-${item.id}`}>
                            <Pencil size={13} />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={10} className="px-4 py-10 text-center text-slate-400 text-sm">
                      No hay modelos en el catálogo. Agrega el primero.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Agregar Modelo */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-[#0F2A5C] flex items-center gap-2">
                <Plus size={16} className="text-[#C9A84C]" /> Agregar Nuevo Modelo
              </h3>
              <button onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100">
                <X size={16} />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <Label className="text-xs font-semibold text-slate-600">Modelo *</Label>
                  <Input value={newMoto.modelo || ""} onChange={e => setNewField("modelo", e.target.value)}
                    placeholder="Ej: CB190R" className="mt-1 h-9" data-testid="new-modelo-input" />
                </div>
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Marca</Label>
                  <Input value={newMoto.marca || "Auteco"} onChange={e => setNewField("marca", e.target.value)}
                    className="mt-1 h-9" />
                </div>
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Costo</Label>
                  <Input type="number" value={newMoto.costo || ""} onChange={e => setNewField("costo", Number(e.target.value))}
                    placeholder="4157461" className="mt-1 h-9" data-testid="new-costo-input" />
                </div>
                <div>
                  <Label className="text-xs font-semibold text-slate-600">PVP *</Label>
                  <Input type="number" value={newMoto.pvp || ""} onChange={e => setNewField("pvp", Number(e.target.value))}
                    placeholder="5749900" className="mt-1 h-9" data-testid="new-pvp-input" />
                </div>
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Cuota Inicial</Label>
                  <Input type="number" value={newMoto.cuota_inicial || ""} onChange={e => setNewField("cuota_inicial", Number(e.target.value))}
                    placeholder="500000" className="mt-1 h-9" />
                </div>
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Matrícula</Label>
                  <Input type="number" value={newMoto.matricula || 660000} onChange={e => setNewField("matricula", Number(e.target.value))}
                    className="mt-1 h-9" />
                </div>
              </div>

              <div className="border-t border-slate-100 pt-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Cuotas por Plan</p>
                <div className="grid grid-cols-3 gap-3">
                  {(["P39S", "P52S", "P78S"] as const).map(plan => (
                    <div key={plan}>
                      <Label className="text-xs font-semibold text-slate-600">{plan} (semanal)</Label>
                      <Input type="number"
                        value={(newMoto.planes as any)?.[plan]?.cuota || ""}
                        onChange={e => setNewPlan(plan, Number(e.target.value))}
                        placeholder="175000" className="mt-1 h-9"
                        data-testid={`new-cuota-${plan.toLowerCase()}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
              <Button variant="outline" onClick={() => { setShowModal(false); setNewMoto({ ...EMPTY_MOTO }); }}>
                Cancelar
              </Button>
              <Button onClick={createMoto} className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white gap-1.5"
                data-testid="confirm-add-modelo-btn">
                <Plus size={14} /> Agregar al Catálogo
              </Button>
            </div>
          </div>
        </div>
      )}
    </TabsContent>
  );
}


// ─── SECURITY TAB ─────────────────────────────────────────────────────────────

function SecurityTab({ api, user }: { api: any; user: any }) {
  const [status2fa, setStatus2fa] = useState<boolean | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [loadingSetup, setLoadingSetup] = useState(false);
  const [loadingEnable, setLoadingEnable] = useState(false);

  useEffect(() => {
    api.get("/auth/2fa/status").then((res: any) => setStatus2fa(res.data.totp_enabled)).catch(() => {});
  }, [api]);

  const handleSetup = async () => {
    setLoadingSetup(true);
    try {
      const res = await api.post("/auth/2fa/setup");
      setQr(res.data.qr_code);
      setSecret(res.data.secret);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error generando QR");
    } finally { setLoadingSetup(false); }
  };

  const handleEnable = async () => {
    setLoadingEnable(true);
    try {
      await api.post("/auth/2fa/enable", { code, secret });
      toast.success("2FA activado — Tu cuenta está protegida");
      setStatus2fa(true); setQr(null); setCode(""); setSecret("");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Código incorrecto"); setCode("");
    } finally { setLoadingEnable(false); }
  };

  const handleDisable = async () => {
    if (!window.confirm("¿Desactivar 2FA? Tu cuenta quedará menos protegida.")) return;
    try {
      await api.post("/auth/2fa/disable");
      toast.success("2FA desactivado"); setStatus2fa(false);
    } catch (err: any) { toast.error(err.response?.data?.detail || "Error"); }
  };

  if (user?.role !== "admin") return null;

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
            <button onClick={handleDisable}
              className="text-xs text-red-500 hover:text-red-700 border border-red-200 px-3 py-1 rounded-lg hover:bg-red-50">
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
              <label className="text-xs font-medium text-slate-700 mb-1 block">
                Ingresa el código de 6 dígitos para confirmar
              </label>
              <input type="text" inputMode="numeric" maxLength={6} value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, ""))}
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

function AuditTab({ api }: { api: any }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<AuditFilters>({
    user_email: "", date_start: "", date_end: "", only_errors: false, page: 1,
  });

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/audit-logs", { params: { ...filters, limit: 50 } });
      setLogs(res.data.logs || []);
      setTotal(res.data.total || 0);
    } catch (err: any) {
      if (err?.response?.status !== 403) toast.error("Error cargando auditoría");
    } finally { setLoading(false); }
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
          <button onClick={exportCSV}
            className="flex items-center gap-1 text-xs border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50">
            <Download size={12} /> Exportar CSV
          </button>
        </div>

        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap gap-3 items-end bg-slate-50">
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Usuario</label>
            <input className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none w-40"
              value={filters.user_email}
              onChange={e => setFilters(f => ({ ...f, user_email: e.target.value, page: 1 }))}
              placeholder="email..." />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Desde</label>
            <input type="date" className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none"
              value={filters.date_start}
              onChange={e => setFilters(f => ({ ...f, date_start: e.target.value, page: 1 }))} />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 block mb-1">Hasta</label>
            <input type="date" className="border rounded px-2 py-1 text-xs focus:border-[#C9A84C] outline-none"
              value={filters.date_end}
              onChange={e => setFilters(f => ({ ...f, date_end: e.target.value, page: 1 }))} />
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
            <thead>
              <tr className="bg-[#0F2A5C] text-white text-[10px] uppercase sticky top-0">
                <th className="px-3 py-2.5 text-left">Fecha / Hora</th>
                <th className="px-3 py-2.5 text-left">Usuario</th>
                <th className="px-3 py-2.5 text-left">Método</th>
                <th className="px-3 py-2.5 text-left">Endpoint</th>
                <th className="px-3 py-2.5 text-center">Estado</th>
              </tr>
            </thead>
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
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    Sin registros con los filtros actuales
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="px-4 py-3 flex items-center justify-between border-t border-slate-100 bg-slate-50">
          <span className="text-xs text-slate-500">Página {filters.page} — {logs.length} de {total}</span>
          <div className="flex gap-2">
            <button disabled={filters.page <= 1}
              onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
              className="text-xs px-3 py-1 border rounded hover:bg-white disabled:opacity-40">Anterior</button>
            <button disabled={logs.length < 50}
              onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
              className="text-xs px-3 py-1 border rounded hover:bg-white disabled:opacity-40">Siguiente</button>
          </div>
        </div>
      </div>
    </TabsContent>
  );
}


// ─── MERCATELY TAB ────────────────────────────────────────────────────────────

function MercatelyTab({ api }: { api: any }) {
  const [apiKey, setApiKey] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [ceoNumber, setCeoNumber] = useState("");
  const [cgoNumber, setCgoNumber] = useState("");
  const [whitelist, setWhitelist] = useState<string[]>([]);
  const [wlInput, setWlInput] = useState("");
  const [destinatarios, setDestinatarios] = useState<string[]>([]);
  const [destInput, setDestInput] = useState("");
  const [status, setStatus] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [globalActivo, setGlobalActivo] = useState(true);
  const [horarioInicio, setHorarioInicio] = useState("08:00");
  const [horarioFin, setHorarioFin] = useState("19:00");
  const [templatesActivos, setTemplatesActivos] = useState<Record<string, boolean>>({
    T1: true, T2: true, T3: true, T4: true, T5: true,
  });
  const [datosBancarios, setDatosBancarios] = useState("");
  const [gestiones, setGestiones] = useState<any[]>([]);
  const [loadingGestiones, setLoadingGestiones] = useState(false);

  const webhookUrl = `${process.env.REACT_APP_BACKEND_URL}/api/mercately/webhook`;

  const TEMPLATE_INFO = [
    { key: "T1", label: "T1 — Recordatorio preventivo", desc: "Lunes 8am · D-2 antes del vencimiento" },
    { key: "T2", label: "T2 — Vencimiento hoy", desc: "Miércoles 8am · día de pago" },
    { key: "T3", label: "T3 — Alerta mora D+1", desc: "Jueves 9am · cuota no pagada ayer" },
    { key: "T4", label: "T4 — Confirmación de pago", desc: "Automático al registrar pago en el sistema" },
    { key: "T5", label: "T5 — Mora severa +30 días", desc: "Sábado 9am · DPD > 30" },
  ];

  useEffect(() => {
    api.get("/settings/mercately").then((res: any) => {
      const d = res.data;
      setStatus(d);
      setPhoneNumber(d.phone_number || "");
      setCeoNumber(d.ceo_number || "");
      setCgoNumber(d.cgo_number || "");
      setWhitelist(d.whitelist || []);
      setDestinatarios(d.destinatarios_resumen || []);
      setGlobalActivo(d.global_activo ?? true);
      setHorarioInicio(d.horario_inicio || "08:00");
      setHorarioFin(d.horario_fin || "19:00");
      setTemplatesActivos({ T1: true, T2: true, T3: true, T4: true, T5: true, ...(d.templates_activos || {}) });
      setDatosBancarios(d.datos_bancarios || "");
    }).catch(() => {});
    loadGestiones();
  }, []); // eslint-disable-line

  const loadGestiones = async () => {
    setLoadingGestiones(true);
    try {
      const res = await api.get("/mercately/gestiones?limit=50");
      setGestiones(res.data.gestiones || []);
    } catch { /* silent */ }
    finally { setLoadingGestiones(false); }
  };

  const handleSave = async () => {
    if (!apiKey.trim() && !status?.has_credentials) {
      toast.error("Ingresa la API Key de Mercately"); return;
    }
    setSaving(true);
    try {
      const payload: any = {
        api_key: apiKey.trim() || "",
        phone_number: phoneNumber.trim(),
        whitelist,
        ceo_number: ceoNumber.trim(),
        cgo_number: cgoNumber.trim(),
        destinatarios_resumen: destinatarios,
        global_activo: globalActivo,
        horario_inicio: horarioInicio,
        horario_fin: horarioFin,
        templates_activos: templatesActivos,
        datos_bancarios: datosBancarios.trim(),
      };
      await api.post("/settings/mercately", payload);
      toast.success("Configuración Mercately guardada");
      setStatus((p: any) => ({
        ...p, has_credentials: payload.api_key ? true : p.has_credentials,
        phone_number: phoneNumber, ceo_number: ceoNumber, cgo_number: cgoNumber, whitelist,
        destinatarios_resumen: destinatarios, global_activo: globalActivo,
        configured_at: new Date().toISOString(),
      }));
      setApiKey("");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error guardando configuración");
    } finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post("/settings/mercately/test");
      toast.success(res.data.message || "Conexión exitosa ✓");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "No se pudo conectar con Mercately");
    } finally { setTesting(false); }
  };

  const addToWhitelist = () => {
    const num = wlInput.trim();
    if (!num) return;
    const norm = num.startsWith("+") ? num : `+${num}`;
    if (!whitelist.includes(norm)) setWhitelist(prev => [...prev, norm]);
    setWlInput("");
  };

  const addToDestinatarios = () => {
    const num = destInput.trim();
    if (!num) return;
    const norm = num.startsWith("+") ? num : `+${num}`;
    if (!destinatarios.includes(norm)) setDestinatarios(prev => [...prev, norm]);
    setDestInput("");
  };

  const fmtDate = (iso: string) => {
    try { return new Date(iso).toLocaleString("es-CO", { timeZone: "America/Bogota", dateStyle: "short", timeStyle: "short" }); }
    catch { return iso?.slice(0, 16) || ""; }
  };

  return (
    <TabsContent value="mercately" className="mt-5 space-y-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-2xl space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
              <MessageCircle size={18} className="text-green-600" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#0F2A5C]">Mercately — WhatsApp Business API</h3>
              <p className="text-xs text-slate-500 mt-0.5">Canal de cobranza automatizada por WhatsApp.</p>
            </div>
          </div>
          {/* Global toggle */}
          <button
            onClick={() => setGlobalActivo(v => !v)}
            className="flex items-center gap-2 shrink-0"
            data-testid="mercately-global-toggle"
          >
            {globalActivo
              ? <><ToggleRight size={32} className="text-green-500" /><span className="text-xs text-green-600 font-semibold">Activo</span></>
              : <><ToggleLeft  size={32} className="text-slate-400" /><span className="text-xs text-slate-400">Inactivo</span></>}
          </button>
        </div>

        {/* Status badge */}
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
            No hay credenciales configuradas. Ingresa tu API Key de Mercately.
          </div>
        )}

        {/* Webhook URL */}
        <div className="bg-[#F0F7FF] rounded-xl p-3 border border-blue-100">
          <p className="text-xs font-semibold text-[#0F2A5C] mb-1">URL del Webhook (configurar en Mercately)</p>
          <div className="flex items-center gap-2">
            <code className="text-[11px] text-blue-700 bg-white border border-blue-200 rounded px-2 py-1 flex-1 truncate">
              {webhookUrl}
            </code>
            <button
              onClick={() => { navigator.clipboard.writeText(webhookUrl); toast.success("URL copiada"); }}
              className="text-[11px] text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap"
              data-testid="copy-webhook-url-btn"
            >
              Copiar
            </button>
          </div>
        </div>

        {/* Fields */}
        <div className="space-y-4">
          <div>
            <Label className="text-sm font-semibold text-slate-700">
              API Key de Mercately {status?.has_credentials && <span className="text-xs text-slate-400 font-normal">(deja vacío para mantener la actual)</span>}
            </Label>
            <Input type="password" placeholder="mercately_api_key_..."
              value={apiKey} onChange={e => setApiKey(e.target.value)}
              className="mt-1.5" data-testid="mercately-api-key-input" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm font-semibold text-slate-700">Número WhatsApp RODDOS</Label>
              <Input type="tel" placeholder="+573001234567"
                value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)}
                className="mt-1.5" data-testid="mercately-phone-input" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm font-semibold text-slate-700">Número CEO (alertas CFO)</Label>
              <Input type="tel" placeholder="+573009876543"
                value={ceoNumber} onChange={e => setCeoNumber(e.target.value)}
                className="mt-1.5" data-testid="mercately-ceo-input" />
            </div>
            <div>
              <Label className="text-sm font-semibold text-slate-700">Número CGO (alertas operativas)</Label>
              <Input type="tel" placeholder="+573009876543"
                value={cgoNumber} onChange={e => setCgoNumber(e.target.value)}
                className="mt-1.5" data-testid="mercately-cgo-input" />
            </div>
          </div>

          {/* Horario de operación */}
          <div>
            <Label className="text-sm font-semibold text-slate-700">Horario de operación</Label>
            <p className="text-xs text-slate-400 mt-0.5 mb-1.5">Los mensajes solo se envían en este horario (COT)</p>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Desde</span>
                <Input type="time" value={horarioInicio}
                  onChange={e => setHorarioInicio(e.target.value)}
                  className="w-28" data-testid="mercately-horario-inicio" />
              </div>
              <span className="text-slate-400">→</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Hasta</span>
                <Input type="time" value={horarioFin}
                  onChange={e => setHorarioFin(e.target.value)}
                  className="w-28" data-testid="mercately-horario-fin" />
              </div>
            </div>
          </div>

          {/* Datos bancarios (Template 2) */}
          <div>
            <Label className="text-sm font-semibold text-slate-700">Datos bancarios (para Template 2)</Label>
            <p className="text-xs text-slate-400 mt-0.5 mb-1.5">Se incluye en el mensaje de "vencimiento hoy" para que el cliente pueda transferir</p>
            <textarea
              value={datosBancarios}
              onChange={e => setDatosBancarios(e.target.value)}
              rows={3}
              placeholder={"Bancolombia Cta Ahorros 123-456789\nNIT: 900.xxx.xxx-1\nA nombre de: RODDOS COLOMBIA SAS"}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-xs focus:border-[#C9A84C] outline-none resize-none"
              data-testid="mercately-datos-bancarios"
            />
          </div>

          {/* Template toggles */}
          <div>
            <Label className="text-sm font-semibold text-slate-700 mb-2 block">Templates automáticos</Label>
            <div className="space-y-2">
              {TEMPLATE_INFO.map(({ key, label, desc }) => (
                <div key={key}
                  className={`flex items-center justify-between p-3 rounded-xl border transition ${
                    templatesActivos[key] ? "bg-green-50 border-green-200" : "bg-slate-50 border-slate-200"
                  }`}
                  data-testid={`template-toggle-${key.toLowerCase()}`}
                >
                  <div>
                    <p className="text-xs font-semibold text-[#0F2A5C]">{label}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{desc}</p>
                  </div>
                  <button onClick={() => setTemplatesActivos(t => ({ ...t, [key]: !t[key] }))}>
                    {templatesActivos[key]
                      ? <ToggleRight size={26} className="text-green-500" />
                      : <ToggleLeft  size={26} className="text-slate-300" />}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Whitelist */}
          <div>
            <Label className="text-sm font-semibold text-slate-700">Whitelist Empleados Internos</Label>
            <p className="text-xs text-slate-400 mb-1.5">Teléfonos que pueden enviar facturas de proveedor</p>
            <div className="flex gap-2">
              <Input type="tel" placeholder="+573001234567" value={wlInput}
                onChange={e => setWlInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addToWhitelist()}
                className="flex-1" data-testid="mercately-whitelist-input" />
              <Button variant="outline" size="sm" onClick={addToWhitelist}
                data-testid="mercately-whitelist-add-btn">
                Agregar
              </Button>
            </div>
            {whitelist.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {whitelist.map(num => (
                  <span key={num} className="flex items-center gap-1 text-xs bg-slate-100 border border-slate-200 rounded-full px-2.5 py-1">
                    <span className="font-mono">{num}</span>
                    <button onClick={() => setWhitelist(prev => prev.filter(n => n !== num))}
                      className="text-slate-400 hover:text-red-500 ml-0.5" data-testid={`whitelist-remove-${num}`}>
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <Label className="text-sm font-semibold text-slate-700">Números que reciben el resumen del viernes</Label>
            <div className="flex gap-2 mt-1.5">
              <Input type="tel" placeholder="+573001234567" value={destInput}
                onChange={e => setDestInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addToDestinatarios()}
                className="flex-1" data-testid="mercately-dest-input" />
              <Button variant="outline" size="sm" onClick={addToDestinatarios}
                data-testid="mercately-dest-add-btn">
                Agregar
              </Button>
            </div>
            {destinatarios.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {destinatarios.map(num => (
                  <span key={num} className="flex items-center gap-1 text-xs bg-blue-50 border border-blue-200 rounded-full px-2.5 py-1">
                    <span className="font-mono">{num}</span>
                    <button onClick={() => setDestinatarios(prev => prev.filter(n => n !== num))}
                      className="text-slate-400 hover:text-red-500 ml-0.5" data-testid={`dest-remove-${num}`}>
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-1">
            <Button onClick={handleTest} disabled={testing || !status?.has_credentials}
              variant="outline"
              className="flex-1 border-green-300 text-green-700 hover:bg-green-50 flex items-center justify-center gap-2"
              data-testid="test-mercately-btn">
              {testing ? <Loader2 size={14} className="animate-spin" /> : <MessageCircle size={14} />}
              Probar Conexión
            </Button>
            <Button onClick={handleSave} disabled={saving}
              className="flex-1 bg-green-600 hover:bg-green-700 text-white flex items-center justify-center gap-2"
              data-testid="save-mercately-btn">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Guardar
            </Button>
          </div>
        </div>
      </div>

      {/* Message log */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden max-w-2xl">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <span className="text-sm font-bold text-[#0F2A5C] flex items-center gap-2">
            <MessageCircle size={14} className="text-green-600" />
            Historial WhatsApp — últimos 50 mensajes
          </span>
          <button onClick={loadGestiones} disabled={loadingGestiones}
            className="text-xs text-slate-400 hover:text-[#0F2A5C] flex items-center gap-1"
            data-testid="refresh-gestiones-btn">
            <RefreshCw size={11} className={loadingGestiones ? "animate-spin" : ""} /> Actualizar
          </button>
        </div>
        <div className="overflow-x-auto max-h-80">
          {loadingGestiones ? (
            <div className="flex items-center justify-center py-8 gap-2 text-slate-400">
              <Loader2 size={14} className="animate-spin" /> Cargando...
            </div>
          ) : gestiones.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-sm">
              Sin mensajes registrados aún.
            </div>
          ) : (
            <table className="w-full text-xs" data-testid="gestiones-log-table">
              <thead>
                <tr className="bg-slate-50 text-[10px] text-slate-500 uppercase sticky top-0">
                  <th className="px-3 py-2 text-left">Fecha (COT)</th>
                  <th className="px-3 py-2 text-left">Cliente</th>
                  <th className="px-3 py-2 text-center">Tipo</th>
                  <th className="px-3 py-2 text-left">Template</th>
                  <th className="px-3 py-2 text-left">Mensaje</th>
                </tr>
              </thead>
              <tbody>
                {gestiones.map((g, i) => (
                  <tr key={i} className={`border-b border-slate-50 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/30"}`}>
                    <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{fmtDate(g.fecha)}</td>
                    <td className="px-3 py-2 max-w-[120px] truncate font-medium">{g.cliente_nombre || "—"}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${g.tipo === "enviado" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
                        {g.tipo === "enviado" ? "→ env" : "← rec"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-500">{g.template}</td>
                    <td className="px-3 py-2 text-slate-600 max-w-[200px] truncate">{g.mensaje}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </TabsContent>
  );
}


// ─── WEBHOOKS TAB ─────────────────────────────────────────────────────────────

function WebhooksTab({ api }: { api: any }) {
  const [webhookStatus, setWebhookStatus] = useState<any>(null);
  const [registering, setRegistering] = useState(false);
  const [runningSyncPago, setRunningSyncPago] = useState(false);
  const [runningSyncFactura, setRunningSyncFactura] = useState(false);

  const loadWebhookStatus = async () => {
    try {
      const res = await api.get("/webhooks/status");
      setWebhookStatus(res.data);
    } catch {}
  };

  useEffect(() => { loadWebhookStatus(); }, []); // eslint-disable-line

  const handleRegisterAll = async () => {
    setRegistering(true);
    try {
      const res = await api.post("/webhooks/setup");
      if (res.data.nota_alegra_bug) {
        toast.warning(res.data.nota_alegra_bug, { duration: 8000 });
      } else {
        toast.success(`${res.data.registradas}/${res.data.total} suscripciones registradas en Alegra`);
      }
      await loadWebhookStatus();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error registrando webhooks");
    } finally { setRegistering(false); }
  };

  const handleRunSyncPago = async () => {
    setRunningSyncPago(true);
    try {
      const res = await api.post("/webhooks/sync-pagos-ahora");
      toast.success(`Sync ejecutado: ${res.data.procesados} pagos nuevos`);
      await loadWebhookStatus();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error ejecutando sync");
    } finally { setRunningSyncPago(false); }
  };

  const handleRunSyncFactura = async () => {
    setRunningSyncFactura(true);
    try {
      const res = await api.post("/webhooks/sync-facturas-ahora", {});
      toast.success(`Polling ejecutado: ${res.data.procesadas} facturas nuevas procesadas`);
      await loadWebhookStatus();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error ejecutando sync de facturas");
    } finally { setRunningSyncFactura(false); }
  };

  const EVENTOS_ESPERADOS = [
    "new-invoice", "edit-invoice", "delete-invoice",
    "new-bill",    "edit-bill",    "delete-bill",
    "new-client",  "edit-client",  "delete-client",
    "new-item",    "edit-item",    "delete-item",
  ];

  const subs: any[] = webhookStatus?.suscripciones || [];

  const getSubStatus = (evento: string) => {
    const s = subs.find((x: any) => x.evento === evento);
    return s?.ok ?? null;
  };

  return (
    <TabsContent value="webhooks" className="mt-5 space-y-5">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-2xl space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
              <Globe size={18} className="text-[#C9A84C]" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#0F2A5C]">Webhooks Alegra — Sincronización Bidireccional</h3>
              <p className="text-xs text-slate-500 mt-0.5">12 eventos suscritos. RODDOS recibe cambios de Alegra en tiempo real.</p>
            </div>
          </div>
          {webhookStatus && (
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${webhookStatus.total_activas >= 12 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
              {webhookStatus.total_activas >= 12 ? <Check size={11} /> : <AlertTriangle size={11} />}
              {webhookStatus.total_activas}/12 activos
            </div>
          )}
        </div>

        {/* 12 Events grid */}
        <div>
          <p className="text-xs font-semibold text-slate-600 mb-2">Estado de suscripciones</p>
          <div className="grid grid-cols-3 gap-2">
            {EVENTOS_ESPERADOS.map(ev => {
              const ok = getSubStatus(ev);
              return (
                <div key={ev}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
                    ok === true  ? "bg-green-50 border-green-200" :
                    ok === false ? "bg-red-50 border-red-200" :
                                   "bg-slate-50 border-slate-200"
                  }`}
                  data-testid={`webhook-event-${ev}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    ok === true  ? "bg-green-500" :
                    ok === false ? "bg-red-500"   : "bg-slate-300"
                  }`} />
                  <span className={ok === true ? "text-green-700 font-medium" : ok === false ? "text-red-600" : "text-slate-500"}>
                    {ev}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Nota sobre bug de Alegra API + Registro Manual */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-amber-800">Registro automático via API no disponible</p>
              <p className="text-[11px] text-amber-700 mt-0.5">
                La API de Alegra rechaza URLs con <code className="font-mono bg-amber-100 px-1 rounded">https://</code> (bug confirmado).
                El polling automático cada 5 min está activo. Para activar webhooks en tiempo real, regístralos manualmente:
              </p>
            </div>
          </div>
          <ol className="text-[11px] text-amber-800 space-y-1 pl-5 list-decimal">
            <li>Abre <strong>app.alegra.com → Configuración → Integraciones → Webhooks</strong></li>
            <li>Copia la URL del receptor (botón abajo)</li>
            <li>Crea un webhook con los 12 eventos listados arriba</li>
          </ol>
          <div className="flex gap-2">
            <a
              href="https://app.alegra.com/user/integrations/webhooks"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-xs font-semibold bg-amber-600 text-white px-3 py-1.5 rounded-lg hover:bg-amber-700 transition"
              data-testid="open-alegra-webhooks-btn"
            >
              <Globe size={12} /> Abrir Alegra → Webhooks
            </a>
            <button
              onClick={() => { navigator.clipboard.writeText(`${process.env.REACT_APP_BACKEND_URL}/api/webhooks/alegra`); toast.success("URL copiada"); }}
              className="flex items-center gap-1.5 text-xs font-semibold border border-amber-400 text-amber-700 px-3 py-1.5 rounded-lg hover:bg-amber-100 transition"
              data-testid="copy-webhook-url-manual-btn"
            >
              Copiar URL receptor
            </button>
          </div>
        </div>

        {/* Webhook URL */}
        <div className="bg-[#F0F7FF] rounded-xl p-3 border border-blue-100">
          <p className="text-xs font-semibold text-[#0F2A5C] mb-1">URL Receptor del Webhook</p>
          <div className="flex items-center gap-2">
            <code className="text-[11px] text-blue-700 bg-white border border-blue-200 rounded px-2 py-1 flex-1 truncate">
              {process.env.REACT_APP_BACKEND_URL}/api/webhooks/alegra
            </code>
            <button
              onClick={() => { navigator.clipboard.writeText(`${process.env.REACT_APP_BACKEND_URL}/api/webhooks/alegra`); toast.success("URL copiada"); }}
              className="text-[11px] text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap"
              data-testid="copy-webhook-receiver-url-btn"
            >
              Copiar
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button onClick={handleRegisterAll} disabled={registering}
            className="flex-1 bg-[#0F2A5C] text-white hover:bg-[#163A7A] flex items-center justify-center gap-2"
            data-testid="register-all-webhooks-btn">
            {registering ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
            Re-registrar todos los webhooks
          </Button>
          <Button onClick={() => loadWebhookStatus()} variant="outline"
            className="flex items-center gap-1.5 border-slate-200 text-slate-600"
            data-testid="refresh-webhook-status-btn">
            <RefreshCw size={13} />
          </Button>
        </div>
      </div>

      {/* Payment sync cron */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-2xl space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
            <RefreshCw size={18} className="text-blue-600" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#0F2A5C]">Sincronización de Pagos Alegra (Cron)</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Alegra no emite webhooks de pagos. Un cron ejecuta cada 5 min para detectar pagos externos.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Intervalo</p>
            <p className="text-sm font-bold text-[#0F2A5C] mt-0.5">cada 5 min</p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Pagos hoy</p>
            <p className="text-sm font-bold text-[#0F2A5C] mt-0.5" data-testid="pagos-hoy-count">
              {webhookStatus?.pagos_sincronizados_hoy ?? "—"}
            </p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100 col-span-1">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Último sync</p>
            <p className="text-[11px] font-semibold text-slate-600 mt-0.5 truncate">
              {webhookStatus?.ultimo_sync_pago === "nunca" ? "Nunca" :
               webhookStatus?.ultimo_sync_pago ? new Date(webhookStatus.ultimo_sync_pago).toLocaleTimeString("es-CO", {hour: "2-digit", minute: "2-digit"}) : "—"}
            </p>
          </div>
        </div>

        <Button onClick={handleRunSyncPago} disabled={runningSyncPago}
          variant="outline"
          className="flex items-center gap-2 border-blue-300 text-blue-700 hover:bg-blue-50"
          data-testid="run-sync-pagos-btn">
          {runningSyncPago ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Ejecutar sync de pagos ahora
        </Button>
      </div>

      {/* Invoice polling cron */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 max-w-2xl space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center flex-shrink-0">
            <RefreshCw size={18} className="text-emerald-600" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#0F2A5C]">Polling de Facturas Alegra (Fallback Webhook)</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Revisa facturas nuevas en Alegra cada 5 min. Actualiza inventario y loanbooks automáticamente.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Intervalo</p>
            <p className="text-sm font-bold text-[#0F2A5C] mt-0.5">cada 5 min</p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Procesadas hoy</p>
            <p className="text-sm font-bold text-[#0F2A5C] mt-0.5" data-testid="facturas-polling-hoy">
              {webhookStatus?.facturas_procesadas_hoy ?? "—"}
            </p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
            <p className="text-[10px] text-slate-400 uppercase font-semibold">Último poll</p>
            <p className="text-[11px] font-semibold text-slate-600 mt-0.5 truncate">
              {webhookStatus?.ultimo_polling_timestamp === "nunca" ? "Nunca" :
               webhookStatus?.ultimo_polling_timestamp
                 ? new Date(webhookStatus.ultimo_polling_timestamp).toLocaleTimeString("es-CO", {hour: "2-digit", minute: "2-digit"})
                 : "—"}
            </p>
          </div>
        </div>

        {webhookStatus?.ultima_factura_procesada_id ? (
          <p className="text-[11px] text-slate-400">
            Última factura Alegra procesada: ID <strong>{webhookStatus.ultima_factura_procesada_id}</strong>
          </p>
        ) : null}

        <Button onClick={handleRunSyncFactura} disabled={runningSyncFactura}
          variant="outline"
          className="flex items-center gap-2 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
          data-testid="run-sync-facturas-btn">
          {runningSyncFactura ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Ejecutar polling de facturas ahora
        </Button>
      </div>
    </TabsContent>
  );
}

// ── Scheduler Tab ─────────────────────────────────────────────────────────────

const SCHEDULER_JOBS = [
  { id: "calcular_dpd_todos",        label: "Calcular DPD",              schedule: "Diario 06:00" },
  { id: "alertar_buckets_criticos",  label: "Alertas Buckets WA",        schedule: "Diario 06:05" },
  { id: "verificar_alertas_cfo",     label: "Verificar Alertas CFO",     schedule: "Diario 06:10" },
  { id: "calcular_scores",           label: "Calcular Scores + PTP",     schedule: "Diario 06:30" },
  // BUILD 9
  { id: "alertas_predictivas",       label: "Alertas Predictivas ML",    schedule: "Diario 06:45", badge: "ML" },
  { id: "generar_cola_radar",        label: "Generar Cola RADAR",        schedule: "Diario 07:00" },
  { id: "resolver_outcomes",         label: "Resolver Outcomes WA",      schedule: "Diario 07:30", badge: "ML" },
  { id: "recordatorio_preventivo",   label: "Recordatorio Preventivo",   schedule: "Mar 09:00" },
  { id: "recordatorio_vencimiento",  label: "Recordatorio Vencimiento",  schedule: "Mié 09:00" },
  { id: "notificar_mora_nueva",      label: "Notificar Mora Nueva",      schedule: "Jue 09:00" },
  { id: "resumen_semanal_ceo",       label: "Resumen Semanal CEO",       schedule: "Vie 17:00" },
  // BUILD 9 — semanal
  { id: "procesar_patrones",         label: "Procesar Patrones ML",      schedule: "Lun 08:00", badge: "ML" },
];

function SchedulerTab({ api }: { api: any }) {
  const [logs, setLogs]           = useState<any[]>([]);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(true);

  useEffect(() => {
    api.get("/settings/wa-logs?limit=50")
      .then((r: any) => setLogs(r.data))
      .catch(() => {})
      .finally(() => setLoadingLogs(false));
  }, [api]);

  const triggerJob = async (jobId: string) => {
    setTriggering(jobId);
    try {
      await api.post(`/scheduler/trigger/${jobId}`);
      toast.success(`Job "${jobId}" iniciado en background`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error al ejecutar job");
    } finally {
      setTimeout(() => setTriggering(null), 1500);
    }
  };

  return (
    <div className="space-y-5">
      {/* Jobs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <h3 className="text-sm font-bold text-[#0F2A5C] mb-3 flex items-center gap-2">
          <span>⏱</span> Jobs del Scheduler (12 total — 3 de ML activos en BUILD 9)
        </h3>
        <div className="space-y-2">
          {SCHEDULER_JOBS.map(job => (
            <div key={job.id} data-testid={`scheduler-job-${job.id}`}
              className="flex items-center justify-between py-2 px-3 bg-slate-50 rounded-lg border border-slate-100">
              <div>
                <p className="text-sm font-medium text-slate-700 flex items-center gap-1.5">
                  {job.label}
                  {job.badge && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 border border-blue-200">{job.badge}</span>
                  )}
                </p>
                <p className="text-xs text-slate-400">{job.schedule} (America/Bogota)</p>
              </div>
              <button
                onClick={() => triggerJob(job.id)}
                disabled={triggering === job.id}
                data-testid={`trigger-${job.id}`}
                className="text-xs bg-[#0F2A5C] text-white px-3 py-1.5 rounded-lg hover:bg-[#163A7A] disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                {triggering === job.id ? (
                  <><Loader2 size={11} className="animate-spin" /> Ejecutando...</>
                ) : "▶ Ejecutar"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* WA Logs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <h3 className="text-sm font-bold text-[#0F2A5C] mb-3 flex items-center gap-2">
          <span>💬</span> Historial WA enviados
          <span className="ml-auto text-xs text-slate-400 font-normal">Últimos 50 mensajes</span>
        </h3>
        {loadingLogs ? (
          <p className="text-xs text-slate-400">Cargando...</p>
        ) : logs.length === 0 ? (
          <p className="text-xs text-slate-400 py-4 text-center">No hay mensajes registrados aún.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-100">
                  <th className="py-2 pr-3">Fecha</th>
                  <th className="py-2 pr-3">Destinatario</th>
                  <th className="py-2 pr-3">Job</th>
                  <th className="py-2 pr-3">Estado</th>
                  <th className="py-2">Mensaje</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-50" data-testid={`wa-log-${i}`}>
                    <td className="py-1.5 pr-3 text-slate-500 whitespace-nowrap">
                      {log.timestamp ? log.timestamp.slice(0, 16).replace("T", " ") : "—"}
                    </td>
                    <td className="py-1.5 pr-3 font-mono text-slate-600">{log.entity_id}</td>
                    <td className="py-1.5 pr-3 text-slate-600">{log.actor || log.metadata?.job || "—"}</td>
                    <td className="py-1.5 pr-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        log.new_state === "sent" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                      }`}>
                        {log.new_state === "sent" ? "OK" : "FAIL"}
                      </span>
                    </td>
                    <td className="py-1.5 text-slate-500 max-w-xs truncate">
                      {log.metadata?.mensaje_preview || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}



// ═══════════════════════════════════════════════════════════════
// DIAN Tab — Integración facturas electrónicas
// ═══════════════════════════════════════════════════════════════
function DianTab({ api }: { api: any }) {
  const [status, setStatus] = React.useState<any>(null);
  const [historial, setHistorial] = React.useState<any[]>([]);
  const [syncing, setSyncing] = React.useState(false);
  const [probando, setProbando] = React.useState(false);

  const loadStatus = React.useCallback(async () => {
    try {
      const s = await api.get("/dian/status");
      setStatus(s.data);
      const h = await api.get("/dian/historial");
      setHistorial(Array.isArray(h.data) ? h.data.slice(0, 10) : []);
    } catch {}
  }, [api]);

  React.useEffect(() => { loadStatus(); }, [loadStatus]);

  async function handleSync() {
    setSyncing(true);
    try {
      const res = await api.post("/dian/sync", {});
      toast.success(`DIAN sync: ${res.data?.procesadas ?? 0} causadas, ${res.data?.omitidas ?? 0} omitidas`);
      await loadStatus();
    } catch { toast.error("Error en DIAN sync"); }
    finally { setSyncing(false); }
  }

  async function handleProbarConexion() {
    setProbando(true);
    try {
      const res = await api.post("/dian/probar-conexion", {});
      if (res.data?.ok) toast.success(res.data.mensaje);
      else toast.error(res.data?.mensaje || "Error al probar conexión");
    } catch { toast.error("Error al probar conexión"); }
    finally { setProbando(false); }
  }

  return (
    <TabsContent value="dian" className="mt-5">
    <div className="space-y-5" data-testid="dian-tab">
      {/* Banner modo simulación */}
      <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex items-start gap-3">
        <AlertTriangle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-bold text-amber-900">
            ⚠️ Modo simulación activo — conecta credenciales reales para datos DIAN
          </p>
          <p className="text-xs text-amber-700 mt-1">
            Los datos mostrados son simulados con proveedores reales de RODDOS (Auteco, bancos, arriendo).
            Para activar la integración real, configura un proveedor intermediario como
            <strong> Alanube</strong> o <strong>Facturalatam</strong>.
          </p>
          <button
            className="mt-2 text-xs font-semibold text-amber-800 border border-amber-500 bg-amber-100 px-3 py-1 rounded-lg hover:bg-amber-200 transition"
            data-testid="dian-configurar-credenciales-btn"
            onClick={() => toast.info("Para activar: configura DIAN_TOKEN, DIAN_AMBIENTE y DIAN_BASE_URL en las variables de entorno del backend")}
          >
            Configurar credenciales reales →
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Estado</p>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <p className="text-sm font-semibold text-slate-700">Simulación activa</p>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Facturas causadas</p>
          <p className="text-xl font-bold text-[#0F2A5C]" data-testid="dian-total-causadas">
            {status?.total_causadas ?? "—"}
          </p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Próximo sync automático</p>
          <p className="text-sm font-semibold text-slate-700">
            Hoy a las <span className="text-[#0F2A5C]">11:00 PM</span>
          </p>
        </div>
      </div>

      {status?.ultimo_sync && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <p className="text-xs font-semibold text-slate-500 mb-1">Último sync</p>
          <p className="text-sm text-slate-700">
            {status.ultimo_sync.timestamp?.slice(0, 16).replace("T", " ")} —{" "}
            <span className="text-green-600 font-medium">{status.ultimo_sync.procesadas} causadas</span>
            {", "}
            <span className="text-slate-500">{status.ultimo_sync.omitidas} omitidas</span>
            {(status.ultimo_sync.errores ?? 0) > 0 && (
              <span className="text-red-500 ml-1">, {status.ultimo_sync.errores} errores</span>
            )}
          </p>
        </div>
      )}

      <div className="flex gap-3 flex-wrap">
        <button
          data-testid="dian-sync-ahora-btn"
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 bg-[#0F2A5C] text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-[#0F2A5C]/90 transition disabled:opacity-60"
        >
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Ejecutar sync ahora
        </button>
        <button
          data-testid="dian-probar-conexion-btn"
          onClick={handleProbarConexion}
          disabled={probando}
          className="flex items-center gap-2 border border-[#0F2A5C]/30 text-[#0F2A5C] text-sm font-semibold px-4 py-2 rounded-lg hover:bg-[#0F2A5C]/5 transition"
        >
          {probando ? <Loader2 size={13} className="animate-spin" /> : null}
          Probar conexión
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <h3 className="text-sm font-bold text-[#0F2A5C] mb-3">Historial de syncs (últimos 30 días)</h3>
        {historial.length === 0 ? (
          <p className="text-xs text-slate-400 py-4 text-center">Sin syncs registrados aún.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-100">
                  <th className="py-2 pr-3">Fecha</th>
                  <th className="py-2 pr-3">Consultadas</th>
                  <th className="py-2 pr-3">Causadas</th>
                  <th className="py-2 pr-3">Omitidas</th>
                  <th className="py-2">Errores</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((s: any, i: number) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="py-2 pr-3 text-slate-600">{s.timestamp?.slice(0, 16).replace("T", " ")}</td>
                    <td className="py-2 pr-3 text-slate-600">{s.consultadas ?? 0}</td>
                    <td className="py-2 pr-3 text-green-600 font-medium">{s.procesadas ?? s.causadas ?? 0}</td>
                    <td className="py-2 pr-3 text-slate-500">{s.omitidas ?? 0}</td>
                    <td className="py-2 text-red-500">{s.errores ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
    </TabsContent>
  );
}
