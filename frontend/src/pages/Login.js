import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { Eye, EyeOff, Shield } from "lucide-react";

export default function Login() {
  const { login, setAuth, token } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ email: "", password: "" });
  const [totp, setTotp] = useState("");
  const [tempToken, setTempToken] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);

  const API = process.env.REACT_APP_BACKEND_URL;

  // Redirect if already authenticated
  useEffect(() => {
    if (token) navigate("/dashboard", { replace: true });
  }, [token, navigate]);

  const handleCredentials = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) { toast.error("Completa todos los campos"); return; }
    setLoading(true);
    try {
      const result = await login(form.email, form.password);
      if (result.requires_2fa) {
        setTempToken(result.temp_token);
        setStep(2);
        toast.info("Ingresa el código de tu app autenticadora");
      } else {
        navigate("/dashboard", { replace: true });
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Error de autenticación");
    } finally {
      setLoading(false);
    }
  };

  const handleTwoFA = async (e) => {
    e.preventDefault();
    if (totp.length !== 6) { toast.error("El código debe tener 6 dígitos"); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/auth/2fa/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temp_token: tempToken, code: totp }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Código incorrecto");
      setAuth(data.token, data.user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(err.message);
      setTotp("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0F2A5C] via-[#163A7A] to-[#0a1f44]">
      <div className="w-full max-w-md px-6">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#C9A84C] rounded-2xl mb-4 shadow-lg">
            <span className="text-[#0F2A5C] font-black text-2xl">R</span>
          </div>
          <h1 className="text-3xl font-black text-white font-montserrat tracking-tight">RODDOS</h1>
          <p className="text-[#C9A84C] text-sm font-medium mt-1">Contable IA — Powered by Alegra</p>
        </div>

        <div className="bg-white/10 backdrop-blur-xl rounded-3xl border border-white/20 p-8 shadow-2xl">
          {step === 1 ? (
            <>
              <h2 className="text-xl font-bold text-white mb-6">Iniciar Sesión</h2>
              <form onSubmit={handleCredentials} className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-white/70 mb-1.5 block">Email</label>
                  <input type="email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full bg-white/10 border border-white/20 text-white rounded-xl px-4 py-3 text-sm placeholder-white/40 focus:outline-none focus:border-[#C9A84C] transition"
                    placeholder="tu@email.com" data-testid="login-email-input" autoComplete="email" />
                </div>
                <div>
                  <label className="text-xs font-medium text-white/70 mb-1.5 block">Contraseña</label>
                  <div className="relative">
                    <input type={showPwd ? "text" : "password"} value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      className="w-full bg-white/10 border border-white/20 text-white rounded-xl px-4 py-3 text-sm placeholder-white/40 focus:outline-none focus:border-[#C9A84C] transition pr-10"
                      placeholder="••••••••" data-testid="login-password-input" autoComplete="current-password" />
                    <button type="button" onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/80">
                      {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="w-full bg-[#C9A84C] hover:bg-[#b8903e] text-[#0F2A5C] font-bold py-3 rounded-xl text-sm transition disabled:opacity-50"
                  data-testid="login-submit-btn">
                  {loading ? "Verificando..." : "Ingresar"}
                </button>
              </form>
              <div className="mt-5 pt-5 border-t border-white/10">
                <p className="text-[11px] text-white/40 text-center mb-2">Acceso demo</p>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => setForm({ email: "admin@roddos.com", password: "Admin@RODDOS2025!" })}
                    className="text-xs bg-white/10 hover:bg-white/20 text-white/70 py-2 px-3 rounded-lg transition" data-testid="demo-admin-btn">
                    Admin
                  </button>
                  <button onClick={() => setForm({ email: "contador@roddos.com", password: "Contador@2025!" })}
                    className="text-xs bg-white/10 hover:bg-white/20 text-white/70 py-2 px-3 rounded-lg transition" data-testid="demo-user-btn">
                    Contador
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-14 h-14 bg-[#C9A84C]/20 rounded-2xl mb-3">
                  <Shield size={28} className="text-[#C9A84C]" />
                </div>
                <h2 className="text-xl font-bold text-white">Verificación 2FA</h2>
                <p className="text-white/60 text-sm mt-1">Código de Google Authenticator</p>
              </div>
              <form onSubmit={handleTwoFA} className="space-y-4">
                <input type="text" inputMode="numeric" maxLength={6} value={totp}
                  onChange={(e) => setTotp(e.target.value.replace(/\D/g, ""))}
                  className="w-full bg-white/10 border border-white/20 text-white rounded-xl px-4 py-4 text-center text-3xl font-mono tracking-[0.5em] placeholder-white/30 focus:outline-none focus:border-[#C9A84C] transition"
                  placeholder="000000" autoFocus data-testid="totp-input" />
                <button type="submit" disabled={loading || totp.length !== 6}
                  className="w-full bg-[#C9A84C] hover:bg-[#b8903e] text-[#0F2A5C] font-bold py-3 rounded-xl text-sm transition disabled:opacity-50"
                  data-testid="totp-submit-btn">
                  {loading ? "Verificando..." : "Confirmar"}
                </button>
                <button type="button" onClick={() => { setStep(1); setTotp(""); }}
                  className="w-full text-xs text-white/50 hover:text-white/80 py-2 transition">
                  Volver
                </button>
              </form>
            </>
          )}
        </div>
        <p className="text-center text-white/30 text-xs mt-6">RODDOS Contable IA © 2025 — Sitio privado</p>
      </div>
    </div>
  );
}
