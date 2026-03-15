import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Brain, Send, Trash2, Loader2, Bot, ChevronDown, ChevronRight,
  BookOpen, TrendingUp, Target, Lightbulb, AlertTriangle, CheckCircle2,
  Bookmark,
} from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

function api() {
  const token = localStorage.getItem("token");
  return axios.create({
    baseURL: `${API}/api`,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

const WELCOME_MESSAGE = `Hola. Soy tu CFO Estratégico.

Puedo ayudarte con:
• Analizar y debatir los reportes financieros
• Diseñar estrategias para reducir el déficit
• Simular escenarios financieros ("¿qué pasa si vendo 5 motos esta semana?")
• Evaluar decisiones de inversión o gasto
• Proyectar impuestos y planear el presupuesto
• Aprender tus prioridades y reglas de negocio

Para enseñarme algo permanente:
  "El arriendo es innegociable hasta dic-2026"
  "Provisionar 20% de utilidad para renta"
  "Meta mínima 15 motos/mes"

¿Qué quieres analizar hoy?`;

interface Message {
  role: "user" | "assistant";
  content: string;
  ts: string;
  saved_instruccion?: any;
  saved_compromiso?: any;
}

interface Indicadores {
  recaudo_semanal_base?: number;
  creditos_activos?: number;
  creditos_minimos?: number;
  margen_semanal?: number;
}

function fmt(n: number) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center mt-1"
          style={{ background: "linear-gradient(135deg,#1a3d7a,#0F2A5C)" }}>
          <Brain size={14} className="text-cyan-300" />
        </div>
      )}
      <div className={`max-w-[75%] ${isUser ? "order-first" : ""}`}>
        <div
          className={`rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? "text-white rounded-br-sm"
              : "text-slate-200 rounded-bl-sm"
          }`}
          style={isUser
            ? { background: "#1a3d7a" }
            : { background: "#1a1a2e", border: "1px solid #2a2a4e" }
          }
        >
          {msg.content}
        </div>
        {(msg.saved_instruccion || msg.saved_compromiso) && (
          <div className="mt-1.5 space-y-1">
            {msg.saved_instruccion && (
              <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 bg-emerald-900/30 border border-emerald-700/30 rounded-lg px-2 py-1">
                <Bookmark size={10} />
                Instrucción guardada · {msg.saved_instruccion.categoria}
              </div>
            )}
            {msg.saved_compromiso && (
              <div className="flex items-center gap-1.5 text-[10px] text-blue-400 bg-blue-900/30 border border-blue-700/30 rounded-lg px-2 py-1">
                <Target size={10} />
                Compromiso registrado · meta: {msg.saved_compromiso.meta_numerica} {msg.saved_compromiso.unidad}
              </div>
            )}
          </div>
        )}
        <p className="text-[9px] text-slate-600 mt-1 px-1">{new Date(msg.ts).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}</p>
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center mt-1 bg-slate-700">
          <Bot size={14} className="text-slate-300" />
        </div>
      )}
    </div>
  );
}

function QuickChip({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-[11px] text-slate-400 border border-slate-700 rounded-full px-3 py-1 hover:border-cyan-500 hover:text-cyan-300 transition whitespace-nowrap"
    >
      {text}
    </button>
  );
}

