import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Bot, Send, Trash2, Paperclip, X, Play,
  CheckCircle2, Loader2, FileText, AlertCircle, Zap
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";

/* ── constants ── */
const fmt = (n) => Number(n || 0).toLocaleString("es-CO");

const TIPO_LABELS = {
  factura_compra: "Factura de Compra",
  factura_venta: "Factura de Venta",
  recibo_pago: "Recibo de Pago",
  comprobante_egreso: "Comprobante de Egreso",
  extracto_bancario: "Extracto Bancario",
  otro: "Documento",
};

const QUICK_PROMPTS = [
  "¿Cuánto IVA debo este período?",
  "Crea factura para Colpatria $5M",
  "Causar arrendamiento $3M octubre",
  "¿Cuánto ReteFuente de $5M en servicios?",
];

/* ── sub-components ── */

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="w-7 h-7 rounded-xl flex items-center justify-center mr-2 flex-shrink-0 mt-0.5"
        style={{ background: "#EFF6FF", border: "1px solid #BFDBFE" }}>
        <Bot size={13} style={{ color: "#00C4D4" }} />
      </div>
      <div className="rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5"
        style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}>
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 rounded-full animate-bounce"
            style={{ background: "#94A3B8", animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  if (msg.isInternal) return null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-xl flex items-center justify-center mr-2 flex-shrink-0 mt-0.5"
          style={{ background: "#EFF6FF", border: "1px solid #BFDBFE" }}>
          <Bot size={13} style={{ color: "#00C4D4" }} />
        </div>
      )}
      <div
        className="max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
        style={
          isUser
            ? { background: "linear-gradient(135deg, #00C4D4, #00C853)", color: "#fff", borderBottomRightRadius: "4px" }
            : msg.isResult
            ? { background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#166534", borderBottomLeftRadius: "4px" }
            : { background: "#FFFFFF", border: "1px solid #E2E8F0", color: "#334155", borderBottomLeftRadius: "4px" }
        }
      >
        {msg.file && (
          <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-lg"
            style={{ background: isUser ? "rgba(255,255,255,0.2)" : "#F8FAFC", border: "1px solid rgba(0,0,0,0.06)" }}>
            {msg.file.preview
              ? <img src={msg.file.preview} alt={msg.file.name} className="w-8 h-8 rounded object-cover" />
              : <FileText size={14} style={{ color: isUser ? "#fff" : "#00C4D4" }} />
            }
            <span className="text-xs font-medium truncate max-w-[180px]">{msg.file.name}</span>
          </div>
        )}

        {isUser ? (
          <div className="whitespace-pre-wrap">{msg.content}</div>
        ) : (
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              strong: ({ children }) => <strong className="font-bold" style={{ color: "#0369A1" }}>{children}</strong>,
              em: ({ children }) => <em className="italic text-slate-500">{children}</em>,
              ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              h1: ({ children }) => <p className="font-bold text-sm mb-1 text-slate-800">{children}</p>,
              h2: ({ children }) => <p className="font-bold text-xs mb-1 uppercase tracking-wide text-slate-700">{children}</p>,
              h3: ({ children }) => <p className="font-semibold text-xs mb-1 text-slate-600">{children}</p>,
              pre: ({ children }) => <pre className="p-2 rounded text-[11px] font-mono overflow-x-auto mt-1 mb-2 bg-slate-100 text-slate-800">{children}</pre>,
              code: ({ children }) => <code className="px-1 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-800">{children}</code>,
              table: ({ children }) => (
                <div className="overflow-x-auto my-2">
                  <table className="w-full text-xs border-collapse border border-slate-200">{children}</table>
                </div>
              ),
              th: ({ children }) => <th className="px-2 py-1 text-left font-semibold bg-slate-50 text-slate-600 border border-slate-200">{children}</th>,
              td: ({ children }) => <td className="px-2 py-1 border border-slate-200 text-slate-700">{children}</td>,
              blockquote: ({ children }) => <blockquote className="border-l-2 pl-3 my-2 italic text-slate-500 border-sky-400">{children}</blockquote>,
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}

        <div className="text-[10px] mt-1.5" style={{ color: isUser ? "rgba(255,255,255,0.6)" : "#CBD5E1" }}>
          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : ""}
        </div>
      </div>
    </div>
  );
}

