import React, { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, X, Send, Trash2, Bot, Loader2, CheckCircle2, AlertCircle, Play } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { ScrollArea } from "./ui/scroll-area";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { formatCOP } from "../utils/formatters";

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-xl flex items-center justify-center mr-2 flex-shrink-0 mt-0.5"
          style={{ background: "#1A1A1A", border: "1px solid #00E5FF30" }}>
          <Bot size={13} style={{ color: "#00E5FF" }} />
        </div>
      )}
      <div
        className="max-w-[82%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
        style={isUser
          ? { background: "linear-gradient(135deg, #00E5FF, #00C853)", color: "#0D0D0D", borderBottomRightRadius: "4px" }
          : msg.isResult
            ? { background: "#00C85310", border: "1px solid #00C85330", color: "#00C853", borderBottomLeftRadius: "4px" }
            : { background: "#1A1A1A", border: "1px solid #1E1E1E", color: "#E8E8E8", borderBottomLeftRadius: "4px" }
        }
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>
        <div className="text-[10px] mt-1" style={{ color: isUser ? "rgba(13,13,13,0.6)" : "#444" }}>
          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : ""}
        </div>
      </div>
    </div>
  );
}

function ExecutionCard({ action, onConfirm, onCancel, executing }) {
  if (!action) return null;
  return (
    <div className="mx-0 mb-3 rounded-xl overflow-hidden" style={{ border: "1px solid #00E5FF40" }} data-testid="execution-card">
      <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: "#0A0A0A", borderBottom: "1px solid #1E1E1E" }}>
        <Play size={13} style={{ color: "#00E5FF" }} />
        <span className="text-xs font-bold text-white uppercase tracking-wide">Listo para ejecutar en Alegra</span>
        <span className="ml-auto text-[10px]" style={{ color: "#555" }}>{action.title}</span>
      </div>

      {action.summary?.length > 0 && (
        <table className="w-full text-xs" style={{ borderBottom: "1px solid #1E1E1E" }}>
          <tbody>
            {action.summary.map((item, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? "#141414" : "#1A1A1A", borderTop: i > 0 ? "1px solid #1E1E1E" : "none" }}>
                <td className="px-3 py-1.5 font-semibold w-1/3" style={{ color: "#555" }}>{item.label}</td>
                <td className="px-3 py-1.5 font-medium" style={{ color: "#E8E8E8" }}>{item.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="p-3 flex gap-2" style={{ background: "#141414" }}>
        <Button
          onClick={() => onConfirm(action)} disabled={executing}
          className="flex-1 text-xs h-9 font-bold disabled:opacity-40"
          style={{ background: "linear-gradient(135deg, #00E5FF, #00C853)", color: "#0D0D0D" }}
          data-testid="confirm-execute-btn">
          {executing ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Ejecutando...</> : <><CheckCircle2 size={13} className="mr-1.5" />Confirmar y ejecutar</>}
        </Button>
        <Button
          onClick={onCancel}
          disabled={executing}
          variant="outline"
          className="text-xs h-9 font-medium px-3"
          style={{ background: "#1A1A1A", border: "1px solid #FF444430", color: "#FF4444" }}
          data-testid="cancel-execute-btn"
        >
          <X size={12} className="mr-1" />Cancelar
        </Button>
      </div>
    </div>
  );
}

const QUICK_PROMPTS = [
  "¿Cuánto es ReteFuente de $5M en servicios?",
  "Crea factura para Colpatria por consultoría $5M",
  "Causar arrendamiento $3M octubre",
  "¿Cuál es el saldo en mis cuentas?",
];

export default function AIChatWidget() {
  const { api, user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [sessionId] = useState(() => `chat-${user?.id || "guest"}-${Date.now()}`);
  const [memorySuggestions, setMemorySuggestions] = useState([]);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, pendingAction, scrollToBottom]);

  // Load memory suggestions on open
  useEffect(() => {
    if (!isOpen) return;
    const today = new Date();
    const isFirstOfMonth = today.getDate() <= 5;
    if (isFirstOfMonth || messages.length === 0) {
      api.get("/agent/memory/suggestions").then(res => {
        if (res.data?.length > 0) setMemorySuggestions(res.data);
      }).catch(() => {});
    }
    if (messages.length === 0) {
      const greeting = memorySuggestions.length > 0
        ? `Hola ${user?.name?.split(" ")[0] || ""}! Soy tu Agente Contable IA.\n\nDetecté ${memorySuggestions.length} acción(es) recurrente(s) del mes pasado. ¿Las ejecuto este mes?\n\nTambién puedes pedirme cualquier cosa:\n• "Crea factura para [cliente] por $X"\n• "Causar arrendamiento $3M"\n• "¿Cuánto IVA debo este período?"`
        : `Hola ${user?.name?.split(" ")[0] || ""}! Soy tu Agente Contable IA.\n\nEjecuto acciones REALES en Alegra desde la conversación:\n• "Crea una factura para Colpatria por $5M"\n• "Causar arrendamiento $3M con ReteFuente"\n• "¿Cuánto IVA debo este período cuatrimestral?"`;
      setMessages([{ role: "assistant", content: greeting, timestamp: new Date().toISOString() }]);
    }
    if (isOpen && inputRef.current) setTimeout(() => inputRef.current?.focus(), 200);
  }, [isOpen]); // eslint-disable-line

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: "user", content: input.trim(), timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    const sentInput = input;
    setInput("");
    setLoading(true);
    setPendingAction(null);

    try {
      const resp = await api.post("/chat/message", { session_id: sessionId, message: sentInput });
      const { message, pending_action } = resp.data;
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: message,
        timestamp: new Date().toISOString(),
      }]);
      if (pending_action?.type && pending_action?.payload) {
        setPendingAction(pending_action);
      }
    } catch {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Hubo un error procesando tu mensaje. Por favor intenta de nuevo.",
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (action) => {
    setExecuting(true);
    try {
      const resp = await api.post("/chat/execute-action", {
        action: action.type,
        payload: action.payload,
      });
      const docId = resp.data.id || resp.data.result?.id || resp.data.result?.number || "";
      const syncMessages = resp.data.sync?.sync_messages || [];

      // Build rich result message: base + all sync messages
      const baseMsg = `✅ **${action.title}** ejecutado en Alegra${docId ? ` — ID: ${docId}` : ""}`;
      const fullContent = syncMessages.length > 0
        ? `${baseMsg}\n\n**Módulos actualizados:**\n${syncMessages.join("\n")}`
        : baseMsg;

      setMessages((prev) => [...prev, {
        role: "assistant",
        content: fullContent,
        timestamp: new Date().toISOString(),
        isResult: true,
        syncMessages,
      }]);
      setPendingAction(null);
      toast.success(`${action.title} ejecutado correctamente`);
    } catch (e) {
      const errMsg = e.response?.data?.detail || "Error al ejecutar en Alegra";
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `❌ Error: ${errMsg}`,
        timestamp: new Date().toISOString(),
      }]);
      toast.error(errMsg);
    } finally {
      setExecuting(false);
    }
  };

  const handleCancelAction = () => {
    setPendingAction(null);
    setMessages((prev) => [...prev, {
      role: "assistant",
      content: "Acción cancelada. ¿En qué más te puedo ayudar?",
      timestamp: new Date().toISOString(),
    }]);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const clearChat = async () => {
    try {
      await api.delete(`/chat/history/${sessionId}`);
      setMessages([{ role: "assistant", content: "Historial borrado. ¿En qué te puedo ayudar?", timestamp: new Date().toISOString() }]);
      setPendingAction(null);
    } catch { toast.error("Error al borrar historial"); }
  };

  return (
    <>
      <button
        className="chat-float-btn"
        onClick={() => setIsOpen(!isOpen)}
        data-testid="chat-toggle-btn"
        aria-label="Abrir asistente IA"
      >
        {isOpen ? <X size={22} style={{ color: "#0D0D0D" }} /> : <MessageSquare size={22} style={{ color: "#0D0D0D" }} />}
      </button>

      {isOpen && (
        <div
          className="fixed bottom-24 right-6 w-[400px] rounded-2xl shadow-2xl flex flex-col z-40 animate-fadeInUp"
          style={{ height: "560px", background: "#121212", border: "1px solid #1E1E1E", boxShadow: "0 0 40px rgba(0,229,255,0.08)" }}
          data-testid="chat-panel"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 rounded-t-2xl" style={{ background: "#0A0A0A", borderBottom: "1px solid #1E1E1E" }}>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: "linear-gradient(135deg, #00E5FF22, #00C85322)", border: "1px solid #00E5FF44" }}>
                <Bot size={15} style={{ color: "#00E5FF" }} />
              </div>
              <div>
                <div className="text-sm font-bold text-white">Agente Contable IA</div>
                <div className="text-[10px]" style={{ color: "#00C853" }}>Ejecuta en Alegra · Claude Sonnet 4.5</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={clearChat} className="p-1.5 rounded-lg transition" style={{ color: "#444" }}
                onMouseEnter={e => e.currentTarget.style.color = "#888"} onMouseLeave={e => e.currentTarget.style.color = "#444"}
                title="Borrar historial"><Trash2 size={14} /></button>
              <button onClick={() => setIsOpen(false)} className="p-1.5 rounded-lg transition" style={{ color: "#444" }}
                onMouseEnter={e => e.currentTarget.style.color = "#888"} onMouseLeave={e => e.currentTarget.style.color = "#444"}>
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3" ref={scrollRef}>
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}

            {/* Memory suggestions */}
            {memorySuggestions.length > 0 && messages.length <= 1 && (
              <div className="mb-3 rounded-xl p-3" style={{ background: "#1A1A1A", border: "1px solid #00E5FF20" }}>
                <p className="text-[11px] font-bold mb-2" style={{ color: "#00E5FF" }}>Acciones recurrentes del mes pasado:</p>
                <div className="space-y-1.5">
                  {memorySuggestions.slice(0, 3).map((m, i) => (
                    <button key={i}
                      onClick={() => setInput(`Ejecuta igual que el mes pasado: ${m.descripcion}${m.monto ? ` por $${m.monto.toLocaleString("es-CO")}` : ""}`)}
                      className="w-full text-left text-xs rounded-lg px-3 py-2 transition"
                      style={{ background: "#141414", border: "1px solid #2A2A2A", color: "#E8E8E8" }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "#00E5FF50"; e.currentTarget.style.color = "#00E5FF"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "#2A2A2A"; e.currentTarget.style.color = "#E8E8E8"; }}
                      data-testid={`memory-suggestion-${i}`}>
                      <span className="font-semibold">{m.tipo === "crear_causacion" ? "Causación" : m.tipo === "crear_factura_venta" ? "Factura" : "Registro"}</span>
                      {" — "}{m.descripcion}{m.monto ? ` ($${m.monto.toLocaleString("es-CO")})` : ""}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {loading && (
              <div className="flex justify-start mb-3">
                <div className="w-7 h-7 rounded-xl flex items-center justify-center mr-2 flex-shrink-0"
                  style={{ background: "#1A1A1A", border: "1px solid #00E5FF30" }}>
                  <Bot size={13} style={{ color: "#00E5FF" }} />
                </div>
                <div className="rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2"
                  style={{ background: "#1A1A1A", border: "1px solid #1E1E1E" }}>
                  <Loader2 size={14} className="animate-spin" style={{ color: "#00E5FF" }} />
                  <span className="text-xs" style={{ color: "#555" }}>Analizando en Alegra...</span>
                </div>
              </div>
            )}
            {pendingAction && !loading && (
              <ExecutionCard action={pendingAction} onConfirm={handleExecute} onCancel={handleCancelAction} executing={executing} />
            )}
          </div>

          {/* Quick prompts */}
          {messages.length <= 1 && (
            <div className="px-3 pb-2">
              <div className="flex flex-wrap gap-1.5">
                {QUICK_PROMPTS.map((p, i) => (
                  <button key={i} onClick={() => setInput(p)}
                    className="text-[10px] px-2.5 py-1 rounded-full transition font-medium"
                    style={{ background: "#1A1A1A", border: "1px solid #00E5FF25", color: "#888" }}
                    onMouseEnter={e => { e.currentTarget.style.color = "#00E5FF"; e.currentTarget.style.borderColor = "#00E5FF60"; }}
                    onMouseLeave={e => { e.currentTarget.style.color = "#888"; e.currentTarget.style.borderColor = "#00E5FF25"; }}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-3" style={{ borderTop: "1px solid #1E1E1E" }}>
            <div className="flex gap-2">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Crea factura, causar gasto, calcular retención..."
                className="flex-1 min-h-[44px] max-h-[88px] text-sm resize-none"
                style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#E8E8E8" }}
                rows={1}
                data-testid="chat-input"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="px-3 self-end h-11 disabled:opacity-40"
                style={{ background: "linear-gradient(135deg, #00E5FF, #00C853)", color: "#0D0D0D", fontWeight: 700 }}
                data-testid="chat-send-btn"
              >
                <Send size={16} />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
