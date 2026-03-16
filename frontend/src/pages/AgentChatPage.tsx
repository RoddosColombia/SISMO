import React, { useState, useRef, useEffect, useCallback } from "react";
import { Bot, Send, Trash2, Paperclip, X, Play,
  CheckCircle2, Loader2, FileText, AlertCircle, Zap,
  Bike, CreditCard, Receipt, ScanLine, UserPlus, ArrowRight,
  Download, Sheet
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
import ReactMarkdown from "react-markdown";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";

/* ── types ── */
interface AttachedFileInfo { name: string; type: string; preview: string | null; }

interface PlExportCardData {
  type: "pl_export_card";
  titulo: string;
  periodo: string;
  periodo_label: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  isInternal?: boolean;
  isResult?: boolean;
  file?: AttachedFileInfo | null;
  docTypeLabel?: string | null;
}

// TODO: type - payload structure varies by action type (journal entries, bill, invoice, tercero)
interface PendingAction {
  type: string;
  title: string;
  summary?: Array<{ label: string; value: string }>;
  payload?: Record<string, any>;
}

interface DocumentProposalData {
  tipo_documento?: string;
  proveedor_cliente?: string;
  nit?: string;
  fecha?: string;
  numero_documento?: string;
  concepto?: string;
  subtotal?: number;
  iva_valor?: number;
  iva_porcentaje?: number;
  retefuente_valor?: number;
  retefuente_tipo?: string;
  total?: number;
  cuenta_gasto_id?: string;
  cuenta_gasto_nombre?: string;
  campos_faltantes?: string[];
  es_pago_loanbook?: boolean;
  loanbook_codigo?: string;
  ilegible?: boolean;
  accion_contable?: string;
}

interface AttachedFile { base64: string; name: string; type: string; preview: string | null; }
interface MemorySuggestion { tipo?: string; descripcion?: string; monto?: number; }

interface TareaActiva {
  estado: "en_curso" | "pausada" | "completada" | "ninguna";
  descripcion?: string;
  pasos_total?: number;
  pasos_completados?: number;
  pasos_pendientes?: string[];
}

/* ── constants ── */
const fmt = (n: number | string | null | undefined): string => Number(n || 0).toLocaleString("es-CO");

const DOC_TYPE_OPTIONS = [
  {
    value: "auto",
    label: "Auto-detectar",
    icon: ScanLine,
    hint: "",
    color: null,
  },
  {
    value: "servicio",
    label: "Factura servicio",
    icon: Receipt,
    hint: "TIPO_DOCUMENTO_INDICADO: Factura de servicio (honorarios, arrendamiento, utilities, asesoría). Acción correcta: crear_causacion con asiento débito cuenta gasto + crédito cuentas por pagar + retenciones aplicables.\n",
    color: "#7C3AED",
  },
  {
    value: "producto",
    label: "Compra motos/productos",
    icon: Bike,
    hint: "TIPO_DOCUMENTO_INDICADO: Factura de compra de productos físicos o motos del inventario. Acción correcta: registrar_factura_compra con purchases.items usando IDs del catálogo Alegra.\n",
    color: "#0369A1",
  },
  {
    value: "pago",
    label: "Pago / Cuota",
    icon: CreditCard,
    hint: "TIPO_DOCUMENTO_INDICADO: Comprobante de pago o transferencia bancaria. Detectar si es cuota de Loanbook RODDOS. Acción correcta: registrar_pago o registrar cuota de Loanbook.\n",
    color: "#047857",
  },
];

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

function TypingIndicator(): React.ReactElement {
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

function MessageBubble({ msg }: { msg: Message }): React.ReactElement | null {
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
            {msg.docTypeLabel && (
              <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0"
                style={{ background: "rgba(255,255,255,0.25)", color: isUser ? "#fff" : "#0369A1" }}>
                {msg.docTypeLabel}
              </span>
            )}
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

function ExecutionCard({ action, onConfirm, onCancel, executing }: {
  action: PendingAction | null;
  onConfirm: (action: PendingAction) => void;
  onCancel: () => void;
  executing: boolean;
}): React.ReactElement | null {
  if (!action) return null;

  /* ── helpers ── */
  const fmtCOP = (n) => n ? `$ ${Number(n).toLocaleString("es-CO")}` : "—";
  const entries = action.payload?.entries || [];
  const totalDeb = entries.reduce((s, e) => s + Number(e.debit || 0), 0);
  const totalCre = entries.reduce((s, e) => s + Number(e.credit || 0), 0);
  const isJournal = action.type === "crear_causacion" && entries.length > 0;

  const billItems = action.payload?.purchases?.items || [];
  const isBill = action.type === "registrar_factura_compra" && billItems.length > 0;

  const invoiceItems = action.payload?.items || [];
  const isInvoice = action.type === "crear_factura_venta" && invoiceItems.length > 0;

  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm" style={{ border: "1px solid #E2E8F0" }} data-testid="execution-card">
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: "#F8FAFC", borderBottom: "1px solid #E2E8F0" }}>
        <Play size={12} className="text-sky-600" />
        <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">Listo para ejecutar en Alegra</span>
        <span className="ml-auto text-[10px] text-slate-400">{action.title}</span>
      </div>

      {/* Summary key-value table */}
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

      {/* Debit/Credit journal table */}
      {isJournal && (
        <div style={{ borderBottom: "1px solid #E2E8F0" }}>
          <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Asiento Contable</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "#F1F5F9" }}>
                <th className="px-3 py-1.5 text-left font-bold text-slate-500 text-[10px] w-1/2">Cuenta</th>
                <th className="px-3 py-1.5 text-right font-bold text-slate-500 text-[10px] w-1/4">Débito</th>
                <th className="px-3 py-1.5 text-right font-bold text-slate-500 text-[10px] w-1/4">Crédito</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#F8FAFC", borderTop: "1px solid #F1F5F9" }}>
                  <td className="px-3 py-1.5 text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400 mr-1">{e.id}</span>
                    {e.name || ""}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium" style={{ color: Number(e.debit) > 0 ? "#0369A1" : "#CBD5E1" }}>
                    {Number(e.debit) > 0 ? fmtCOP(e.debit) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium" style={{ color: Number(e.credit) > 0 ? "#047857" : "#CBD5E1" }}>
                    {Number(e.credit) > 0 ? fmtCOP(e.credit) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ background: "#F1F5F9", borderTop: "2px solid #E2E8F0" }}>
                <td className="px-3 py-1.5 font-bold text-slate-600 text-[10px] uppercase tracking-wide">Totales</td>
                <td className="px-3 py-1.5 text-right font-bold text-sky-700 text-xs">{fmtCOP(totalDeb)}</td>
                <td className="px-3 py-1.5 text-right font-bold text-emerald-700 text-xs">{fmtCOP(totalCre)}</td>
              </tr>
            </tfoot>
          </table>
          {totalDeb !== totalCre && (
            <div className="px-3 py-1.5 bg-amber-50 border-t border-amber-200 flex items-center gap-1.5">
              <AlertCircle size={11} className="text-amber-600" />
              <span className="text-[10px] text-amber-700 font-semibold">Débitos y créditos no coinciden — revisar antes de confirmar</span>
            </div>
          )}
        </div>
      )}

      {/* Bill items table */}
      {isBill && (
        <div style={{ borderBottom: "1px solid #E2E8F0" }}>
          <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Items de Compra</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "#F1F5F9" }}>
                <th className="px-3 py-1.5 text-left font-bold text-slate-500 text-[10px]">Item</th>
                <th className="px-3 py-1.5 text-center font-bold text-slate-500 text-[10px]">Cant.</th>
                <th className="px-3 py-1.5 text-right font-bold text-slate-500 text-[10px]">Precio Unit.</th>
                <th className="px-3 py-1.5 text-right font-bold text-slate-500 text-[10px]">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {billItems.map((it, i) => {
                const sub = Number(it.price || 0) * Number(it.quantity || 1);
                return (
                  <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#F8FAFC" }}>
                    <td className="px-3 py-1.5 text-slate-600">
                      {it.name || <span className="font-mono text-[10px] text-slate-400">id:{it.id}</span>}
                    </td>
                    <td className="px-3 py-1.5 text-center text-slate-600">{it.quantity || 1}</td>
                    <td className="px-3 py-1.5 text-right text-slate-600">{fmtCOP(it.price)}</td>
                    <td className="px-3 py-1.5 text-right font-semibold text-slate-700">{fmtCOP(sub)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Invoice items table */}
      {isInvoice && (
        <div style={{ borderBottom: "1px solid #E2E8F0" }}>
          <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Items de Venta</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "#F1F5F9" }}>
                <th className="px-3 py-1.5 text-left font-bold text-slate-500 text-[10px]">Producto</th>
                <th className="px-3 py-1.5 text-center font-bold text-slate-500 text-[10px]">Cant.</th>
                <th className="px-3 py-1.5 text-right font-bold text-slate-500 text-[10px]">Precio</th>
              </tr>
            </thead>
            <tbody>
              {invoiceItems.map((it, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#F8FAFC" }}>
                  <td className="px-3 py-1.5 text-slate-600">{it.name || `id:${it.id}`}</td>
                  <td className="px-3 py-1.5 text-center text-slate-600">{it.quantity || 1}</td>
                  <td className="px-3 py-1.5 text-right text-slate-600">{fmtCOP(it.price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Action buttons */}
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

function TerceroCard({ action, onConfirm, onCancel, executing }: {
  action: PendingAction | null;
  onConfirm: (action: PendingAction) => void;
  onCancel: () => void;
  executing: boolean;
}): React.ReactElement | null {
  const p = action?.payload || {};
  const [name, setName] = useState(p.name || p.nameObject?.firstName || "");
  const [nit, setNit] = useState(p.identification || p.identificationObject?.number || "");
  const [email, setEmail] = useState(p.email || "");
  if (!action) return null;
  const typeLabel = Array.isArray(p.type)
    ? p.type.map((t) => t === "provider" ? "Proveedor" : t === "client" ? "Cliente" : t).join(", ")
    : (p.type || "Proveedor");

  const fieldCls = "w-full text-xs px-3 py-2 rounded-lg outline-none border border-slate-200 bg-white text-slate-700 focus:ring-2 focus:ring-orange-200 focus:border-orange-400 transition";
  const labelCls = "text-[10px] font-bold uppercase tracking-wide mb-1 block text-slate-400";

  const handleConfirmClick = () => {
    const updatedPayload = { ...p, name, identification: nit, email };
    onConfirm({ ...action, payload: updatedPayload });
  };

  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm" style={{ border: "1px solid #FED7AA" }} data-testid="tercero-card">
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-2 flex-wrap" style={{ background: "#FFF7ED", borderBottom: "1px solid #FED7AA" }}>
        <UserPlus size={13} className="text-orange-600 flex-shrink-0" />
        <span className="text-xs font-bold text-orange-700 uppercase tracking-wide">Tercero no encontrado en Alegra</span>
        <span className="ml-auto text-[10px] text-orange-500">¿Crear y continuar?</span>
      </div>

      {/* Fields */}
      <div className="p-4 space-y-3 bg-white">
        <div>
          <label className={labelCls}>Nombre / Razón Social</label>
          <input value={name} onChange={(e) => setName(e.target.value)}
            className={fieldCls} placeholder="Nombre del tercero" data-testid="tercero-name" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>NIT / Cédula</label>
            <input value={nit} onChange={(e) => setNit(e.target.value)}
              className={fieldCls} placeholder="900123456-1" data-testid="tercero-nit" />
          </div>
          <div>
            <label className={labelCls}>Tipo</label>
            <div className="text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-600 font-medium">
              {typeLabel}
            </div>
          </div>
        </div>
        <div>
          <label className={labelCls}>Email (opcional)</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)}
            className={fieldCls} placeholder="correo@empresa.com" data-testid="tercero-email" />
        </div>

        {/* Account suggestion */}
        {p.accounting_account_name && (
          <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg" style={{ background: "#EFF6FF", border: "1px solid #BFDBFE" }}>
            <div className="flex-shrink-0 mt-0.5">
              <div className="w-4 h-4 rounded-full bg-blue-100 flex items-center justify-center">
                <span className="text-[8px] font-bold text-blue-600">C</span>
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold text-blue-600 uppercase tracking-wide mb-0.5">Cuenta contable sugerida</div>
              <div className="text-xs text-blue-700 font-medium">
                <span className="font-mono text-[10px] text-blue-500 mr-1">{p.accounting_account_suggested}</span>
                {p.accounting_account_name}
              </div>
              <div className="text-[10px] text-blue-400 mt-0.5">Puedes ajustar esto en Alegra después de la creación</div>
            </div>
          </div>
        )}

        {/* Next action preview */}
        {p._next_action && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200">
            <ArrowRight size={11} className="text-slate-400 flex-shrink-0" />
            <span className="text-[10px] text-slate-500">
              Tras crear el tercero, se ejecutará automáticamente:
              <span className="font-bold text-slate-600 ml-1">{p._next_action.title}</span>
            </span>
          </div>
        )}
      </div>

      {/* Buttons */}
      <div className="p-3 flex gap-2 bg-white border-t border-slate-100">
        <Button onClick={handleConfirmClick} disabled={executing || !name.trim()}
          className="flex-1 text-xs h-9 font-bold disabled:opacity-40"
          style={{ background: executing ? "#94A3B8" : "linear-gradient(135deg, #F97316, #EF4444)", color: "#fff" }}
          data-testid="confirm-tercero-btn">
          {executing
            ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Creando...</>
            : <><UserPlus size={13} className="mr-1.5" />Crear tercero y continuar</>}
        </Button>
        <Button onClick={onCancel} disabled={executing} variant="outline"
          className="text-xs h-9 px-3 font-medium border-slate-200 text-slate-500 hover:bg-slate-50"
          data-testid="cancel-tercero-btn">
          <X size={12} className="mr-1" />Cancelar
        </Button>
      </div>
    </div>
  );
}


function PlExportCard({ card, token }: { card: PlExportCardData; token?: string }): React.ReactElement {
  const [downloading, setDownloading] = useState<"pdf" | "excel" | null>(null);

  const handlePdf = () => {
    const url = `${API}/api/cfo/estado-resultados/pdf?periodo=${card.periodo}`;
    window.open(url, "_blank");
  };

  const handleExcel = async () => {
    setDownloading("excel");
    try {
      const res = await fetch(`${API}/api/cfo/estado-resultados/excel?periodo=${card.periodo}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Error");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `RODDOS_PL_${card.periodo}.xlsx`;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); window.URL.revokeObjectURL(url);
    } catch { /* silent */ } finally { setDownloading(null); }
  };

  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm" style={{ border: "1px solid #BFDBFE" }} data-testid="pl-export-card">
      <div className="px-4 py-2.5 flex items-center gap-2 flex-wrap" style={{ background: "#EFF6FF", borderBottom: "1px solid #BFDBFE" }}>
        <FileText size={13} className="text-blue-600" />
        <span className="text-xs font-bold text-blue-700 uppercase tracking-wide">Estado de Resultados</span>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700 border border-blue-200">{card.periodo_label}</span>
      </div>
      <div className="px-4 py-3 bg-white">
        <p className="text-sm font-semibold text-slate-700 mb-3">{card.titulo}</p>
        <div className="flex gap-2">
          <button
            onClick={handleExcel}
            disabled={downloading === "excel"}
            data-testid="pl-export-excel-btn"
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2 px-3 rounded-lg border border-emerald-300 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition disabled:opacity-50"
          >
            {downloading === "excel" ? <Loader2 size={12} className="animate-spin" /> : <Sheet size={12} />}
            Excel (.xlsx)
          </button>
          <button
            onClick={handlePdf}
            data-testid="pl-export-pdf-btn"
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2 px-3 rounded-lg border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 transition"
          >
            <Download size={12} />
            PDF Ejecutivo
          </button>
        </div>
      </div>
    </div>
  );
}


function CuotasInicialesCard({ card }: { card: any }): React.ReactElement {
  const fmt = (n: number) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
  const RODDOS_MSG = (nombre: string, monto: number) =>
    `Hola ${nombre.split(" ")[0]}, te recordamos que tienes pendiente el pago de tu cuota inicial de ${fmt(monto)} para tu moto. Por favor comunícate con nosotros. — RODDOS Motos Colombia`;

  const handleWA = (cliente: any) => {
    if (!cliente.telefono) { alert("Sin número de teléfono registrado"); return; }
    const num = cliente.telefono.replace(/\D/g, "");
    window.open(`https://wa.me/57${num}?text=${encodeURIComponent(RODDOS_MSG(cliente.cliente, cliente.monto))}`, "_blank");
  };

  const handleWAAll = () => {
    card.clientes?.filter((c: any) => c.telefono).forEach((c: any) => handleWA(c));
  };

  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm border border-emerald-200" data-testid="cuotas-iniciales-card">
      <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: "#064E3B" }}>
        <CreditCard size={13} className="text-emerald-300" />
        <span className="text-xs font-bold text-emerald-100 uppercase tracking-wide">Cuotas Iniciales Pendientes</span>
        <span className="ml-auto text-xs font-bold text-emerald-200">{fmt(card.total)} · {card.count} clientes</span>
      </div>
      <div className="bg-white divide-y divide-slate-100">
        {card.clientes?.map((c: any, i: number) => (
          <div key={i} className="flex items-center justify-between px-4 py-2.5" data-testid={`cuota-client-row-${i}`}>
            <div>
              <p className="text-sm font-semibold text-slate-800">{c.cliente}</p>
              <p className="text-xs text-slate-500">{c.codigo}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-emerald-700">{fmt(c.monto)}</span>
              <button
                onClick={() => handleWA(c)}
                data-testid={`wa-btn-${i}`}
                className="flex items-center gap-1 text-[10px] font-bold text-white bg-green-600 hover:bg-green-700 px-2.5 py-1.5 rounded-lg transition"
              >
                <span>💬</span> WhatsApp
              </button>
            </div>
          </div>
        ))}
      </div>
      {card.clientes?.some((c: any) => c.telefono) && (
        <div className="px-4 py-2.5 bg-emerald-50 border-t border-emerald-100">
          <button
            onClick={handleWAAll}
            data-testid="wa-all-btn"
            className="w-full text-xs font-bold text-emerald-700 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 py-2 rounded-lg transition"
          >
            💬 Generar WhatsApp para todos ({card.clientes?.filter((c: any) => c.telefono).length} con teléfono)
          </button>
        </div>
      )}
    </div>
  );
}


function MultiFilePreview({ files, onProcess, onClear, processing, processingIdx }: {
  files: any[]; onProcess: () => void; onClear: () => void; processing: boolean; processingIdx: number;
}): React.ReactElement {
  const getType = (name: string, mime: string) => {
    if (mime === "application/pdf") return "📄 PDF";
    if (mime.startsWith("image/")) return "🖼️ Imagen";
    return "📎 Archivo";
  };
  return (
    <div className="mb-4 rounded-xl overflow-hidden shadow-sm border border-blue-200" data-testid="multi-file-preview">
      <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: "#1E3A5F" }}>
        <Paperclip size={13} className="text-blue-300" />
        <span className="text-xs font-bold text-blue-100 uppercase tracking-wide">Archivos detectados ({files.length})</span>
      </div>
      <div className="bg-white divide-y divide-slate-100">
        {files.map((f, i) => (
          <div key={i} className={`flex items-center gap-3 px-4 py-2 ${processing && i === processingIdx ? "bg-blue-50" : ""}`} data-testid={`multi-file-row-${i}`}>
            <span className="text-lg">{f.type === "application/pdf" ? "📄" : "🖼️"}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate">{f.name}</p>
              <p className="text-[10px] text-slate-400">{getType(f.name, f.type)}</p>
            </div>
            {processing && i === processingIdx && <Loader2 size={12} className="animate-spin text-blue-600 flex-shrink-0" />}
            {processing && i < processingIdx && <CheckCircle2 size={12} className="text-emerald-600 flex-shrink-0" />}
          </div>
        ))}
      </div>
      <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex gap-2">
        <button onClick={onProcess} disabled={processing}
          className="flex-1 text-xs font-bold text-white bg-[#0F2A5C] hover:bg-[#1a3d7a] py-2 rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-1.5"
          data-testid="process-all-files-btn">
          {processing ? <><Loader2 size={11} className="animate-spin" /> Procesando {processingIdx + 1}/{files.length}...</> : <><Play size={11} /> Procesar todos</>}
        </button>
        <button onClick={onClear} disabled={processing} className="text-xs text-slate-500 hover:text-slate-700 px-3 py-2 rounded-lg border border-slate-200 transition disabled:opacity-40">
          <X size={11} />
        </button>
      </div>
    </div>
  );
}


function DocumentProposalCard({ proposal, onConfirm, onCancel, loading }: {
  proposal: DocumentProposalData;
  onConfirm: (data: DocumentProposalData & { total: number }) => void;
  onCancel: () => void;
  loading: boolean;
}): React.ReactElement {
  const [data, setData] = useState<DocumentProposalData>({ ...proposal });
  // TODO: type - generic key-value updater for dynamic form fields
  const update = (k: string, v: any) => setData((p) => ({ ...p, [k]: v } as DocumentProposalData));
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

/* ── TareaActiva badge ── */

function TareaActivaBadge({ tarea, onPausar, onContinuar }: {
  tarea: TareaActiva;
  onPausar: () => void;
  onContinuar: () => void;
}): React.ReactElement | null {
  const [expanded, setExpanded] = useState(false);

  if (!tarea || tarea.estado === "ninguna") return null;

  const completados = tarea.pasos_completados ?? 0;
  const total = tarea.pasos_total ?? 0;
  const pct = total > 0 ? Math.min(100, Math.round((completados / total) * 100)) : 0;

  const theme = tarea.estado === "completada"
    ? { border: "#BBF7D0", accent: "#00C853", bg: "#F0FDF4", text: "#166534" }
    : tarea.estado === "pausada"
    ? { border: "#FDE68A", accent: "#F59E0B", bg: "#FFFBEB", text: "#92400E" }
    : { border: "#BAE6FD", accent: "#00C4D4", bg: "#EFF6FF", text: "#0369A1" };

  return (
    <div
      className="mx-5 mt-3 rounded-xl overflow-hidden flex-shrink-0"
      style={{ border: `1px solid ${theme.border}`, background: theme.bg }}
      data-testid="tarea-activa-badge"
    >
      {/* Main row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{
            background: theme.accent,
            animation: tarea.estado === "en_curso" ? "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite" : "none",
          }}
        />
        <span className="text-xs font-semibold flex-1 truncate" style={{ color: theme.text }}>
          {tarea.descripcion || "Tarea en progreso"}
        </span>
        <span className="text-xs font-bold font-mono flex-shrink-0" style={{ color: theme.accent }}>
          [{completados}/{total}]
        </span>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setExpanded((p) => !p)}
            className="text-[10px] px-2 py-0.5 rounded font-semibold transition"
            style={{ background: `${theme.accent}22`, color: theme.accent }}
            data-testid="tarea-ver-btn"
          >
            {expanded ? "Ocultar" : "Ver"}
          </button>
          {tarea.estado === "en_curso" && (
            <button
              onClick={onPausar}
              className="text-[10px] px-2 py-0.5 rounded font-semibold transition"
              style={{ background: "#FEF3C7", color: "#92400E", border: "1px solid #FDE68A" }}
              data-testid="tarea-pausar-btn"
            >
              Pausar
            </button>
          )}
          {tarea.estado === "pausada" && (
            <button
              onClick={onContinuar}
              className="text-[10px] px-2 py-0.5 rounded font-semibold transition"
              style={{ background: "#D1FAE5", color: "#166534", border: "1px solid #BBF7D0" }}
              data-testid="tarea-continuar-btn"
            >
              Continuar
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mx-3 mb-2 h-1.5 rounded-full overflow-hidden" style={{ background: theme.border }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: theme.accent }}
        />
      </div>

      {/* Expanded step list */}
      {expanded && (
        <div className="mx-3 mb-2.5 space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wide mb-1" style={{ color: theme.text }}>
            Pasos pendientes:
          </div>
          {(tarea.pasos_pendientes ?? []).length > 0
            ? (tarea.pasos_pendientes ?? []).map((paso, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[11px]" style={{ color: theme.text }}>
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: theme.accent }} />
                  {paso}
                </div>
              ))
            : (
                <div className="text-[11px]" style={{ color: theme.text }}>
                  {tarea.estado === "completada" ? "Todos los pasos completados." : "Sin pasos registrados."}
                </div>
              )}
        </div>
      )}
    </div>
  );
}

