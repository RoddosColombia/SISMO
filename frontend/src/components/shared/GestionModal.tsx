import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { useAuth } from "../../contexts/AuthContext";

const CANALES = [
  { value: "llamada",   label: "📞 Llamada" },
  { value: "whatsapp",  label: "💬 WhatsApp" },
];

const RESULTADOS = [
  "contestó_pagará_hoy",
  "contestó_prometió_fecha",
  "contestó_no_pagará",
  "no_contestó",
  "número_equivocado",
  "respondió_pagará",
  "respondió_prometió_fecha",
  "visto_sin_respuesta",
  "no_entregado",
  "acuerdo_de_pago_firmado",
];

interface Props {
  loanbook_id: string;
  cliente_nombre: string;
  onClose: () => void;
  onSave?: () => void;
}

export function GestionModal({ loanbook_id, cliente_nombre, onClose, onSave }: Props) {
  const { api } = useAuth();
  const [canal, setCanal]         = useState("llamada");
  const [resultado, setResultado] = useState("");
  const [nota, setNota]           = useState("");
  const [ptpFecha, setPtpFecha]   = useState("");
  const [ptpMonto, setPtpMonto]   = useState("");
  const [saving, setSaving]       = useState(false);

  const needsPtp = resultado.includes("prometió") || resultado === "acuerdo_de_pago_firmado";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resultado) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { canal, resultado, nota };
      if (needsPtp && ptpFecha)  payload.ptp_fecha = ptpFecha;
      if (needsPtp && ptpMonto)  payload.ptp_monto = parseFloat(ptpMonto);
      await api.post(`/crm/${loanbook_id}/gestion`, payload);
      onSave?.();
      onClose();
    } catch {
      // toast shown by parent
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-[#0D1E3A] border-[#1E3A5F] text-white max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-base text-white">
            Registrar gestión — {cliente_nombre.split(" ")[0]}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          {/* Canal */}
          <div>
            <p className="text-xs text-slate-400 mb-1.5">Canal</p>
            <div className="flex gap-2">
              {CANALES.map(c => (
                <button
                  key={c.value} type="button"
                  onClick={() => setCanal(c.value)}
                  data-testid={`canal-btn-${c.value}`}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    canal === c.value
                      ? "bg-blue-600 border-blue-500 text-white"
                      : "bg-[#091529] border-[#1E3A5F] text-slate-300 hover:border-blue-600"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Resultado */}
          <div>
            <p className="text-xs text-slate-400 mb-1">Resultado</p>
            <select
              value={resultado} onChange={e => setResultado(e.target.value)}
              required
              data-testid="gestion-resultado-select"
              className="w-full bg-[#091529] border border-[#1E3A5F] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">— Seleccionar —</option>
              {RESULTADOS.map(r => (
                <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>

          {/* Nota */}
          <div>
            <p className="text-xs text-slate-400 mb-1">Nota (opcional)</p>
            <Textarea
              value={nota} onChange={e => setNota(e.target.value)}
              maxLength={500}
              placeholder="Observaciones..."
              data-testid="gestion-nota-input"
              className="bg-[#091529] border-[#1E3A5F] text-white text-sm min-h-[70px] resize-none"
            />
          </div>

          {/* PTP fields */}
          {needsPtp && (
            <div className="space-y-3 border border-blue-800/50 rounded-lg p-3 bg-blue-900/10">
              <p className="text-xs text-blue-400 font-medium">Promesa de pago</p>
              <div>
                <p className="text-xs text-slate-400 mb-1">Fecha acordada</p>
                <Input
                  type="date" value={ptpFecha} onChange={e => setPtpFecha(e.target.value)}
                  data-testid="gestion-ptp-fecha"
                  className="bg-[#091529] border-[#1E3A5F] text-white"
                />
              </div>
              {ptpFecha && (
                <div>
                  <p className="text-xs text-slate-400 mb-1">Monto prometido ($)</p>
                  <Input
                    type="number" value={ptpMonto} onChange={e => setPtpMonto(e.target.value)}
                    placeholder="0"
                    data-testid="gestion-ptp-monto"
                    className="bg-[#091529] border-[#1E3A5F] text-white"
                  />
                </div>
              )}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}
              className="flex-1 border-[#1E3A5F] text-slate-300 hover:bg-[#1E3A5F]">
              Cancelar
            </Button>
            <Button type="submit" disabled={!resultado || saving}
              data-testid="gestion-submit-btn"
              className="flex-1 bg-blue-600 hover:bg-blue-500 text-white">
              {saving ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
