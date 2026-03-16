import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Phone, MessageCircle, Calendar, AlertTriangle, Star,
  Edit2, Check, X, Plus, Loader2, Clock, User, Brain, TrendingDown,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "../components/ui/sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { GestionModal } from "../components/shared/GestionModal";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";

const BUCKET_STYLE: Record<string, { bg: string; text: string; border: string; label: string }> = {
  RECUPERACION: { bg: "bg-red-900/30",    text: "text-red-400",    border: "border-red-700",    label: "RECUPERACIÓN" },
  CRITICO:      { bg: "bg-red-800/25",    text: "text-red-300",    border: "border-red-600",    label: "CRÍTICO" },
  URGENTE:      { bg: "bg-orange-900/25", text: "text-orange-400", border: "border-orange-700", label: "URGENTE" },
  ACTIVO:       { bg: "bg-yellow-900/20", text: "text-yellow-400", border: "border-yellow-700", label: "ACTIVO" },
  HOY:          { bg: "bg-blue-900/25",   text: "text-blue-400",   border: "border-blue-700",   label: "HOY" },
  AL_DIA:       { bg: "bg-emerald-900/20",text: "text-emerald-400",border: "border-emerald-700",label: "AL DÍA" },
};

const SCORE_STYLE: Record<string, { bg: string; text: string }> = {
  A: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  B: { bg: "bg-blue-500/15",    text: "text-blue-400" },
  C: { bg: "bg-yellow-500/15",  text: "text-yellow-400" },
  F: { bg: "bg-red-500/15",     text: "text-red-400" },
};

const RESULTADOS = [
  "contestó_pagará_hoy", "contestó_prometió_fecha", "contestó_no_pagará",
  "no_contestó", "número_equivocado", "respondió_pagará", "respondió_prometió_fecha",
  "visto_sin_respuesta", "no_entregado", "acuerdo_de_pago_firmado",
];
const CANALES = ["llamada", "whatsapp", "visita", "email"];

const fmt  = (n: number) => `$${Math.round(n || 0).toLocaleString("es-CO")}`;
const fmtD = (s: string) => s ? s.split("T")[0] : "—";
const stars = (l: string) => l === "A" ? "★★★" : l === "B" ? "★★" : l === "C" ? "★" : "";

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, children }: { title: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-4">
      <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">{title}</h2>
      {children}
    </div>
  );
}