export default function CFOEstrategico() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: WELCOME_MESSAGE, ts: new Date().toISOString() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => `cfo-${Date.now()}`);
  const [indicadores, setIndicadores] = useState<Indicadores>({});
  const [instrucciones, setInstrucciones] = useState<any[]>([]);
  const [showInstrucciones, setShowInstrucciones] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load indicadores
  useEffect(() => {
    api().get("/cfo/indicadores").then(r => setIndicadores(r.data)).catch(() => {});
    api().get("/cfo/instrucciones").then(r => setInstrucciones(r.data.instrucciones || [])).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: text, ts: new Date().toISOString() }]);
    setLoading(true);
    try {
      const resp = await api().post("/cfo/chat/message", { message: text, session_id: sessionId });
      const { message, session_id, saved_instruccion, saved_compromiso } = resp.data;
      if (session_id) setSessionId(session_id);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: message,
        ts: new Date().toISOString(),
        saved_instruccion,
        saved_compromiso,
      }]);
      if (saved_instruccion) {
        setInstrucciones(prev => [saved_instruccion, ...prev]);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Error: ${err.response?.data?.detail || "No se pudo conectar con el CFO Estratégico."}`,
        ts: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, sessionId]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleClear = () => {
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE, ts: new Date().toISOString() }]);
    setSessionId(`cfo-${Date.now()}`);
  };

  const handleDeleteInstruccion = async (id: string) => {
    try {
      await api().delete(`/cfo/instrucciones/${id}`);
      setInstrucciones(prev => prev.filter(i => i.id !== id));
    } catch {}
  };

  const deficit = indicadores.margen_semanal ?? 0;
  const creditos = indicadores.creditos_activos ?? 0;
  const creditosMeta = indicadores.creditos_minimos ?? 45;

  const QUICK_ACTIONS = [
    "¿Cómo atacamos el déficit de $5.8M?",
    "¿Qué pasa si vendo 5 motos esta semana?",
    "¿Debo comprar motos a Auteco ahora?",
    "¿Cuánto IVA debo declarar este cuatrimestre?",
    "¿Cómo va la ejecución del presupuesto?",
    "Meta: vender 15 motos este mes",
  ];

  return (
    <div className="flex flex-col h-full" style={{ background: "#0d0d1a", color: "#e2e8f0" }}>
      {/* Header */}
      <div className="flex-shrink-0 px-5 py-3 border-b flex items-center justify-between"
        style={{ borderColor: "#1e1e3a", background: "#0d0d1a" }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: "linear-gradient(135deg, #1a3d7a, #0d2054)" }}>
            <Brain size={18} className="text-cyan-300" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white">CFO Estratégico RODDOS</h1>
            <p className="text-[10px] text-slate-500">Análisis · Estrategia · Aprendizaje</p>
          </div>
          {/* Dynamic badges */}
          <div className="flex gap-2 ml-2">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${deficit < 0 ? "text-red-400 border-red-700 bg-red-900/20" : "text-emerald-400 border-emerald-700 bg-emerald-900/20"}`}
              data-testid="cfo-deficit-badge">
              Déficit: {fmt(deficit)}/sem
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border text-blue-400 border-blue-700 bg-blue-900/20"
              data-testid="cfo-creditos-badge">
              {creditos}/{creditosMeta} créditos
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowInstrucciones(!showInstrucciones)}
            className="text-[11px] text-slate-400 border border-slate-700 rounded-lg px-2.5 py-1.5 hover:border-cyan-500 hover:text-cyan-300 transition flex items-center gap-1"
            data-testid="toggle-instrucciones-btn"
          >
            <BookOpen size={11} /> {instrucciones.length} reglas
          </button>
          <button onClick={handleClear} className="text-slate-500 hover:text-slate-300 transition p-1.5" title="Nueva sesión">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Instrucciones panel */}
      {showInstrucciones && (
        <div className="flex-shrink-0 border-b px-5 py-3 space-y-1.5 max-h-48 overflow-y-auto"
          style={{ borderColor: "#1e1e3a", background: "#0a0a18" }} data-testid="instrucciones-panel">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-2">Instrucciones estratégicas guardadas</p>
          {instrucciones.length === 0 ? (
            <p className="text-xs text-slate-600">Ninguna instrucción guardada aún. Dime algo como "Aprende que el arriendo es innegociable."</p>
          ) : instrucciones.map((inst, i) => (
            <div key={inst.id || i} className="flex items-start justify-between gap-2 text-[11px] text-slate-300 bg-slate-800/40 border border-slate-700/30 rounded-lg px-2.5 py-1.5" data-testid={`instruccion-item-${i}`}>
              <div>
                <span className="text-[9px] text-cyan-500 font-bold mr-1">[{inst.categoria}]</span>
                {inst.instruccion?.slice(0, 120)}
              </div>
              <button onClick={() => handleDeleteInstruccion(inst.id)} className="text-slate-600 hover:text-red-400 flex-shrink-0">
                <Trash2 size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4" data-testid="cfo-messages-area">
        {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
        {loading && (
          <div className="flex gap-3 mb-4">
            <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
              style={{ background: "linear-gradient(135deg,#1a3d7a,#0F2A5C)" }}>
              <Brain size={14} className="text-cyan-300" />
            </div>
            <div className="flex items-center gap-1.5 px-4 py-3 rounded-xl text-slate-400 text-xs"
              style={{ background: "#1a1a2e", border: "1px solid #2a2a4e" }}>
              <Loader2 size={12} className="animate-spin" />
              Analizando datos reales...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick actions */}
      {messages.length <= 1 && (
        <div className="flex-shrink-0 px-5 pb-3">
          <p className="text-[10px] text-slate-600 mb-2 uppercase tracking-wide">Acciones rápidas</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_ACTIONS.map(q => (
              <QuickChip key={q} text={q} onClick={() => { setInput(q); inputRef.current?.focus(); }} />
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t" style={{ borderColor: "#1e1e3a" }}>
        <div className="flex items-end gap-2 rounded-xl px-3 py-2 border"
          style={{ background: "#12122a", borderColor: "#2a2a4e" }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="¿Qué quieres analizar? · Enter para enviar · Shift+Enter para nueva línea"
            rows={1}
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-600 resize-none outline-none leading-relaxed"
            style={{ maxHeight: "120px" }}
            data-testid="cfo-chat-input"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition disabled:opacity-40"
            style={{ background: input.trim() ? "#1a3d7a" : "#1a1a2e" }}
            data-testid="cfo-send-btn"
          >
            {loading ? <Loader2 size={14} className="animate-spin text-cyan-300" /> : <Send size={14} className="text-cyan-300" />}
          </button>
        </div>
        <p className="text-[9px] text-slate-700 text-center mt-1.5">
          Claude Sonnet · Datos reales de Alegra y loanbooks · Historial independiente del Agente Contador
        </p>
      </div>
    </div>
  );
}