function ExecutionCard({ action, onConfirm, onCancel, executing }) {
  if (!action) return null;
  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm" style={{ border: "1px solid #E2E8F0" }} data-testid="execution-card">
      <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: "#F8FAFC", borderBottom: "1px solid #E2E8F0" }}>
        <Play size={12} className="text-sky-600" />
        <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">Listo para ejecutar en Alegra</span>
        <span className="ml-auto text-[10px] text-slate-400">{action.title}</span>
      </div>
      {action.summary?.length > 0 && (
        <table className="w-full text-xs" style={{ borderBottom: "1px solid #E2E8F0" }}>
          <tbody>
            {action.summary.map((item, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? "#FFFFFF" : "#F8FAFC" }}>
                <td className="px-3 py-1.5 font-semibold text-slate-400 w-1/3">{item.label}</td>
                <td className="px-3 py-1.5 font-medium text-slate-700">{item.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="p-3 flex gap-2 bg-white">
        <Button onClick={() => onConfirm(action)} disabled={executing}
          className="flex-1 text-xs h-9 font-bold disabled:opacity-40"
          style={{ background: "linear-gradient(135deg, #00C4D4, #00C853)", color: "#fff" }}
          data-testid="confirm-execute-btn">
          {executing
            ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Ejecutando...</>
            : <><CheckCircle2 size={13} className="mr-1.5" />Confirmar y ejecutar</>}
        </Button>
        <Button onClick={onCancel} disabled={executing} variant="outline"
          className="text-xs h-9 px-3 font-medium border-red-200 text-red-500 hover:bg-red-50"
          data-testid="cancel-execute-btn">
          <X size={12} className="mr-1" />Cancelar
        </Button>
      </div>
    </div>
  );
}

function DocumentProposalCard({ proposal, onConfirm, onCancel, loading }) {
  const [data, setData] = useState({ ...proposal });
  const update = (k, v) => setData((p) => ({ ...p, [k]: v }));
  const calcTotal = Number(data.subtotal || 0) + Number(data.iva_valor || 0) - Number(data.retefuente_valor || 0);

  const fieldCls = "w-full text-xs px-3 py-2 rounded-lg outline-none border border-slate-200 bg-white text-slate-700 focus:ring-2 focus:ring-sky-200 focus:border-sky-400 transition";
  const labelCls = "text-[10px] font-bold uppercase tracking-wide mb-1 block text-slate-400";

  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm" style={{ border: "1px solid #E2E8F0" }} data-testid="document-proposal-card">
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-2 flex-wrap bg-slate-50" style={{ borderBottom: "1px solid #E2E8F0" }}>
        <FileText size={13} className="text-sky-600" />
        <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">Comprobante Analizado</span>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-50 text-sky-700 border border-sky-200">
          {TIPO_LABELS[data.tipo_documento] || data.tipo_documento}
        </span>
        {data.es_pago_loanbook && (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Cuota Loanbook {data.loanbook_codigo || ""}
          </span>
        )}
        {data.ilegible && (
          <span className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertCircle size={10} />Datos incompletos
          </span>
        )}
      </div>

      {/* Fields */}
      <div className="p-4 space-y-3 bg-white">
        <div>
          <label className={labelCls}>Proveedor / Cliente</label>
          <input value={data.proveedor_cliente || ""} onChange={(e) => update("proveedor_cliente", e.target.value)}
            className={fieldCls} data-testid="proposal-proveedor" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>NIT / Cédula</label>
            <input value={data.nit || ""} onChange={(e) => update("nit", e.target.value)}
              className={fieldCls} data-testid="proposal-nit" />
          </div>
          <div>
            <label className={labelCls}>Fecha</label>
            <input type="date" value={data.fecha || ""} onChange={(e) => update("fecha", e.target.value)}
              className={fieldCls} data-testid="proposal-fecha" />
          </div>
        </div>

        <div>
          <label className={labelCls}>N° Documento</label>
          <input value={data.numero_documento || ""} onChange={(e) => update("numero_documento", e.target.value)}
            className={fieldCls} placeholder="Número de factura o recibo" data-testid="proposal-numero" />
        </div>

        <div>
          <label className={labelCls}>Concepto</label>
          <textarea value={data.concepto || ""} onChange={(e) => update("concepto", e.target.value)}
            rows={2} className={`${fieldCls} resize-none`} data-testid="proposal-concepto" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Subtotal $</label>
            <input type="number" value={data.subtotal || 0} onChange={(e) => update("subtotal", Number(e.target.value))}
              className={fieldCls} data-testid="proposal-subtotal" />
          </div>
          <div>
            <label className={labelCls}>IVA {data.iva_porcentaje ? `(${data.iva_porcentaje}%)` : ""} $</label>
            <input type="number" value={data.iva_valor || 0} onChange={(e) => update("iva_valor", Number(e.target.value))}
              className={fieldCls} data-testid="proposal-iva" />
          </div>
          <div>
            <label className={labelCls}>ReteFuente {data.retefuente_tipo !== "ninguna" ? `(${data.retefuente_tipo || ""})` : ""} $</label>
            <input type="number" value={data.retefuente_valor || 0} onChange={(e) => update("retefuente_valor", Number(e.target.value))}
              className={fieldCls} data-testid="proposal-retefuente" />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wide mb-1 block text-sky-600">TOTAL $</label>
            <div className="text-sm font-bold px-3 py-2 rounded-lg bg-sky-50 border border-sky-200 text-sky-700" data-testid="proposal-total">
              {fmt(calcTotal)}
            </div>
          </div>
        </div>

        {data.cuenta_gasto_nombre && (
          <div className="px-3 py-2 rounded-lg text-xs bg-slate-50 border border-slate-200 text-slate-500">
            Cuenta sugerida: [{data.cuenta_gasto_id}] {data.cuenta_gasto_nombre}
          </div>
        )}

        {data.campos_faltantes?.length > 0 && (
          <div className="px-3 py-2 rounded-lg text-xs bg-amber-50 border border-amber-200 text-amber-700">
            Campos sin leer: {data.campos_faltantes.join(", ")} — complete manualmente
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 flex gap-2 bg-slate-50" style={{ borderTop: "1px solid #E2E8F0" }}>
        <Button onClick={() => onConfirm({ ...data, total: calcTotal })} disabled={loading}
          className="flex-1 text-xs h-9 font-bold disabled:opacity-40"
          style={{ background: "linear-gradient(135deg, #00C4D4, #00C853)", color: "#fff" }}
          data-testid="proposal-confirm-btn">
          {loading
            ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Registrando...</>
            : <><CheckCircle2 size={13} className="mr-1.5" />Confirmar y registrar</>}
        </Button>
        <Button onClick={onCancel} disabled={loading} variant="outline"
          className="text-xs h-9 px-3 font-medium border-red-200 text-red-500 hover:bg-red-50"
          data-testid="proposal-cancel-btn">
          <X size={12} className="mr-1" />Cancelar
        </Button>
      </div>
    </div>
  );
}

/* ── main page ── */
export default function AgentChatPage() {
  const { api, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [documentProposal, setDocumentProposal] = useState(null);
  const [attachedFile, setAttachedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [memorySuggestions, setMemorySuggestions] = useState([]);

  const sessionId = useRef(`chat-main-${user?.id || "guest"}`).current;
  const messagesRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const initialLoadDone = useRef(false);

  /* scroll to bottom */
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages, loading, documentProposal, pendingAction]);

  /* load history or show welcome */
  useEffect(() => {
    if (initialLoadDone.current) return;
    initialLoadDone.current = true;

    const init = async () => {
      let suggestions = [];
      try {
        const res = await api.get("/agent/memory/suggestions");
        suggestions = res.data || [];
        if (suggestions.length > 0) setMemorySuggestions(suggestions);
      } catch {}

      try {
        const hist = await api.get(`/chat/history/${sessionId}`);
        if (hist.data?.length > 0) {
          setMessages(hist.data.filter((m) => m.role !== "system").map((m) => ({
            role: m.role, content: m.content, timestamp: m.timestamp,
          })));
          return;
        }
      } catch {}

      const name = user?.name?.split(" ")[0] || "";
      const greeting = suggestions.length > 0
        ? `Hola ${name}! Soy tu Agente Contable IA de RODDOS.\n\nDetecté ${suggestions.length} acción(es) recurrente(s) del mes pasado. ¿Las ejecuto este mes?\n\nTambién puedes adjuntar comprobantes PDF o imágenes para registrarlos automáticamente.`
        : `Hola ${name}! Soy tu Agente Contable IA de RODDOS.\n\nEjecuto acciones REALES en Alegra directamente desde aquí:\n• Crear facturas de venta y compra\n• Causar egresos e ingresos con asientos NIIF\n• Registrar pagos y cuotas de cartera\n• Analizar comprobantes — adjunta PDF o imagen (📎, arrastra o Ctrl+V)\n\nDime qué necesitas o adjunta un documento para comenzar.`;

      setMessages([{ role: "assistant", content: greeting, timestamp: new Date().toISOString() }]);
    };

    init();
  }, []); // eslint-disable-line

  /* document-level paste for images */
  useEffect(() => {
    const onPaste = (e) => {
      if (attachedFile) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) handleFileAttach(file);
          break;
        }
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [attachedFile]); // eslint-disable-line

  /* file helpers */
  const fileToBase64 = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const handleFileAttach = useCallback(async (file) => {
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "application/pdf"];
    if (file.size > 20 * 1024 * 1024) { toast.error("El archivo no puede superar 20MB"); return; }
    if (!allowed.includes(file.type)) { toast.error("Solo imágenes (JPG, PNG, WebP) y PDF"); return; }
    try {
      const base64 = await fileToBase64(file);
      const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
      setAttachedFile({ base64, name: file.name, type: file.type, preview });
      inputRef.current?.focus();
    } catch { toast.error("Error al procesar el archivo"); }
  }, []);

  /* drag & drop */
  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault(); setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileAttach(file);
  };

  /* send message */
  const handleSend = async () => {
    if ((!input.trim() && !attachedFile) || loading) return;

    const sentInput = input.trim();
    const sentFile = attachedFile;
    setMessages((prev) => [...prev, {
      role: "user", content: sentInput || "Analizar este documento", timestamp: new Date().toISOString(),
      file: sentFile ? { name: sentFile.name, type: sentFile.type, preview: sentFile.preview } : null,
    }]);
    setInput(""); setAttachedFile(null); setLoading(true);
    setDocumentProposal(null); setPendingAction(null);

    try {
      const payload = {
        session_id: sessionId,
        message: sentInput || "Analiza este comprobante contable y extrae los datos para su registro en Alegra.",
        ...(sentFile ? { file_content: sentFile.base64, file_name: sentFile.name, file_type: sentFile.type } : {}),
      };
      const resp = await api.post("/chat/message", payload);
      const { message, pending_action, document_proposal } = resp.data;
      setMessages((prev) => [...prev, { role: "assistant", content: message, timestamp: new Date().toISOString() }]);
      if (document_proposal) setDocumentProposal(document_proposal);
      else if (pending_action?.type && pending_action?.payload) setPendingAction(pending_action);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Hubo un error. Por favor intenta de nuevo.", timestamp: new Date().toISOString() }]);
    } finally { setLoading(false); }
  };

  /* confirm document proposal */
  const handleConfirmProposal = async (confirmedProposal) => {
    setDocumentProposal(null); setConfirming(true);

    const lines = [
      "CONFIRMAR EJECUCIÓN — Comprobante contable verificado por el usuario:",
      `Tipo: ${TIPO_LABELS[confirmedProposal.tipo_documento] || confirmedProposal.tipo_documento}`,
      confirmedProposal.proveedor_cliente && `Proveedor/Cliente: ${confirmedProposal.proveedor_cliente}${confirmedProposal.nit ? ` (NIT: ${confirmedProposal.nit})` : ""}`,
      confirmedProposal.fecha && `Fecha: ${confirmedProposal.fecha}`,
      confirmedProposal.numero_documento && `N° Documento: ${confirmedProposal.numero_documento}`,
      `Concepto: ${confirmedProposal.concepto}`,
      `Subtotal: $${fmt(confirmedProposal.subtotal)}`,
      Number(confirmedProposal.iva_valor) > 0 && `IVA ${confirmedProposal.iva_porcentaje || 19}%: $${fmt(confirmedProposal.iva_valor)}`,
      Number(confirmedProposal.retefuente_valor) > 0 && `ReteFuente (${confirmedProposal.retefuente_tipo}): $${fmt(confirmedProposal.retefuente_valor)}`,
      `Total: $${fmt(confirmedProposal.total)}`,
      confirmedProposal.cuenta_gasto_id && `Cuenta contable: [${confirmedProposal.cuenta_gasto_id}] ${confirmedProposal.cuenta_gasto_nombre}`,
      "",
      `Acción: ${confirmedProposal.accion_contable}`,
      "Genera el bloque <action> completo con payload correcto para Alegra.",
    ].filter(Boolean).join("\n");

    setMessages((prev) => [...prev, { role: "user", content: "Confirmando datos del comprobante...", timestamp: new Date().toISOString(), isInternal: true }]);
    setLoading(true);

    try {
      const resp = await api.post("/chat/message", { session_id: sessionId, message: lines });
      const { message, pending_action } = resp.data;
      setMessages((prev) => [...prev, { role: "assistant", content: message, timestamp: new Date().toISOString() }]);

      if (pending_action?.type && pending_action?.payload) {
        setExecuting(true);
        try {
          const execResp = await api.post("/chat/execute-action", { action: pending_action.type, payload: pending_action.payload });
          const docId = execResp.data.id || execResp.data.result?.id || "";
          const syncMsgs = execResp.data.sync?.sync_messages || [];
          const full = `Comprobante registrado en Alegra${docId ? ` — ID: ${docId}` : ""}${syncMsgs.length > 0 ? `\n\nMódulos actualizados:\n${syncMsgs.join("\n")}` : ""}`;
          setMessages((prev) => [...prev, { role: "assistant", content: full, timestamp: new Date().toISOString(), isResult: true }]);
          toast.success("Comprobante registrado en Alegra");
        } catch (e) {
          const errMsg = e.response?.data?.detail || "Error al ejecutar en Alegra";
          setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${errMsg}`, timestamp: new Date().toISOString() }]);
          toast.error(errMsg);
        } finally { setExecuting(false); }
      }
    } catch { toast.error("Error al procesar la confirmación"); }
    finally { setLoading(false); setConfirming(false); }
  };

  const handleExecute = async (action) => {
    setExecuting(true);
    try {
      const resp = await api.post("/chat/execute-action", { action: action.type, payload: action.payload });
      const docId = resp.data.id || resp.data.result?.id || "";
      const syncMsgs = resp.data.sync?.sync_messages || [];
      const full = `${action.title} ejecutado en Alegra${docId ? ` — ID: ${docId}` : ""}${syncMsgs.length > 0 ? `\n\nMódulos actualizados:\n${syncMsgs.join("\n")}` : ""}`;
      setMessages((prev) => [...prev, { role: "assistant", content: full, timestamp: new Date().toISOString(), isResult: true }]);
      setPendingAction(null);
      toast.success(`${action.title} ejecutado correctamente`);
    } catch (e) {
      const errMsg = e.response?.data?.detail || "Error al ejecutar en Alegra";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${errMsg}`, timestamp: new Date().toISOString() }]);
      toast.error(errMsg);
    } finally { setExecuting(false); }
  };

  const handleCancelAction = () => {
    setPendingAction(null);
    setMessages((prev) => [...prev, { role: "assistant", content: "Acción cancelada. ¿En qué más te puedo ayudar?", timestamp: new Date().toISOString() }]);
  };

  const clearChat = async () => {
    try {
      await api.delete(`/chat/history/${sessionId}`);
      setMessages([{ role: "assistant", content: "Historial borrado. ¿En qué te puedo ayudar?", timestamp: new Date().toISOString() }]);
      setPendingAction(null); setDocumentProposal(null);
    } catch { toast.error("Error al borrar historial"); }
  };

  const handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const showQuickPrompts = messages.length <= 1 && !loading;

  return (
    <div className="h-full flex flex-col relative" style={{ background: "#F8FAFC" }}
      onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
      data-testid="agent-chat-page">

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(255,255,255,0.92)", border: "2px dashed #00C4D4", backdropFilter: "blur(4px)" }}>
          <div className="text-center select-none">
            <Paperclip size={36} className="text-sky-500 mx-auto mb-3" />
            <p className="text-base font-bold text-sky-600">Suelta para adjuntar</p>
            <p className="text-xs mt-1 text-slate-400">PDF o imagen</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 flex-shrink-0 bg-white"
        style={{ borderBottom: "1px solid #E2E8F0" }} data-testid="chat-header">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: "linear-gradient(135deg, #EFF6FF, #F0FDFA)", border: "1px solid #BAE6FD" }}>
            <Bot size={17} className="text-sky-500" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-800">Agente Contable IA</div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] text-emerald-600">Claude Sonnet 4.5 · Alegra conectado</span>
            </div>
          </div>
        </div>
        <button onClick={clearChat} className="p-2 rounded-lg hover:bg-slate-100 transition text-slate-400"
          title="Borrar historial" data-testid="clear-chat-btn">
          <Trash2 size={15} />
        </button>
      </div>

      {/* Messages */}
      <div ref={messagesRef} className="flex-1 overflow-y-auto px-5 py-5" data-testid="chat-messages">
        {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}

        {/* Memory suggestions */}
        {memorySuggestions.length > 0 && messages.length <= 1 && (
          <div className="mb-4 rounded-xl p-3 bg-white border border-slate-200 shadow-sm">
            <p className="text-[11px] font-bold mb-2.5 flex items-center gap-1.5 text-sky-600">
              <Zap size={11} />Acciones recurrentes del mes pasado:
            </p>
            <div className="space-y-1.5">
              {memorySuggestions.slice(0, 3).map((m, i) => (
                <button key={i}
                  onClick={() => setInput(`Ejecuta igual que el mes pasado: ${m.descripcion}${m.monto ? ` por $${m.monto.toLocaleString("es-CO")}` : ""}`)}
                  className="w-full text-left text-xs rounded-lg px-3 py-2 bg-slate-50 border border-slate-200 text-slate-700 hover:bg-sky-50 hover:border-sky-200 transition"
                  data-testid={`memory-suggestion-${i}`}>
                  <span className="font-semibold text-sky-600">
                    {m.tipo === "crear_causacion" ? "Causación" : m.tipo === "crear_factura_venta" ? "Factura" : "Registro"}
                  </span>
                  {" — "}{m.descripcion}{m.monto ? ` ($${m.monto.toLocaleString("es-CO")})` : ""}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && <TypingIndicator />}

        {documentProposal && !loading && (
          <DocumentProposalCard proposal={documentProposal}
            onConfirm={handleConfirmProposal}
            onCancel={() => { setDocumentProposal(null); setMessages((prev) => [...prev, { role: "assistant", content: "Propuesta cancelada. ¿En qué más te puedo ayudar?", timestamp: new Date().toISOString() }]); }}
            loading={confirming || executing}
          />
        )}

        {pendingAction && !loading && (
          <ExecutionCard action={pendingAction} onConfirm={handleExecute}
            onCancel={handleCancelAction} executing={executing} />
        )}
      </div>

      {/* Quick prompts */}
      {showQuickPrompts && (
        <div className="px-5 pb-3">
          <div className="flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((p, i) => (
              <button key={i}
                onClick={() => { setInput(p); inputRef.current?.focus(); }}
                className="text-[11px] px-3 py-1.5 rounded-full font-medium transition bg-white border border-slate-200 text-slate-500 hover:bg-sky-50 hover:border-sky-300 hover:text-sky-600">
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="flex-shrink-0 bg-white" style={{ borderTop: "1px solid #E2E8F0" }}>
        {/* File preview */}
        {attachedFile && (
          <div className="px-4 pt-3 pb-1">
            <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-50 border border-sky-200"
              data-testid="file-preview-strip">
              {attachedFile.preview
                ? <img src={attachedFile.preview} alt={attachedFile.name} className="w-8 h-8 rounded object-cover" />
                : <FileText size={16} className="text-sky-500" />
              }
              <span className="text-xs font-medium max-w-[200px] truncate text-slate-700">{attachedFile.name}</span>
              <button onClick={() => setAttachedFile(null)} className="hover:opacity-60 transition text-slate-400"
                data-testid="remove-file-btn">
                <X size={13} />
              </button>
            </div>
          </div>
        )}

        <div className="p-4 flex items-end gap-2">
          <button onClick={() => fileInputRef.current?.click()}
            className="p-2.5 rounded-lg transition flex-shrink-0 bg-slate-50 border border-slate-200 text-slate-400 hover:text-sky-500 hover:bg-sky-50 hover:border-sky-300"
            title="Adjuntar PDF o imagen (o arrastra / Ctrl+V)" data-testid="file-attach-btn">
            <Paperclip size={17} />
          </button>
          <input ref={fileInputRef} type="file" hidden
            accept="image/jpeg,image/jpg,image/png,image/gif,image/webp,application/pdf"
            onChange={(e) => { const f = e.target.files[0]; if (f) handleFileAttach(f); e.target.value = ""; }} />

          <Textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe un mensaje o adjunta un comprobante (📎, arrastra o Ctrl+V)..."
            rows={1} className="flex-1 min-h-[44px] max-h-[120px] text-sm resize-none border-slate-200"
            style={{ borderRadius: "10px" }} data-testid="chat-input" />

          <Button onClick={handleSend} disabled={(!input.trim() && !attachedFile) || loading}
            className="px-3.5 self-end h-11 flex-shrink-0 disabled:opacity-40 rounded-xl font-bold"
            style={{ background: "linear-gradient(135deg, #00C4D4, #00C853)", color: "#fff" }}
            data-testid="chat-send-btn">
            <Send size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