// ── Gestion Modal ─────────────────────────────────────────────────────────────
// ── Main ──────────────────────────────────────────────────────────────────────
export default function CRMCliente() {
  const { id } = useParams<{ id: string }>();
  const { api } = useAuth();
  const navigate = useNavigate();
  const [data, setData]       = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editDatos, setEditDatos] = useState<any>({});
  const [nota, setNota]       = useState("");
  const [addingNota, setAddingNota] = useState(false);
  const [showGestion, setShowGestion] = useState(false);
  const [showPTP, setShowPTP] = useState(false);
  const [ptpFecha, setPtpFecha] = useState("");
  const [ptpMonto, setPtpMonto] = useState("");
  // BUILD 9 — Capa de Aprendizaje
  const [learning, setLearning] = useState<any>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/crm/${id}`);
      setData(res.data);
      const crm = res.data.crm || {};
      setEditDatos({
        telefono_alternativo: crm.telefono_alternativo || "",
        direccion: crm.direccion || "",
        barrio: crm.barrio || "",
        ciudad: crm.ciudad || "Bogotá",
        email: crm.email || "",
        ocupacion: crm.ocupacion || "",
        referencia_1: crm.referencia_1 || { nombre: "", telefono: "", parentesco: "" },
        referencia_2: crm.referencia_2 || { nombre: "", telefono: "", parentesco: "" },
      });
    } catch { toast.error("No se pudo cargar el cliente"); }
    finally { setLoading(false); }
  }, [api, id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // BUILD 9 — Fetch learning data (recomendación + alerta)
  useEffect(() => {
    if (!id) return;
    api.get(`/crm/${id}/learning`).then((r: any) => setLearning(r.data)).catch(() => {});
  }, [id, api]);

  const handleSaveDatos = async () => {
    try {
      await api.put(`/crm/${id}/datos`, editDatos);
      toast.success("Datos actualizados");
      setEditMode(false);
      fetchData();
    } catch { toast.error("Error guardando datos"); }
  };

  const handleAddNota = async () => {
    if (!nota.trim()) return;
    setAddingNota(true);
    try {
      await api.post(`/crm/${id}/nota`, { texto: nota });
      toast.success("Nota agregada");
      setNota(""); fetchData();
    } catch { toast.error("Error agregando nota"); }
    finally { setAddingNota(false); }
  };

  const handlePTP = async () => {
    if (!ptpFecha || !ptpMonto) { toast.error("Completa fecha y monto del PTP"); return; }
    try {
      await api.post(`/crm/${id}/ptp`, { ptp_fecha: ptpFecha, ptp_monto: parseFloat(ptpMonto) });
      toast.success("PTP registrado");
      setShowPTP(false); fetchData();
    } catch { toast.error("Error registrando PTP"); }
  };

  if (loading) return (
    <div className="min-h-screen bg-[#060E1E] flex items-center justify-center">
      <Loader2 size={28} className="animate-spin text-[#00C8FF]" />
    </div>
  );
  if (!data) return null;

  const { loan, crm, score_letra, score_pct, bucket, dpd_actual, dias_para_protocolo,
          mora_acumulada, cuotas_pagadas, cuotas_vencidas, cuotas_pendientes,
          proxima_cuota, gestiones, whatsapp_gestiones, historial_pagos } = data;

  const bs = BUCKET_STYLE[bucket] || BUCKET_STYLE.AL_DIA;
  const ss = SCORE_STYLE[score_letra] || SCORE_STYLE.C;
  const nombre = loan?.cliente_nombre || crm?.nombre_completo || "Cliente";
  const telefono = loan?.cliente_telefono || crm?.telefono_principal || "";
  const waLink = (() => {
    const p = telefono.replace(/\D/g, "");
    const wp = p.startsWith("57") ? p : `57${p}`;
    return `https://wa.me/${wp}`;
  })();

  return (
    <div className="min-h-screen bg-[#060E1E] text-white pb-8">
      {/* Sticky top header — always visible on mobile */}
      <div className="sticky top-0 z-20 bg-[#060E1E]/95 backdrop-blur border-b border-[#1E3A5F] px-4 py-3 flex items-center gap-3" data-testid="crm-sticky-header">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-white shrink-0"
          data-testid="crm-back-btn">
          <ArrowLeft size={14} />
        </button>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="font-semibold text-white truncate">{nombre}</span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${bs.bg} ${bs.text} ${bs.border}`}>{bs.label}</span>
          {dpd_actual > 0 && (
            <span className="text-[10px] text-red-400 shrink-0">{dpd_actual}d</span>
          )}
        </div>
        <button onClick={() => setShowGestion(true)}
          className="shrink-0 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg px-3 py-1.5 transition-colors"
          data-testid="gestion-btn-sticky">
          + Gestión
        </button>
      </div>

      <div className="px-4 py-5 md:px-6 max-w-4xl mx-auto">
      {/* Client header card */}
      <div className="bg-[#0D1E3A] border border-[#1E3A5F] rounded-xl p-5 mb-4" data-testid="crm-header">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-white">{nombre}</h1>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${bs.bg} ${bs.text} ${bs.border}`}>{bs.label}</span>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${ss.bg} ${ss.text}`}>
                {stars(score_letra)}{score_letra} — {score_pct}%
              </span>
              {dpd_actual > 0 && (
                <span className="text-xs bg-red-900/20 text-red-400 border border-red-800 px-2.5 py-1 rounded-full">{dpd_actual} DPD</span>
              )}
              {dpd_actual > 0 && dias_para_protocolo <= 5 && (
                <span className="text-xs flex items-center gap-1 text-orange-400">
                  <AlertTriangle size={12} /> {dias_para_protocolo === 0 ? "Protocolo activo" : `Protocolo en ${dias_para_protocolo}d`}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1 font-mono">{loan?.codigo} · {loan?.plan}</p>
          </div>
          {/* Acciones rápidas */}
          <div className="flex gap-2 flex-wrap" data-testid="acciones-rapidas">
            <a href={waLink} target="_blank" rel="noreferrer"
              className="flex items-center gap-1.5 text-xs bg-green-900/30 border border-green-800 text-green-400 rounded-lg px-3 py-2 hover:bg-green-800/40 transition-colors"
              data-testid="wa-link-btn">
              <MessageCircle size={13} /> WhatsApp
            </a>
            <button onClick={() => setShowGestion(true)}
              className="flex items-center gap-1.5 text-xs bg-[#0F2A5C]/60 border border-[#1E3A5F] text-blue-300 rounded-lg px-3 py-2 hover:bg-[#0F2A5C] transition-colors"
              data-testid="gestion-btn">
              <Phone size={13} /> Llamada
            </button>
            <button onClick={() => setShowPTP(true)}
              className="flex items-center gap-1.5 text-xs bg-purple-900/20 border border-purple-800 text-purple-400 rounded-lg px-3 py-2 hover:bg-purple-800/30 transition-colors"
              data-testid="ptp-btn">
              <Calendar size={13} /> PTP
            </button>
            <button onClick={() => alert("Escalada a gerencia registrada")}
              className="flex items-center gap-1.5 text-xs bg-red-900/20 border border-red-800 text-red-400 rounded-lg px-3 py-2 hover:bg-red-800/30 transition-colors"
              data-testid="escalar-btn">
              <AlertTriangle size={13} /> Escalar
            </button>
          </div>
        </div>
      </div>

      {/* BUILD 9 — Sección de Inteligencia Predictiva */}
      {learning && (
        <div className="space-y-2 mb-4">
          {/* Alerta predictiva (naranja) — solo si DPD=0 y prob > 0.60 */}
          {learning.alerta_deterioro?.alerta && dpd_actual === 0 && (
            <div
              className="flex items-start gap-3 rounded-xl border border-orange-600/40 bg-orange-900/15 px-4 py-3"
              data-testid="learning-alerta-deterioro"
            >
              <TrendingDown size={16} className="text-orange-400 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-xs font-bold text-orange-300">
                  Alerta predictiva: {Math.round((learning.alerta_deterioro.probabilidad || 0) * 100)}% de probabilidad de no pagar
                </p>
                {learning.alerta_deterioro.señales?.length > 0 && (
                  <p className="text-[11px] text-orange-400/80 mt-0.5">
                    Señales: {learning.alerta_deterioro.señales.join(" · ")}
                  </p>
                )}
                <p className="text-[11px] text-orange-300/70 mt-0.5">
                  {learning.alerta_deterioro.accion_sugerida}
                </p>
              </div>
            </div>
          )}
          {/* Recomendación de contacto (azul) — solo si hay patrón con confianza >= 0.6 */}
          {learning.recomendacion?.tiene_patron && (learning.recomendacion?.confianza || 0) >= 0.6 && (
            <div
              className="flex items-start gap-3 rounded-xl border border-blue-600/40 bg-blue-900/15 px-4 py-3"
              data-testid="learning-recomendacion"
            >
              <Brain size={16} className="text-blue-400 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-xs font-bold text-blue-300">
                  El sistema recomienda: {learning.recomendacion.recomendacion}
                </p>
                <p className="text-[11px] text-blue-400/70 mt-0.5">
                  Tasa de éxito histórica: {learning.recomendacion.tasa_exito}% ·
                  Confianza: {Math.round((learning.recomendacion.confianza || 0) * 100)}%
                  {learning.recomendacion.scope === "segmento" && " (patrón de segmento)"}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        {/* Situación crédito */}
        <Section title="Situación del crédito">
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-[#091529] rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-slate-400 mb-0.5">Pagadas</p>
              <p className="text-base font-bold text-emerald-400">{cuotas_pagadas}</p>
            </div>
            <div className="bg-[#091529] rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-slate-400 mb-0.5">Vencidas</p>
              <p className={`text-base font-bold ${cuotas_vencidas > 0 ? "text-red-400" : "text-slate-400"}`}>{cuotas_vencidas}</p>
            </div>
            <div className="bg-[#091529] rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-slate-400 mb-0.5">Pendientes</p>
              <p className="text-base font-bold text-blue-400">{cuotas_pendientes}</p>
            </div>
          </div>
          <div className="space-y-1.5 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Mora acumulada</span>
              <span className={mora_acumulada > 0 ? "text-red-400 font-semibold" : "text-slate-300"}>{fmt(mora_acumulada)}</span>
            </div>
            {proxima_cuota && (
              <div className="flex justify-between">
                <span className="text-slate-400">Próxima cuota #{proxima_cuota.numero}</span>
                <span className="text-slate-300">{fmt(proxima_cuota.valor)} · {fmtD(proxima_cuota.fecha_vencimiento)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-400">Saldo total</span>
              <span className="text-white font-semibold">{fmt(loan?.saldo_pendiente || 0)}</span>
            </div>
          </div>
        </Section>

        {/* Contacto (editable) */}
        <Section title={
          <div className="flex items-center justify-between w-full">
            <span>Contacto</span>
            {!editMode
              ? <button onClick={() => setEditMode(true)} className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1"><Edit2 size={10} /> Editar</button>
              : (
                <div className="flex gap-2">
                  <button onClick={() => setEditMode(false)} className="text-[10px] text-slate-400 hover:text-white flex items-center gap-1"><X size={10} /> Cancelar</button>
                  <button onClick={handleSaveDatos} className="text-[10px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1"><Check size={10} /> Guardar</button>
                </div>
              )
            }
          </div>
        }>
          {editMode ? (
            <div className="space-y-2 text-sm">
              {[
                { label: "Tel. alternativo", key: "telefono_alternativo" },
                { label: "Dirección", key: "direccion" },
                { label: "Barrio", key: "barrio" },
                { label: "Ciudad", key: "ciudad" },
                { label: "Email", key: "email" },
                { label: "Ocupación", key: "ocupacion" },
              ].map(f => (
                <div key={f.key}>
                  <Label className="text-[10px] text-slate-500">{f.label}</Label>
                  <Input value={editDatos[f.key] || ""} onChange={e => setEditDatos((p: any) => ({...p, [f.key]: e.target.value}))}
                    className="mt-0.5 h-7 text-xs bg-[#091529] border-[#1E3A5F] text-white" />
                </div>
              ))}
              <div className="pt-1">
                <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Referencia 1</p>
                <div className="grid grid-cols-3 gap-1">
                  {["nombre", "telefono", "parentesco"].map(k => (
                    <Input key={k} placeholder={k} value={editDatos.referencia_1?.[k] || ""}
                      onChange={e => setEditDatos((p: any) => ({...p, referencia_1: {...p.referencia_1, [k]: e.target.value}}))}
                      className="h-7 text-xs bg-[#091529] border-[#1E3A5F] text-white" />
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Tel. principal</span><span className="text-white font-mono">{telefono}</span></div>
              {crm?.telefono_alternativo && <div className="flex justify-between"><span className="text-slate-400">Tel. alternativo</span><span className="text-white font-mono">{crm.telefono_alternativo}</span></div>}
              {crm?.direccion && <div className="flex justify-between"><span className="text-slate-400">Dirección</span><span className="text-white text-right max-w-[55%]">{crm.direccion}{crm.barrio ? `, ${crm.barrio}` : ""}</span></div>}
              {crm?.ocupacion && <div className="flex justify-between"><span className="text-slate-400">Ocupación</span><span className="text-white">{crm.ocupacion}</span></div>}
              {crm?.referencia_1?.nombre && <div className="flex justify-between"><span className="text-slate-400">Ref 1</span><span className="text-white">{crm.referencia_1.nombre} ({crm.referencia_1.parentesco})</span></div>}
              {crm?.referencia_2?.nombre && <div className="flex justify-between"><span className="text-slate-400">Ref 2</span><span className="text-white">{crm.referencia_2.nombre} ({crm.referencia_2.parentesco})</span></div>}
            </div>
          )}
        </Section>
      </div>

      {/* Timeline gestiones */}
      <Section title={`Timeline de gestiones (${gestiones?.length || 0})`}>
        {!gestiones?.length ? (
          <p className="text-xs text-slate-500">Sin gestiones registradas aún.</p>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto pr-1" data-testid="gestiones-timeline">
            {gestiones.map((g: any) => (
              <div key={g.id} className="flex gap-3 border-b border-[#1E3A5F]/50 pb-2">
                <div className="w-1 flex-shrink-0 rounded-full bg-blue-600 mt-1 self-stretch" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold text-blue-400 uppercase">{g.canal}</span>
                    <span className="text-[10px] text-slate-400">{g.resultado?.replace(/_/g, " ")}</span>
                    <span className="text-[10px] text-slate-600 ml-auto">{fmtD(g.created_at)}</span>
                  </div>
                  {g.nota && <p className="text-xs text-slate-300 mt-0.5 truncate">{g.nota}</p>}
                  {g.ptp_fecha && <p className="text-[10px] text-purple-400 mt-0.5 flex items-center gap-1"><Calendar size={9} /> PTP: {g.ptp_fecha}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* WhatsApp history */}
      {whatsapp_gestiones?.length > 0 && (
        <Section title={`WhatsApp — Historial (${whatsapp_gestiones.length})`}>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1" data-testid="whatsapp-gestiones-timeline">
            {whatsapp_gestiones.map((g: any, i: number) => {
              const isEnviado = g.tipo === "enviado";
              const TEMPLATE_LABELS: Record<string, string> = {
                recordatorio_preventivo: "Recordatorio D-2",
                vencimiento_hoy: "Vencimiento hoy",
                mora_d1: "Mora D+1",
                confirmacion_pago: "Confirmación pago",
                mora_severa: "Mora severa",
                respuesta_automatica: "Respuesta auto",
                libre: "Mensaje libre",
              };
              const templateLabel = TEMPLATE_LABELS[g.template] || g.template || "WhatsApp";
              return (
                <div key={i} className={`rounded-lg px-3 py-2 text-xs ${isEnviado ? "bg-[#0D2A1A] border border-green-900/50" : "bg-[#0D1E3A] border border-[#1E3A5F]/50"}`}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className={`font-semibold ${isEnviado ? "text-green-400" : "text-blue-400"}`}>
                      {isEnviado ? "→ Enviado" : "← Recibido"}
                      {" · "}
                      <span className="font-normal text-slate-400">{templateLabel}</span>
                    </span>
                    <span className="text-[10px] text-slate-600 whitespace-nowrap">{fmtD(g.fecha)}</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed line-clamp-3">{g.mensaje}</p>
                  {g.intencion && g.intencion !== "NO_RECONOCIDA" && (
                    <span className="inline-block mt-1 text-[10px] bg-purple-900/40 text-purple-300 px-1.5 py-0.5 rounded">
                      Intención: {g.intencion}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Notas del cobrador */}
      <Section title="Notas del cobrador">
        <div className="space-y-2 mb-3 max-h-40 overflow-y-auto pr-1" data-testid="notas-list">
          {!crm?.notas?.length ? (
            <p className="text-xs text-slate-500">Sin notas aún.</p>
          ) : crm.notas.map((n: any) => (
            <div key={n.id} className="bg-[#091529] rounded-lg px-3 py-2">
              <p className="text-xs text-white">{n.texto}</p>
              <p className="text-[10px] text-slate-500 mt-0.5">{n.autor} · {fmtD(n.created_at)}</p>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <Input value={nota} onChange={e => setNota(e.target.value)}
            placeholder="Agregar nota..."
            className="flex-1 text-sm bg-[#091529] border-[#1E3A5F] text-white"
            onKeyDown={e => e.key === "Enter" && handleAddNota()}
            data-testid="nota-input" />
          <Button onClick={handleAddNota} disabled={addingNota || !nota.trim()}
            size="sm" className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="nota-add-btn">
            {addingNota ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          </Button>
        </div>
      </Section>

      {/* Modals */}
      {showGestion && (
        <GestionModal
          loanbook_id={id || ""}
          cliente_nombre={nombre}
          onClose={() => setShowGestion(false)}
          onSave={() => { setShowGestion(false); fetchData(); }}
        />
      )}

      <Dialog open={showPTP} onOpenChange={setShowPTP}>
        <DialogContent className="bg-[#0D1E3A] border-[#1E3A5F] text-white max-w-sm">
          <DialogHeader><DialogTitle className="text-white text-base">Registrar PTP</DialogTitle></DialogHeader>
          <div className="space-y-3 pt-1">
            <div>
              <Label className="text-xs text-slate-400">Fecha promesa de pago</Label>
              <Input type="date" value={ptpFecha} onChange={e => setPtpFecha(e.target.value)}
                className="mt-1 bg-[#091529] border-[#1E3A5F] text-white" data-testid="ptp-modal-fecha" />
            </div>
            <div>
              <Label className="text-xs text-slate-400">Monto prometido</Label>
              <Input type="number" value={ptpMonto} onChange={e => setPtpMonto(e.target.value)}
                placeholder="190000" className="mt-1 bg-[#091529] border-[#1E3A5F] text-white" data-testid="ptp-modal-monto" />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowPTP(false)} className="flex-1 border-[#1E3A5F] text-slate-400">Cancelar</Button>
              <Button onClick={handlePTP} className="flex-1 bg-purple-600 hover:bg-purple-700 text-white" data-testid="ptp-save-btn">Guardar PTP</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
}
