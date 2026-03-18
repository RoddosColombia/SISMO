import React, { useState, useEffect } from "react";
import {
  User, Lock, Shield, Bell, CheckCircle2, XCircle,
  Eye, EyeOff, Save, LogOut, Loader2, AlertTriangle,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

// ── Helpers ────────────────────────────────────────────────────────────────────
function PasswordStrength({ password }: { password: string }) {
  const checks = [
    { ok: password.length >= 8,                label: "Mínimo 8 caracteres" },
    { ok: /[A-Z]/.test(password),              label: "Al menos 1 mayúscula" },
    { ok: /[0-9]/.test(password),              label: "Al menos 1 número" },
  ];
  return (
    <ul className="mt-2 space-y-1">
      {checks.map((c) => (
        <li key={c.label} className={`flex items-center gap-1.5 text-xs ${c.ok ? "text-green-600" : "text-slate-400"}`}>
          {c.ok ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
          {c.label}
        </li>
      ))}
    </ul>
  );
}

// ── Sección 1: Datos del usuario ──────────────────────────────────────────────
function SeccionDatos({ api, user }: { api: any; user: any }) {
  const [nombre, setNombre] = useState(user?.name || "");
  const [cargo, setCargo] = useState(user?.cargo || "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!nombre.trim()) { toast.error("El nombre no puede estar vacío"); return; }
    setSaving(true);
    try {
      await api.put("/auth/perfil", { nombre, cargo });
      toast.success("Perfil actualizado");
    } catch {
      toast.error("Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">Nombre completo</label>
          <input
            data-testid="perfil-nombre-input"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#0F2A5C]/20 focus:border-[#0F2A5C] outline-none"
            placeholder="Tu nombre completo"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">Cargo</label>
          <input
            data-testid="perfil-cargo-input"
            value={cargo}
            onChange={(e) => setCargo(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#0F2A5C]/20 focus:border-[#0F2A5C] outline-none"
            placeholder="Ej: Contador, Gerente..."
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">Correo electrónico</label>
          <input
            value={user?.email || ""}
            readOnly
            className="w-full border border-slate-100 bg-slate-50 rounded-lg px-3 py-2 text-sm text-slate-500 cursor-not-allowed"
          />
          <p className="text-[11px] text-slate-400 mt-0.5">El correo es tu usuario — no se puede cambiar</p>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">Empresa</label>
          <input
            value="RODDOS S.A.S."
            readOnly
            className="w-full border border-slate-100 bg-slate-50 rounded-lg px-3 py-2 text-sm text-slate-500 cursor-not-allowed"
          />
        </div>
      </div>
      <button
        data-testid="perfil-guardar-btn"
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-1.5 bg-[#0F2A5C] text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-[#0F2A5C]/90 transition disabled:opacity-60"
      >
        {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
        Guardar cambios
      </button>
    </div>
  );
}

// ── Sección 2: Cambio de contraseña ───────────────────────────────────────────
function SeccionPassword({ api }: { api: any }) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [form, setForm] = useState({ actual: "", nueva: "", confirmar: "" });
  const [show, setShow] = useState({ actual: false, nueva: false, confirmar: false });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const coinciden = form.nueva && form.confirmar && form.nueva === form.confirmar;
  const noCoinciden = form.nueva && form.confirmar && form.nueva !== form.confirmar;

  async function handleCambiar() {
    setError("");
    if (!form.actual || !form.nueva || !form.confirmar) { setError("Completa todos los campos"); return; }
    if (form.nueva !== form.confirmar) { setError("Las contraseñas nuevas no coinciden"); return; }
    setSaving(true);
    try {
      await api.put("/auth/cambiar-password", {
        password_actual: form.actual,
        password_nueva: form.nueva,
        password_confirmar: form.confirmar,
      });
      toast.success("Contraseña actualizada. Inicia sesión de nuevo.");
      setTimeout(() => { logout(); navigate("/login"); }, 1500);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error al cambiar la contraseña");
    } finally {
      setSaving(false);
    }
  }

  const field = (key: "actual" | "nueva" | "confirmar", label: string, testId: string) => (
    <div>
      <label className="block text-xs font-semibold text-slate-500 mb-1">{label}</label>
      <div className="relative">
        <input
          data-testid={testId}
          type={show[key] ? "text" : "password"}
          value={form[key]}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm pr-9 focus:ring-2 focus:ring-[#0F2A5C]/20 focus:border-[#0F2A5C] outline-none"
          placeholder="••••••••"
        />
        <button
          type="button"
          onClick={() => setShow({ ...show, [key]: !show[key] })}
          className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
        >
          {show[key] ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-4 max-w-md">
      {field("actual", "Contraseña actual", "perfil-pwd-actual")}
      {field("nueva", "Nueva contraseña", "perfil-pwd-nueva")}
      {form.nueva && <PasswordStrength password={form.nueva} />}
      {field("confirmar", "Confirmar contraseña", "perfil-pwd-confirmar")}
      {noCoinciden && (
        <p className="text-xs text-red-500 flex items-center gap-1"><XCircle size={11} /> Las contraseñas no coinciden</p>
      )}
      {coinciden && (
        <p className="text-xs text-green-600 flex items-center gap-1"><CheckCircle2 size={11} /> Las contraseñas coinciden</p>
      )}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg p-2 text-xs text-red-700" data-testid="perfil-pwd-error">
          <AlertTriangle size={13} />{error}
        </div>
      )}
      <button
        data-testid="perfil-cambiar-pwd-btn"
        onClick={handleCambiar}
        disabled={saving || !form.actual || !form.nueva || !coinciden}
        className="flex items-center gap-1.5 bg-amber-600 text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-amber-700 transition disabled:opacity-50"
      >
        {saving ? <Loader2 size={13} className="animate-spin" /> : <Lock size={13} />}
        Cambiar contraseña
      </button>
    </div>
  );
}

// ── Sección 3: Sesiones activas ───────────────────────────────────────────────
function SeccionSesiones({ api }: { api: any }) {
  const [sesiones, setSesiones] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    api.get("/auth/sesiones").then((d: any) => {
      setSesiones(Array.isArray(d) ? d : d.data || []);
    }).catch(() => setSesiones([])).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-3">
      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 text-sm"><Loader2 size={14} className="animate-spin" /> Cargando sesiones...</div>
      ) : sesiones.length === 0 ? (
        <p className="text-sm text-slate-400">Sin historial de sesiones</p>
      ) : (
        sesiones.map((s, i) => (
          <div key={i} className="flex items-center justify-between border border-slate-200 rounded-xl px-4 py-3 bg-white">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-[#0F2A5C]/10 rounded-full flex items-center justify-center">
                <Shield size={14} className="text-[#0F2A5C]" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-700">{s.dispositivo || "Navegador web"}</p>
                <p className="text-xs text-slate-400">
                  Último acceso: {s.last_active ? new Date(s.last_active).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "—"}
                </p>
              </div>
            </div>
            {s.es_actual ? (
              <span className="text-[11px] font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Esta sesión</span>
            ) : (
              <button className="text-xs text-red-500 hover:text-red-700 transition flex items-center gap-1">
                <LogOut size={11} /> Cerrar
              </button>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ── Sección 4: Preferencias ───────────────────────────────────────────────────
function SeccionPreferencias({ api }: { api: any }) {
  const [prefs, setPrefs] = useState({
    notif_errores_agente: true,
    notif_resumen_cfo_lunes: true,
    notif_dian_errores: true,
  });
  const [saving, setSaving] = useState(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    api.get("/auth/preferencias").then((d: any) => setPrefs(d)).catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await api.put("/auth/preferencias", prefs);
      toast.success("Preferencias guardadas");
    } catch { toast.error("Error al guardar"); }
    finally { setSaving(false); }
  }

  const toggle = (key: keyof typeof prefs, label: string, testId: string) => (
    <label className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0 cursor-pointer" data-testid={testId}>
      <span className="text-sm text-slate-600">{label}</span>
      <div className={`relative w-10 h-5 rounded-full transition-colors ${prefs[key] ? "bg-[#0F2A5C]" : "bg-slate-200"}`}
        onClick={() => setPrefs({ ...prefs, [key]: !prefs[key] })}>
        <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${prefs[key] ? "translate-x-5" : ""}`} />
      </div>
    </label>
  );

  return (
    <div className="space-y-4 max-w-lg">
      <div className="border border-slate-200 rounded-xl p-4 bg-white divide-y divide-slate-100">
        {toggle("notif_errores_agente", "Alerta cuando el agente detecta errores", "pref-notif-agente")}
        {toggle("notif_resumen_cfo_lunes", "Resumen semanal del CFO los lunes", "pref-notif-cfo")}
        {toggle("notif_dian_errores", "Alerta cuando DIAN sync tiene errores", "pref-notif-dian")}
      </div>
      <button
        data-testid="prefs-guardar-btn"
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-1.5 bg-[#0F2A5C] text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-[#0F2A5C]/90 transition disabled:opacity-60"
      >
        {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
        Guardar preferencias
      </button>
    </div>
  );
}

// ── Página principal ───────────────────────────────────────────────────────────
export default function Perfil() {
  const { api, user } = useAuth();
  const [seccion, setSeccion] = useState<"datos" | "password" | "sesiones" | "preferencias">("datos");

  const secciones = [
    { key: "datos",        icon: User,   label: "Datos del perfil" },
    { key: "password",     icon: Lock,   label: "Cambio de contraseña" },
    { key: "sesiones",     icon: Shield, label: "Sesiones activas" },
    { key: "preferencias", icon: Bell,   label: "Preferencias" },
  ] as const;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6" data-testid="perfil-page">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat">Mi Perfil</h2>
        <p className="text-sm text-slate-500 mt-1">Gestiona tu cuenta, contraseña y preferencias</p>
      </div>

      {/* Avatar + nav */}
      <div className="flex flex-col md:flex-row gap-6">
        {/* Sidebar nav */}
        <nav className="md:w-56 flex-shrink-0 space-y-1">
          {secciones.map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              data-testid={`perfil-nav-${key}`}
              onClick={() => setSeccion(key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors text-left
                ${seccion === key ? "bg-[#0F2A5C] text-white" : "text-slate-600 hover:bg-slate-100"}`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </nav>

        {/* Content card */}
        <div className="flex-1 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          {seccion === "datos" && <SeccionDatos api={api} user={user} />}
          {seccion === "password" && <SeccionPassword api={api} />}
          {seccion === "sesiones" && <SeccionSesiones api={api} />}
          {seccion === "preferencias" && <SeccionPreferencias api={api} />}
        </div>
      </div>
    </div>
  );
}
