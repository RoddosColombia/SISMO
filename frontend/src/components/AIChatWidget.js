import React, { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Trash2, Bot, Loader2, ExternalLink } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ScrollArea } from "./ui/scroll-area";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

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
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed
          ${isUser
            ? "bg-[#0F2A5C] text-white rounded-br-sm"
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

function ActionCard({ action, onConfirm }) {
  if (!action) return null;
  return (
    <div className="mx-3 mb-3 p-3 bg-[#F0F4FF] border border-[#C7D7FF] rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <span className="bg-[#00A9E0] text-white text-[10px] font-bold px-2 py-0.5 rounded-full">ACCIÓN SUGERIDA</span>
        <span className="text-xs font-semibold text-[#0F2A5C]">{action.title}</span>
      </div>
      {action.module && (
        <div className="flex items-center gap-2 mt-2">
          <Button
            size="sm"
            className="text-xs bg-[#0F2A5C] hover:bg-[#163A7A] text-white"
            onClick={() => onConfirm(action)}
            data-testid="chat-action-confirm-btn"
          >
            <ExternalLink size={12} className="mr-1" />
            Ir a {action.title}
          </Button>
        </div>
      )}
    </div>
  );
}

export default function AIChatWidget() {
  const { api, user } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `chat-${user?.id || "guest"}-${Date.now()}`);
  const [lastAction, setLastAction] = useState(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: "assistant",
        content: `Hola, ${user?.name?.split(" ")[0] || ""}! Soy tu asistente contable IA. Puedo ayudarte a registrar facturas, causaciones, calcular retenciones y más.\n\nEjemplos:\n• "Causar arrendamiento $3.000.000 octubre"\n• "¿Cuánto es ReteFuente de $5.000.000 en servicios?"\n• "Crear factura de consultoría para Colpatria por $5.000.000"`,
        timestamp: new Date().toISOString(),
      }]);
    }
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [isOpen]); // eslint-disable-line

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: "user", content: input.trim(), timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    const sentInput = input;
    setInput("");
    setLoading(true);
    setLastAction(null);

    try {
      const resp = await api.post("/chat/message", { session_id: sessionId, message: sentInput });
      const { message, action } = resp.data;
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: message,
        timestamp: new Date().toISOString(),
      }]);
      if (action) setLastAction(action);
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Lo siento, hubo un error al procesar tu mensaje. Por favor intenta de nuevo.",
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleActionConfirm = (action) => {
    if (action.module) {
      navigate(action.module);
      setIsOpen(false);
      toast.info(`Abriendo ${action.title}...`);
    }
  };

  const clearChat = async () => {
    try {
      await api.delete(`/chat/history/${sessionId}`);
      setMessages([{
        role: "assistant",
        content: "Historial borrado. ¿En qué te puedo ayudar?",
        timestamp: new Date().toISOString(),
      }]);
      setLastAction(null);
    } catch {
      toast.error("Error al borrar el historial");
    }
  };

  return (
    <>
      {/* Floating button */}
      <button
        className="chat-float-btn"
        onClick={() => setIsOpen(!isOpen)}
        data-testid="chat-toggle-btn"
        aria-label="Abrir asistente IA"
      >
        {isOpen ? <X size={22} className="text-[#0F2A5C]" /> : <MessageSquare size={22} className="text-[#0F2A5C]" />}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div
          className="fixed bottom-24 right-6 w-[380px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-40 animate-fadeInUp"
          style={{ height: "520px" }}
          data-testid="chat-panel"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#0F2A5C] rounded-t-2xl">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-[#C9A84C] flex items-center justify-center">
                <Bot size={14} className="text-[#0F2A5C]" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">Asistente Contable IA</div>
                <div className="text-[10px] text-slate-400">Claude Sonnet 4.5 · NIIF Colombia</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={clearChat} className="text-slate-400 hover:text-white p-1.5 rounded" title="Borrar historial">
                <Trash2 size={14} />
              </button>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white p-1.5 rounded">
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3" ref={scrollRef}>
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            {loading && (
              <div className="flex justify-start mb-3">
                <div className="w-7 h-7 rounded-full bg-[#0F2A5C] flex items-center justify-center mr-2 flex-shrink-0">
                  <Bot size={13} className="text-white" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm">
                  <Loader2 size={16} className="animate-spin text-[#0F2A5C]" />
                </div>
              </div>
            )}
            {lastAction && !loading && (
              <ActionCard action={lastAction} onConfirm={handleActionConfirm} />
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-100">
            <div className="flex gap-2">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribe tu consulta contable..."
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
            <p className="text-[10px] text-slate-400 mt-1.5 text-center">Enter para enviar · Shift+Enter nueva línea</p>
          </div>
        </div>
      )}
    </>
  );
}
