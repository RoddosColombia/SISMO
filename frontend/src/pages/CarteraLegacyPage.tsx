import React, { useState, useEffect, useCallback } from "react";
import { X, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CreditoLegacy {
  codigo_sismo: string;
  cedula: string;
  numero_credito_original: string;
  nombre_completo: string;
  placa?: string;
  aliado: string;
  estado: string;
  estado_legacy_excel: string;
  saldo_actual: number;
  saldo_inicial: number;
  dias_mora_maxima?: number;
  pct_on_time?: number;
  score_total?: number;
  decision_historica?: string;
  analisis_texto?: string;
  alegra_contact_id?: string;
  pagos_recibidos?: PagoRegistrado[];
}

interface PagoRegistrado {
  fecha?: string;
  monto?: number;
  alegra_journal_id?: string;
}

interface Stats {
  total_creditos?: number;
  saldo_total?: number;
  activos?: number;
  saldados?: number;
  en_mora?: number;
  al_dia?: number;
  por_aliado?: { aliado: string; count: number; saldo: number }[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const COP = (n: number) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);

const ALIADOS = ["RODDOS_Directo", "Motai", "MDT", "Yamarinos", "BMR", "sin_aliado"];

function EstadoBadge({ estado, excel }: { estado: string; excel: string }) {
  const mora = excel === "En Mora";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
      mora ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
    }`}>
      {mora ? "En Mora" : "Al Día"}
    </span>
  );
}

// ── Drawer de detalle ─────────────────────────────────────────────────────────

function DrawerDetalle({ credito, onClose }: { credito: CreditoLegacy; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white shadow-xl overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white z-10">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{credito.nombre_completo}</h2>
            <p className="text-xs text-gray-500 font-mono">{credito.codigo_sismo}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Datos básicos */}
          <div className="grid grid-cols-2 gap-4">
            {[
              ["Cédula", credito.cedula],
              ["Crédito #", credito.numero_credito_original],
              ["Placa", credito.placa || "—"],
              ["Aliado", credito.aliado],
              ["Estado", credito.estado],
              ["Excel", credito.estado_legacy_excel],
            ].map(([label, val]) => (
              <div key={label}>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{label}</p>
                <p className="text-sm font-medium text-gray-900">{val}</p>
              </div>
            ))}
          </div>

          {/* Saldos */}
          <div className="grid grid-cols-2 gap-4 bg-gray-50 rounded-lg p-4">
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider">Saldo inicial</p>
              <p className="text-lg font-bold text-gray-900">{COP(credito.saldo_inicial)}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider">Saldo actual</p>
              <p className={`text-lg font-bold ${credito.saldo_actual > 0 ? "text-red-600" : "text-emerald-600"}`}>
                {COP(credito.saldo_actual)}
              </p>
            </div>
          </div>

          {/* Scoring */}
          <div className="grid grid-cols-3 gap-3">
            {credito.score_total != null && (
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">Score</p>
                <p className="text-xl font-bold text-gray-900">{credito.score_total.toFixed(1)}</p>
              </div>
            )}
            {credito.pct_on_time != null && (
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">% Al día</p>
                <p className="text-xl font-bold text-gray-900">{(credito.pct_on_time * 100).toFixed(0)}%</p>
              </div>
            )}
            {credito.dias_mora_maxima != null && (
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">Días mora</p>
                <p className={`text-xl font-bold ${credito.dias_mora_maxima > 30 ? "text-red-600" : "text-amber-600"}`}>
                  {credito.dias_mora_maxima}
                </p>
              </div>
            )}
          </div>

          {/* Decisión + análisis */}
          {credito.decision_historica && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Decisión histórica</p>
              <p className="text-sm text-gray-700">{credito.decision_historica}</p>
            </div>
          )}
          {credito.analisis_texto && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Análisis</p>
              <p className="text-xs text-gray-600 leading-relaxed">{credito.analisis_texto}</p>
            </div>
          )}

          {/* Pagos */}
          <div>
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">
              Pagos registrados ({credito.pagos_recibidos?.length ?? 0})
            </p>
            {!credito.pagos_recibidos?.length ? (
              <p className="text-xs text-gray-500">Sin pagos registrados</p>
            ) : (
              <div className="space-y-2">
                {credito.pagos_recibidos.map((p, i) => (
                  <div key={i} className="flex items-center justify-between bg-emerald-50 rounded-md px-3 py-2">
                    <span className="text-xs text-gray-600">{p.fecha || "—"}</span>
                    <span className="text-sm font-semibold text-emerald-700">{p.monto ? COP(p.monto) : "—"}</span>
                    {p.alegra_journal_id && (
                      <span className="text-[10px] font-mono text-gray-400">J#{p.alegra_journal_id}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CarteraLegacyPage() {
  const { api } = useAuth();

  const [creditos, setCreditos] = useState<CreditoLegacy[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CreditoLegacy | null>(null);
  const [detalle, setDetalle] = useState<CreditoLegacy | null>(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);

  // Filters
  const [estado, setEstado] = useState("");
  const [aliado, setAliado] = useState("");
  const [enMora, setEnMora] = useState<string>("");

  // Pagination
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const LIMIT = 50;

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get("/cartera-legacy/stats");
      setStats(res.data?.data ?? {});
    } catch { /* silent */ }
  }, [api]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, limit: LIMIT };
      if (estado) params.estado = estado;
      if (aliado) params.aliado = aliado;
      if (enMora !== "") params.en_mora = enMora === "true";

      const res = await api.get("/cartera-legacy", { params });
      setCreditos(res.data?.data ?? []);
      setTotal(res.data?.total ?? 0);
      setPages(res.data?.pages ?? 1);
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  }, [api, page, estado, aliado, enMora]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { setPage(1); }, [estado, aliado, enMora]);
  useEffect(() => { fetchList(); }, [fetchList]);

  async function openDetalle(credito: CreditoLegacy) {
    setSelected(credito);
    setLoadingDetalle(true);
    try {
      const res = await api.get(`/cartera-legacy/${credito.codigo_sismo}`);
      setDetalle(res.data?.data ?? credito);
    } catch {
      setDetalle(credito);
    } finally {
      setLoadingDetalle(false);
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Cartera Legacy</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {total} créditos · {stats.saldo_total != null ? COP(stats.saldo_total) : "…"} saldo total
          </p>
        </div>
        <button onClick={() => { fetchList(); fetchStats(); }} className="p-2 rounded-md hover:bg-gray-100 text-gray-500">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Stats cards */}
      <div className="px-6 py-3 flex gap-3 flex-shrink-0">
        {[
          { label: "Activos", val: stats.activos, color: "text-gray-900" },
          { label: "En mora", val: stats.en_mora, color: "text-red-600" },
          { label: "Al día", val: stats.al_dia, color: "text-emerald-600" },
          { label: "Saldados", val: stats.saldados, color: "text-gray-500" },
        ].map(({ label, val, color }) => (
          <div key={label} className="bg-white rounded-lg border border-gray-100 px-4 py-2 flex-1 text-center shadow-sm">
            <p className="text-[10px] text-gray-400 uppercase tracking-wider">{label}</p>
            <p className={`text-xl font-bold ${color}`}>{val ?? "—"}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="px-6 pb-3 flex gap-3 flex-shrink-0 flex-wrap">
        <select
          value={estado}
          onChange={e => setEstado(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-white outline-none focus:ring-2 focus:ring-emerald-100"
        >
          <option value="">Todos los estados</option>
          <option value="activo">Activo</option>
          <option value="saldado">Saldado</option>
          <option value="castigado">Castigado</option>
        </select>
        <select
          value={aliado}
          onChange={e => setAliado(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-white outline-none focus:ring-2 focus:ring-emerald-100"
        >
          <option value="">Todos los aliados</option>
          {ALIADOS.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select
          value={enMora}
          onChange={e => setEnMora(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-white outline-none focus:ring-2 focus:ring-emerald-100"
        >
          <option value="">Mora / Al día</option>
          <option value="true">En Mora</option>
          <option value="false">Al Día</option>
        </select>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 pb-4">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">Cargando...</div>
        ) : creditos.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
            {total === 0 ? "Sin datos — ejecuta BUILD 0.2 para migrar los créditos." : "No hay resultados con los filtros aplicados."}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Código", "Cliente", "Cédula", "Placa", "Aliado", "Estado", "Saldo", "Días mora"].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {creditos.map(c => (
                  <tr
                    key={c.codigo_sismo}
                    onClick={() => openDetalle(c)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{c.codigo_sismo}</td>
                    <td className="px-4 py-3 font-medium text-gray-900 max-w-[180px] truncate">{c.nombre_completo}</td>
                    <td className="px-4 py-3 text-gray-600 font-mono text-xs">{c.cedula}</td>
                    <td className="px-4 py-3 text-gray-600">{c.placa || "—"}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{c.aliado}</td>
                    <td className="px-4 py-3">
                      <EstadoBadge estado={c.estado} excel={c.estado_legacy_excel} />
                    </td>
                    <td className="px-4 py-3 font-semibold text-gray-900 text-right whitespace-nowrap">
                      {COP(c.saldo_actual)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {c.dias_mora_maxima != null ? (
                        <span className={`font-semibold ${c.dias_mora_maxima > 30 ? "text-red-600" : "text-amber-600"}`}>
                          {c.dias_mora_maxima}
                        </span>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
            <span>{total} registros · página {page} de {pages}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage(p => Math.min(pages, p + 1))}
                disabled={page === pages}
                className="p-1.5 rounded-md border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {selected && (
        loadingDetalle ? (
          <div className="fixed inset-0 z-50 flex justify-end">
            <div className="absolute inset-0 bg-black/20" onClick={() => setSelected(null)} />
            <div className="relative w-full max-w-lg bg-white shadow-xl flex items-center justify-center">
              <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          </div>
        ) : detalle ? (
          <DrawerDetalle credito={detalle} onClose={() => { setSelected(null); setDetalle(null); }} />
        ) : null
      )}
    </div>
  );
}