/* ── main page ── */
export default function AgentChatPage() {
  const { api, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [documentProposal, setDocumentProposal] = useState<DocumentProposalData | null>(null);
  const [plExportCard, setPlExportCard] = useState<PlExportCardData | null>(null);
  const [cuotasInicialesCard, setCuotasInicialesCard] = useState<any>(null);
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [multiFileProcessing, setMultiFileProcessing] = useState(false);
  const [multiFileIdx, setMultiFileIdx] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [memorySuggestions, setMemorySuggestions] = useState<MemorySuggestion[]>([]);
  const [docTypeHint, setDocTypeHint] = useState("auto");
  const [tareaActiva, setTareaActiva] = useState<TareaActiva | null>(null);

  const sessionId = useRef(`chat-main-${user?.id || "guest"}`).current;
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  /* poll tarea activa every 3s — with offline guard and 502 back-off */
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    let completedTimer: ReturnType<typeof setTimeout>;
    let retryDelay = 3000;

    const poll = async () => {
      if (!navigator.onLine) return; // skip when offline
      try {
        const res = await api.get("/chat/tarea");
        const t: TareaActiva = res.data;
        retryDelay = 3000; // reset on success
        if (t.estado === "completada") {
          setTareaActiva(t);
          clearInterval(interval);
          completedTimer = setTimeout(() => setTareaActiva(null), 3000);
        } else if (t.estado === "ninguna") {
          setTareaActiva(null);
        } else {
          setTareaActiva(t);
        }
      } catch (e: any) {
        // On 502/503 back off exponentially up to 30s
        if (e?.response?.status === 502 || e?.response?.status === 503 || !e?.response) {
          retryDelay = Math.min(retryDelay * 2, 30000);
          clearInterval(interval);
          interval = setInterval(poll, retryDelay);
        }
        // On any error: silently keep the last known state
      }
    };

    poll();
    interval = setInterval(poll, retryDelay);
    return () => { clearInterval(interval); clearTimeout(completedTimer); };
  }, []); // eslint-disable-line

  /* document-level paste for images */  useEffect(() => {
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
  const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve((reader.result as string).split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const handleFileAttach = useCallback(async (file: File): Promise<void> => {
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "application/pdf"];
    if (file.size > 20 * 1024 * 1024) { toast.error("El archivo no puede superar 20MB"); return; }
    if (!allowed.includes(file.type)) { toast.error("Solo imágenes (JPG, PNG, WebP) y PDF"); return; }
    try {
      const base64 = await fileToBase64(file);
      const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
      setAttachedFile({ base64, name: file.name, type: file.type, preview });
      setDocTypeHint("auto");
      inputRef.current?.focus();
    } catch { toast.error("Error al procesar el archivo"); }
  }, []);

  /* drag & drop */
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>): void => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>): void => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false); };
  const handleDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault(); setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 1) {
      handleFileAttach(files[0]);
    } else if (files.length > 1) {
      const process = async () => {
        const processed: AttachedFile[] = [];
        for (const f of files.slice(0, 10)) {
          const base64: string = await new Promise((res, rej) => {
            const reader = new FileReader();
            reader.onload = () => res((reader.result as string).split(",")[1]);
            reader.onerror = rej;
            reader.readAsDataURL(f);
          });
          const preview = f.type.startsWith("image/") ? `data:${f.type};base64,${base64}` : null;
          processed.push({ base64, name: f.name, type: f.type, preview });
        }
        setAttachedFiles(processed);
      };
      process();
    }
  };

  /* send message */
  const handleSend = async () => {
    if ((!input.trim() && !attachedFile) || loading || multiFileProcessing) return;

    const sentInput = input.trim();
    const sentFile = attachedFile;
    const selectedType = DOC_TYPE_OPTIONS.find((o) => o.value === docTypeHint);
    const typeHint = sentFile && selectedType ? selectedType.hint : "";

    setMessages((prev) => [...prev, {
      role: "user", content: sentInput || "Analizar este documento", timestamp: new Date().toISOString(),
      file: sentFile ? { name: sentFile.name, type: sentFile.type, preview: sentFile.preview } : null,
      docTypeLabel: sentFile && selectedType?.value !== "auto" ? selectedType.label : null,
    }]);
    setInput(""); setAttachedFile(null); setDocTypeHint("auto"); setLoading(true);
    setDocumentProposal(null); setPendingAction(null); setPlExportCard(null); setCuotasInicialesCard(null);

    try {
      const baseMessage = sentInput || "Analiza este comprobante contable y extrae los datos para su registro en Alegra.";
      const payload = {
        session_id: sessionId,
        message: typeHint + baseMessage,
        ...(sentFile ? { file_content: sentFile.base64, file_name: sentFile.name, file_type: sentFile.type } : {}),
      };
      const resp = await api.post("/chat/message", payload);
      const { message, pending_action, document_proposal, export_card, cuotas_iniciales_card } = resp.data;
      setMessages((prev) => [...prev, { role: "assistant", content: message, timestamp: new Date().toISOString() }]);
      if (document_proposal) setDocumentProposal(document_proposal);
      else if (cuotas_iniciales_card?.type === "cuotas_iniciales_card") setCuotasInicialesCard(cuotas_iniciales_card);
      else if (export_card?.type === "pl_export_card") setPlExportCard(export_card);
      else if (pending_action?.type && pending_action?.payload) setPendingAction(pending_action);
    } catch (err: any) {
      const rawDetail = err?.response?.data?.detail ?? "";
      let errMsg = "Error al comunicarse con el asistente. Intenta de nuevo.";
      if (rawDetail) {
        if (rawDetail.includes("Budget has been exceeded") || rawDetail.includes("budget")) {
          errMsg = "El saldo del LLM Key est\u00e1 agotado. Ve a Perfil \u2192 Universal Key \u2192 Add Balance para recargar.";
        } else if (rawDetail.includes("Anthropic") || rawDetail.includes("litellm") || rawDetail.includes("API de IA")) {
          errMsg = `Error en la API de IA: ${rawDetail}`;
        } else {
          errMsg = rawDetail;
        }
      }
      setMessages((prev) => [...prev, { role: "assistant", content: errMsg, timestamp: new Date().toISOString() }]);
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
      const full = `${resp.data.message || action.title + " ejecutado en Alegra"}${docId ? ` — ID: ${docId}` : ""}${syncMsgs.length > 0 ? `\n\nMódulos actualizados:\n${syncMsgs.join("\n")}` : ""}`;
      setMessages((prev) => [...prev, { role: "assistant", content: full, timestamp: new Date().toISOString(), isResult: true }]);

      // Handle sequential action (e.g. crear_contacto → then original action)
      if (resp.data.next_pending_action?.type && resp.data.next_pending_action?.payload) {
        toast.success(`${action.title} completado. Continuando con la siguiente acción...`);
        setPendingAction(resp.data.next_pending_action);
      } else {
        setPendingAction(null);
        toast.success(`${action.title} ejecutado correctamente`);
      }
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

  const handleProcessAllFiles = async () => {
    if (!attachedFiles.length || multiFileProcessing) return;
    setMultiFileProcessing(true);
    setMultiFileIdx(0);
    for (let i = 0; i < attachedFiles.length; i++) {
      setMultiFileIdx(i);
      const f = attachedFiles[i];
      setMessages(prev => [...prev, {
        role: "user",
        content: `[Procesando archivo ${i + 1}/${attachedFiles.length}: ${f.name}]`,
        timestamp: new Date().toISOString(),
      }]);
      try {
        const payload = {
          message: `Procesa este archivo: ${f.name}`,
          session_id: sessionId,
          file_b64: f.base64,
          file_type: f.type,
          file_name: f.name,
          doc_type_hint: "auto",
        };
        const resp = await api.post("/chat/message", payload);
        const { message, pending_action, session_id: newSid } = resp.data;
        // sessionId is a ref, no need to update
        setMessages(prev => [...prev, { role: "assistant", content: message, timestamp: new Date().toISOString() }]);
        if (pending_action?.type && pending_action?.payload) {
          setPendingAction(pending_action);
          break;
        }
      } catch (e: any) {
        setMessages(prev => [...prev, { role: "assistant", content: `Error procesando ${f.name}: ${e.response?.data?.detail || "Error desconocido"}`, timestamp: new Date().toISOString() }]);
      }
    }
    setMultiFileProcessing(false);
    setAttachedFiles([]);
  };

  const handlePausarTarea = async () => {
    try {
      await api.patch("/chat/tarea/avance", null, { params: { accion: "pausar" } });
      setTareaActiva((prev) => prev ? { ...prev, estado: "pausada" } : null);
    } catch { toast.error("Error al pausar la tarea"); }
  };

  const handleContinuarTarea = async () => {
    try {
      await api.patch("/chat/tarea/avance", null, { params: { accion: "continuar" } });
      setTareaActiva((prev) => prev ? { ...prev, estado: "en_curso" } : null);
    } catch { toast.error("Error al reanudar la tarea"); }
  };

  const clearChat = async () => {
    try {
      await api.delete(`/chat/history/${sessionId}`);
      setMessages([{ role: "assistant", content: "Historial borrado. ¿En qué te puedo ayudar?", timestamp: new Date().toISOString() }]);
      setPendingAction(null); setDocumentProposal(null);
    } catch { toast.error("Error al borrar historial"); }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
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

      {/* Task badge */}
      {tareaActiva && tareaActiva.estado !== "ninguna" && (
        <TareaActivaBadge
          tarea={tareaActiva}
          onPausar={handlePausarTarea}
          onContinuar={handleContinuarTarea}
        />
      )}

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
          pendingAction.type === "crear_contacto"
            ? <TerceroCard action={pendingAction} onConfirm={handleExecute}
                onCancel={handleCancelAction} executing={executing} />
            : <ExecutionCard action={pendingAction} onConfirm={handleExecute}
                onCancel={handleCancelAction} executing={executing} />
        )}

        {plExportCard && !loading && (
          <PlExportCard card={plExportCard} token={(api as any).defaults?.headers?.Authorization?.replace("Bearer ", "")} />
        )}

        {cuotasInicialesCard && !loading && (
          <CuotasInicialesCard card={cuotasInicialesCard} />
        )}

        {attachedFiles.length > 0 && !loading && (
          <MultiFilePreview
            files={attachedFiles}
            onProcess={handleProcessAllFiles}
            onClear={() => setAttachedFiles([])}
            processing={multiFileProcessing}
            processingIdx={multiFileIdx}
          />
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
      <div className="flex-shrink-0 bg-white relative" style={{ borderTop: "1px solid #E2E8F0", zIndex: 10000 }}>
        {/* File preview + type selector */}
        {attachedFile && (
          <div className="px-4 pt-3 pb-2">
            {/* File row */}
            <div className="flex items-center gap-2 mb-2.5">
              <div className="flex items-center gap-2 flex-1 min-w-0 px-3 py-2 rounded-xl bg-sky-50 border border-sky-200"
                data-testid="file-preview-strip">
                {attachedFile.preview
                  ? <img src={attachedFile.preview} alt={attachedFile.name} className="w-7 h-7 rounded object-cover flex-shrink-0" />
                  : <FileText size={15} className="text-sky-500 flex-shrink-0" />
                }
                <span className="text-xs font-medium truncate text-slate-700 flex-1">{attachedFile.name}</span>
                <button onClick={() => { setAttachedFile(null); setDocTypeHint("auto"); }}
                  className="hover:opacity-60 transition text-slate-400 flex-shrink-0 ml-1"
                  data-testid="remove-file-btn">
                  <X size={13} />
                </button>
              </div>
            </div>

            {/* Type chips */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Tipo:</span>
              {DOC_TYPE_OPTIONS.map((opt) => {
                const isSelected = docTypeHint === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setDocTypeHint(opt.value)}
                    className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-semibold border transition-all"
                    style={isSelected
                      ? { background: opt.color || "linear-gradient(135deg, #00C4D4, #00C853)", color: "#fff", borderColor: opt.color || "#00C4D4" }
                      : { background: "#fff", color: "#64748B", borderColor: "#E2E8F0" }
                    }
                    data-testid={`doc-type-chip-${opt.value}`}
                  >
                    <opt.icon size={10} />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="p-4 flex items-end gap-2">
          <button onClick={() => fileInputRef.current?.click()}
            className="p-2.5 rounded-lg transition flex-shrink-0 bg-slate-50 border border-slate-200 text-slate-400 hover:text-sky-500 hover:bg-sky-50 hover:border-sky-300"
            title="Adjuntar PDF o imagen · hasta 10 archivos (o arrastra / Ctrl+V)" data-testid="file-attach-btn">
            <Paperclip size={17} />
          </button>
          <input ref={fileInputRef} type="file" hidden multiple
            accept="image/jpeg,image/jpg,image/png,image/gif,image/webp,application/pdf"
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              if (files.length === 1) {
                handleFileAttach(files[0]);
              } else if (files.length > 1) {
                const process = async () => {
                  const processed: AttachedFile[] = [];
                  for (const f of files.slice(0, 10)) {
                    const base64: string = await new Promise((res, rej) => {
                      const reader = new FileReader();
                      reader.onload = () => res((reader.result as string).split(",")[1]);
                      reader.onerror = rej;
                      reader.readAsDataURL(f);
                    });
                    const preview = f.type.startsWith("image/") ? `data:${f.type};base64,${base64}` : null;
                    processed.push({ base64, name: f.name, type: f.type, preview });
                  }
                  setAttachedFiles(processed);
                };
                process();
              }
              e.target.value = "";
            }} />

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
