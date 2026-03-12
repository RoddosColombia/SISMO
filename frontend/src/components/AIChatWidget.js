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
        <div className="w-7 h-7 rounded-full bg-[#0F2A5C] flex items-center justify-center mr-2 flex-shrink-0 mt-0.5">
          <Bot size={13} className="text-white" />
        </div>
      )}
      <div
        className={`max-w-[82%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed
          ${isUser
            ? "bg-[#0F2A5C] text-white rounded-br-sm"
            : msg.isResult
              ? "bg-green-50 border border-green-200 text-green-800 rounded-bl-sm"
              : "bg-white border border-slate-200 text-slate-700 rounded-bl-sm shadow-sm"
          }`}
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>
        <div className={`text-[10px] mt-1 ${isUser ? "text-slate-300" : "text-slate-400"}`}>
          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : ""}
        </div>
      </div>
    </div>
  );
}

function ExecutionCard({ action, onConfirm, onCancel, executing }) {
  if (!action) return null;

  return (
    <div className="mx-3 mb-3 bg-white border-2 border-[#C9A84C] rounded-xl shadow-md overflow-hidden" data-testid="execution-card">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#0F2A5C] to-[#163A7A] px-4 py-2.5 flex items-center gap-2">
        <Play size={13} className="text-[#C9A84C]" />
        <span className="text-xs font-bold text-white uppercase tracking-wide">Listo para ejecutar en Alegra</span>
        <span className="ml-auto text-[10px] text-slate-300">{action.title}</span>
      </div>

      {/* Summary table */}
      {action.summary?.length > 0 && (
        <table className="w-full text-xs border-b border-slate-100">
          <tbody>
            {action.summary.map((item, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-slate-50" : "bg-white"}>
                <td className="px-3 py-1.5 font-semibold text-slate-500 w-1/3">{item.label}</td>
                <td className="px-3 py-1.5 text-slate-800 font-medium">{item.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Actions */}
      <div className="p-3 flex gap-2">
        <Button
          onClick={() => onConfirm(action)}
          disabled={executing}
          className="flex-1 bg-green-600 hover:bg-green-700 text-white text-xs h-9 font-semibold"
          data-testid="confirm-execute-btn"
        >
          {executing ? (
            <><Loader2 size={13} className="mr-1.5 animate-spin" />Ejecutando en Alegra...</>
          ) : (
            <><CheckCircle2 size={13} className="mr-1.5" />Confirmar y ejecutar en Alegra</>
          )}
        </Button>
        <Button
          onClick={onCancel}
          disabled={executing}
          variant="outline"
          className="text-xs h-9 text-red-500 border-red-200 hover:bg-red-50"
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
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, pendingAction, scrollToBottom]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: "assistant",
        content: `Hola ${user?.name?.split(" ")[0] || ""}! Soy tu Agente Contable IA.\n\nEjecuto acciones REALES en Alegra desde la conversación. No necesitas ir a formularios.\n\nEjemplos:\n• "Crea una factura para Colpatria por consultoría $5M"\n• "Causar arrendamiento $3M con ReteFuente a Arrendamientos Premium"\n• "Registrar pago de factura FV-2025-001 de Colpatria"\n• "¿Cuánto es ReteFuente de $8.500.000 en honorarios?"`,
        timestamp: new Date().toISOString(),
      }]);
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
      const successMsg = `✅ ${action.title} ejecutado en Alegra${docId ? ` — ID: ${docId}` : ""}`;
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: successMsg,
        timestamp: new Date().toISOString(),
        isResult: true,
      }]);
      setPendingAction(null);
      toast.success(successMsg);
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
        {isOpen ? <X size={22} className="text-[#0F2A5C]" /> : <MessageSquare size={22} className="text-[#0F2A5C]" />}
      </button>

      {isOpen && (
        <div
          className="fixed bottom-24 right-6 w-[400px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-40 animate-fadeInUp"
          style={{ height: "560px" }}
          data-testid="chat-panel"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#0F2A5C] rounded-t-2xl">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-[#C9A84C] flex items-center justify-center">
                <Bot size={14} className="text-[#0F2A5C]" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">Agente Contable IA</div>
                <div className="text-[10px] text-[#C9A84C]">Ejecuta en Alegra · Claude Sonnet 4.5</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={clearChat} className="text-slate-400 hover:text-white p-1.5 rounded" title="Borrar historial"><Trash2 size={14} /></button>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white p-1.5 rounded"><X size={14} /></button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3" ref={scrollRef}>
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            {loading && (
              <div className="flex justify-start mb-3">
                <div className="w-7 h-7 rounded-full bg-[#0F2A5C] flex items-center justify-center mr-2 flex-shrink-0">
                  <Bot size={13} className="text-white" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin text-[#0F2A5C]" />
                  <span className="text-xs text-slate-500">Analizando en Alegra...</span>
                </div>
              </div>
            )}
            {pendingAction && !loading && (
              <ExecutionCard
                action={pendingAction}
                onConfirm={handleExecute}
                onCancel={handleCancelAction}
                executing={executing}
              />
            )}
          </div>

          {/* Quick prompts */}
          {messages.length <= 1 && (
            <div className="px-3 pb-2">
              <div className="flex flex-wrap gap-1.5">
                {QUICK_PROMPTS.map((p, i) => (
                  <button key={i} onClick={() => setInput(p)} className="text-[10px] bg-[#F0F4FF] text-[#0F2A5C] border border-[#C7D7FF] px-2 py-1 rounded-full hover:bg-[#C9A84C]/20 transition-colors">{p}</button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-3 border-t border-slate-100">
            <div className="flex gap-2">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Crea factura, causar gasto, calcular retención..."
                className="flex-1 min-h-[44px] max-h-[88px] text-sm resize-none border-slate-200 focus:border-[#C9A84C]"
                rows={1}
                data-testid="chat-input"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="bg-[#0F2A5C] hover:bg-[#163A7A] text-white px-3 self-end h-11"
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
