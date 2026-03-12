import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) { toast.error("Ingresa tu email y contraseña"); return; }
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Bienvenido a RODDOS Contable IA");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Credenciales incorrectas");
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (role) => {
    if (role === "admin") { setEmail("admin@roddos.com"); setPassword("Admin@RODDOS2025!"); }
    else { setEmail("contador@roddos.com"); setPassword("Contador@2025!"); }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel — image */}
      <div
        className="hidden lg:flex lg:w-1/2 relative flex-col justify-end p-12"
        style={{
          background: `linear-gradient(135deg, rgba(15,42,92,0.92) 0%, rgba(10,29,64,0.85) 100%), url('https://images.unsplash.com/photo-1688011852608-dff8cdb43f2d?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200') center/cover no-repeat`,
        }}
      >
        <div className="text-white">
          <div className="text-3xl font-bold font-montserrat mb-3">RODDOS Contable IA</div>
          <div className="text-slate-300 text-base leading-relaxed max-w-sm">
            Asistente de inteligencia artificial especializado en contabilidad colombiana. Integrado directamente con Alegra ERP.
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            {["NIIF Colombia", "Alegra API", "IA Contable", "DIAN 2025"].map(tag => (
              <span key={tag} className="bg-white/10 text-white text-xs px-3 py-1.5 rounded-full border border-white/20 font-medium">{tag}</span>
            ))}
          </div>
        </div>
        <div className="absolute top-8 left-12">
          <div className="text-xl font-bold text-white font-montserrat">RODDOS</div>
          <div className="text-xs text-slate-400">Plataforma Contable Inteligente</div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center bg-[#F8FAFC] p-8">
        <div className="w-full max-w-md animate-fadeInUp">
          <div className="lg:hidden text-center mb-8">
            <div className="text-2xl font-bold text-[#0F2A5C] font-montserrat">RODDOS Contable IA</div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
            <h2 className="text-2xl font-bold text-[#0F2A5C] font-montserrat mb-1">Iniciar sesión</h2>
            <p className="text-sm text-slate-500 mb-8">Accede a tu plataforma contable inteligente</p>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <Label htmlFor="email" className="text-sm font-medium text-slate-700">Correo electrónico</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@empresa.com"
                  className="mt-1.5 h-11"
                  required
                  data-testid="email-input"
                />
              </div>

              <div>
                <Label htmlFor="password" className="text-sm font-medium text-slate-700">Contraseña</Label>
                <div className="relative mt-1.5">
                  <Input
                    id="password"
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="h-11 pr-10"
                    required
                    data-testid="password-input"
                  />
                  <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" onClick={() => setShowPass(!showPass)}>
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 bg-[#0F2A5C] hover:bg-[#163A7A] text-white font-semibold"
                data-testid="login-submit-btn"
              >
                {loading ? <><Loader2 size={16} className="mr-2 animate-spin" /> Ingresando...</> : "Ingresar"}
              </Button>
            </form>

            {/* Demo credentials */}
            <div className="mt-6 pt-5 border-t border-slate-100">
              <p className="text-xs text-center text-slate-500 mb-3 font-medium">ACCESOS DEMO</p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => fillDemo("admin")}
                  className="text-xs py-2 px-3 border border-[#0F2A5C]/30 text-[#0F2A5C] rounded-lg hover:bg-[#F0F4FF] transition-colors font-medium"
                  data-testid="demo-admin-btn"
                >
                  Admin
                </button>
                <button
                  onClick={() => fillDemo("user")}
                  className="text-xs py-2 px-3 border border-[#C9A84C]/50 text-[#8B6F2A] rounded-lg hover:bg-amber-50 transition-colors font-medium"
                  data-testid="demo-user-btn"
                >
                  Contador
                </button>
              </div>
              <p className="text-[10px] text-center text-slate-400 mt-2">Haz clic para pre-rellenar las credenciales demo</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
