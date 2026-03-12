import React from "react";
import { formatCOP } from "../utils/formatters";
import { CheckCircle, XCircle } from "lucide-react";

export default function JournalEntryPreview({ entries = [], title = "PREVIEW ASIENTO CONTABLE", period }) {
  const totalDebit = entries.reduce((s, e) => s + (parseFloat(e.debit) || 0), 0);
  const totalCredit = entries.reduce((s, e) => s + (parseFloat(e.credit) || 0), 0);
  const diff = Math.abs(totalDebit - totalCredit);
  const isBalanced = diff < 1;

  if (entries.length === 0) return null;

  return (
    <div className="journal-preview animate-fadeInUp" data-testid="journal-entry-preview">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#F8FAFC] border-b border-slate-200">
        <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">{title}</span>
        <div className="flex items-center gap-3">
          {period && <span className="text-xs text-slate-400">Período: {period}</span>}
          {isBalanced ? (
            <span className="flex items-center gap-1 text-xs font-semibold text-green-600">
              <CheckCircle size={13} /> El asiento cuadra
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs font-semibold text-red-600">
              <XCircle size={13} /> Diferencia: {formatCOP(diff)}
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <th className="text-left px-4 py-2">Cuenta</th>
              <th className="text-right px-4 py-2 w-32">Débito</th>
              <th className="text-right px-4 py-2 w-32">Crédito</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-2 text-slate-700">
                  {entry.account ? (
                    <span>
                      <span className="font-mono text-xs text-slate-400 mr-2">[{entry.account.code}]</span>
                      {entry.account.name}
                    </span>
                  ) : (
                    <span className="text-slate-400 italic">Sin cuenta seleccionada</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right num-right">
                  {entry.debit > 0 ? (
                    <span className="font-semibold text-blue-700">{formatCOP(entry.debit)}</span>
                  ) : ""}
                </td>
                <td className="px-4 py-2 text-right num-right">
                  {entry.credit > 0 ? (
                    <span className="font-semibold text-orange-700">{formatCOP(entry.credit)}</span>
                  ) : ""}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold">
              <td className="px-4 py-2.5 text-xs uppercase text-slate-600">TOTALES</td>
              <td className="px-4 py-2.5 text-right num-right text-blue-700">{formatCOP(totalDebit)}</td>
              <td className="px-4 py-2.5 text-right num-right text-orange-700">{formatCOP(totalCredit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {!isBalanced && totalDebit > 0 && totalCredit > 0 && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100">
          <p className="text-xs text-red-600 font-medium">
            El asiento no cuadra. Diferencia de {formatCOP(diff)}. El botón de guardar permanecerá desactivado.
          </p>
        </div>
      )}
    </div>
  );
}
