// @ts-nocheck
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { Eye, EyeOff, Shield } from "lucide-react";

/* Radar "O" — matches RODDOS logo brand mark */
function RadarIcon({ size = 56 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 56 56" fill="none">
      <circle cx="28" cy="28" r="4.5"  stroke="#00E5FF" strokeWidth="2.5" />
      <path d="M28 28 m-9 0 a9 9 0 0 1 9-9"   stroke="#00C853" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M28 28 m-9 0 a9 9 0 0 0 9 9"   stroke="#00E5FF" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M28 28 m-15 0 a15 15 0 0 1 15-15" stroke="#00C853" strokeWidth="1.8" strokeLinecap="round" opacity="0.7" />
      <path d="M28 28 m-15 0 a15 15 0 0 0 15 15" stroke="#00E5FF" strokeWidth="1.8" strokeLinecap="round" opacity="0.7" />
      <path d="M28 28 m-21 0 a21 21 0 0 1 21-21" stroke="#00C853" strokeWidth="1.2" strokeLinecap="round" opacity="0.4" />
      <path d="M28 28 m-21 0 a21 21 0 0 0 21 21" stroke="#00E5FF" strokeWidth="1.2" strokeLinecap="round" opacity="0.4" />
    </svg>
  );
}

export default function Login() {
  const { login, setAuth, token } = useAuth();
  const navigate = useNavigate();
  const [step, setStep]           = useState(1);
  const [form, setForm]           = useState({ email: "", password: "" });
  const [totp, setTotp]           = useState("");
  const [tempToken, setTempToken] = useState("");
  const [showPwd, setShowPwd]     = useState(false);
  const [loading, setLoading]     = useState(false);

  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    if (token) navigate("/agente-contable", { replace: true });
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
        navigate("/agente-contable", { replace: true });
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
      navigate("/agente-contable", { replace: true });
    } catch (err) {
      toast.error(err.message);
      setTotp("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#0D0D0D" }}>
      {/* Background grid pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0" style={{
          backgroundImage: "linear-gradient(rgba(0,229,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,0.03) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }} />
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(0,229,255,0.04) 0%, transparent 70%)" }} />
      </div>

      <div className="relative w-full max-w-sm px-6">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="mb-4 animate-cyan-glow">
            <RadarIcon size={64} />
          </div>
          <h1 className="text-3xl font-black text-white font-montserrat tracking-wider">RODDOS</h1>
          <p className="text-xs font-semibold mt-1.5" style={{ color: "#00E5FF" }}>
            Contable IA — Powered by Alegra
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-7 shadow-2xl" style={{
          background: "#121212",
          border: "1px solid #1E1E1E",
          boxShadow: "0 0 40px rgba(0,229,255,0.06)",
        }}>
          {step === 1 ? (
            <>
              <h2 className="text-base font-bold text-white mb-5">Iniciar Sesión</h2>
              <form onSubmit={handleCredentials} className="space-y-4">
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide mb-1.5 block" style={{ color: "#555" }}>
                    Email
                  </label>
                  <input
                    type="email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-xl px-4 py-3 text-sm transition focus:outline-none"
                    style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#E8E8E8" }}
                    placeholder="tu@email.com"
                    data-testid="login-email-input" autoComplete="email"
                    onFocus={e => e.target.style.borderColor = "#00E5FF"}
                    onBlur={e => e.target.style.borderColor = "#2A2A2A"}
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide mb-1.5 block" style={{ color: "#555" }}>
                    Contraseña
                  </label>
                  <div className="relative">
                    <input
                      type={showPwd ? "text" : "password"} value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      className="w-full rounded-xl px-4 py-3 text-sm transition focus:outline-none pr-10"
                      style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#E8E8E8" }}
                      placeholder="••••••••"
                      data-testid="login-password-input" autoComplete="current-password"
                      onFocus={e => e.target.style.borderColor = "#00E5FF"}
                      onBlur={e => e.target.style.borderColor = "#2A2A2A"}
                    />
                    <button type="button" onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 transition"
                      style={{ color: "#444" }}>
                      {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
                <button
                  type="submit" disabled={loading}
                  className="w-full font-bold py-3 rounded-xl text-sm transition-all disabled:opacity-40 mt-1"
                  style={{
                    background: loading ? "#1A1A1A" : "linear-gradient(135deg, #00E5FF, #00C853)",
                    color: "#0D0D0D",
                    boxShadow: loading ? "none" : "0 4px 20px rgba(0,229,255,0.25)",
                  }}
                  data-testid="login-submit-btn"
                >
                  {loading ? "Verificando..." : "Ingresar"}
                </button>
              </form>

              {/* Demo shortcuts */}
              <div className="mt-5 pt-5" style={{ borderTop: "1px solid #1E1E1E" }}>
                <p className="text-[10px] text-center mb-2.5 uppercase tracking-widest" style={{ color: "#333" }}>
                  Acceso demo
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setForm({ email: "contabilidad@roddos.com", password: "Admin@RODDOS2025!" })}
                    className="text-xs py-2 px-3 rounded-lg font-medium transition"
                    style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#888" }}
                    data-testid="demo-admin-btn"
                  >
                    Contabilidad
                  </button>
                  <button
                    onClick={() => setForm({ email: "compras@roddos.com", password: "Contador@2025!" })}
                    className="text-xs py-2 px-3 rounded-lg font-medium transition"
                    style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#888" }}
                    data-testid="demo-user-btn"
                  >
                    Compras
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-3"
                  style={{ background: "rgba(0,229,255,0.08)", border: "1px solid rgba(0,229,255,0.2)" }}>
                  <Shield size={26} style={{ color: "#00E5FF" }} />
                </div>
                <h2 className="text-base font-bold text-white">Verificación 2FA</h2>
                <p className="text-xs mt-1" style={{ color: "#555" }}>Código de Google Authenticator</p>
              </div>
              <form onSubmit={handleTwoFA} className="space-y-4">
                <input
                  type="text" inputMode="numeric" maxLength={6} value={totp}
                  onChange={(e) => setTotp(e.target.value.replace(/\D/g, ""))}
                  className="w-full rounded-xl px-4 py-4 text-center text-3xl font-mono tracking-[0.5em] focus:outline-none transition"
                  style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#00E5FF",
                    letterSpacing: "0.5em" }}
                  placeholder="000000" autoFocus data-testid="totp-input"
                  onFocus={e => e.target.style.borderColor = "#00E5FF"}
                  onBlur={e => e.target.style.borderColor = "#2A2A2A"}
                />
                <button
                  type="submit" disabled={loading || totp.length !== 6}
                  className="w-full font-bold py-3 rounded-xl text-sm transition-all disabled:opacity-40"
                  style={{
                    background: "linear-gradient(135deg, #00E5FF, #00C853)",
                    color: "#0D0D0D",
                    boxShadow: "0 4px 20px rgba(0,229,255,0.25)",
                  }}
                  data-testid="totp-submit-btn"
                >
                  {loading ? "Verificando..." : "Confirmar"}
                </button>
                <button type="button" onClick={() => { setStep(1); setTotp(""); }}
                  className="w-full text-xs py-2 transition"
                  style={{ color: "#444" }}>
                  Volver
                </button>
              </form>
            </>
          )}
        </div>
        <p className="text-center mt-6 text-[10px] uppercase tracking-widest" style={{ color: "#2A2A2A" }}>
          RODDOS Contable IA © 2025 — Sitio privado
        </p>
      </div>
    </div>
  );
}
