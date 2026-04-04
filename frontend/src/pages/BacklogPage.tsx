import React, { useState, useEffect, useCallback } from "react";
import { Clock, CheckCircle, XCircle, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Sugerencia {
  id: number;
  titulo: string;
  cuenta_debito: number;
  cuenta_debito_nombre: string;
  cuenta_credito: number;
  cuenta_credito_nombre: string;
  observaciones: string;
  razon: string;
  es_traslado: boolean;
}

interface BacklogItem {
  backlog_hash: string;
  banco: string;
  extracto: string;
  fecha: string;
  descripcion: string;
  monto: number;
  tipo: string;
  confianza_motor: number;
  cuenta_sugerida?: number;
  cuenta_debito_sugerida?: number;
  cuenta_credito_sugerida?: number;
  es_transferencia_interna?: boolean;
  razon_baja_confianza?: string;
  estado: "pendiente" | "causado" | "descartado";
  journal_alegra_id?: string;
  creado_at: string;
  _id?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatCOP(n: number) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency", currency: "COP", minimumFractionDigits: 0,
  }).format(n);
}

function EstadoBadge({ estado }: { estado: string }) {
  if (estado === "pendiente") return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700">
      <Clock size={10} /> Pendiente
    </span>
  );
  if (estado === "causado") return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700">
      <CheckCircle size={10} /> Causado
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-500">
      <XCircle size={10} /> Descartado
    </span>
  );
}

// ── Modal Causar con sugerencias inteligentes ─────────────────────────────────

function ModalCausar({
  item, onClose, onConfirm, loading, api,
}: {
  item: BacklogItem;
  onClose: () => void;
  onConfirm: (cuentaDebito: number, cuentaCredito: number, obs: string) => void;
  loading: boolean;
  api: any;
}) {
  const [sugerencias, setSugerencias] = useState<Sugerencia[]>([]);
  const [loadingSug, setLoadingSug] = useState(true);
  const [seleccionada, setSeleccionada] = useState(0);
  const [obs, setObs] = useState("");

  useEffect(() => {
    const id = item._id || item.backlog_hash;
    setLoadingSug(true);
    api.get(`/contabilidad_pendientes/backlog/sugerencias/${id}`)
      .then((r: any) => {
        const sugs: Sugerencia[] = r.data.sugerencias || [];
        setSugerencias(sugs);
        if (sugs.length > 0) {
          setSeleccionada(0);
          setObs(sugs[0].observaciones);
        }
      })
      .catch(() => {
        // Fallback sin nombres si el endpoint falla
        const banco = item.banco || "bbva";
        const bancoCuenta: Record<string, number> = { bbva: 5318, bancolombia: 5314, davivienda: 5322, nequi: 5310 };
        const fb: Sugerencia = {
          id: 1, titulo: "Gastos generales",
          cuenta_debito: 5493, cuenta_debito_nombre: "Gastos generales",
          cuenta_credito: bancoCuenta[banco] || 5318, cuenta_credito_nombre: banco.toUpperCase(),
          observaciones: item.descripcion, razon: "Cuenta comodín",
          es_traslado: false,
        };
        setSugerencias([fb]);
        setObs(item.descripcion);
      })
      .finally(() => setLoadingSug(false));
  }, []);  // eslint-disable-line

  const sug = sugerencias[seleccionada];
  const esTraslado = sug?.es_traslado;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6">
        {/* Header */}
        <h2 className="text-base font-bold mb-1" style={{ color: "#1c1b1f" }}>Causar movimiento</h2>
        <p className="text-xs mb-1" style={{ color: "#9e9a97" }}>
          {item.fecha} · {item.banco.toUpperCase()} · {formatCOP(Math.abs(item.monto))}
        </p>
        <p className="text-xs font-medium mb-5 truncate" style={{ color: "#49454f" }} title={item.descripcion}>
          {item.descripcion}
        </p>

        {loadingSug ? (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-[#0F2A5C] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Radio group de sugerencias */}
            <div className="mb-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "#9e9a97" }}>
                Asiento contable — selecciona una opción
              </p>
              <div className="space-y-2">
                {sugerencias.map((s, i) => (
                  <label
                    key={s.id}
                    className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                      seleccionada === i
                        ? "border-[#0f2a5c] bg-[#0f2a5c]/[0.04]"
                        : "border-slate-200 bg-slate-50 hover:bg-slate-100"
                    }`}
                    onClick={() => { setSeleccionada(i); setObs(s.observaciones); }}
                  >
                    <input
                      type="radio"
                      checked={seleccionada === i}
                      onChange={() => { setSeleccionada(i); setObs(s.observaciones); }}
                      className="mt-0.5 accent-[#0f2a5c]"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-bold" style={{ color: "#0f2a5c" }}>{s.titulo}</span>
                        {s.es_traslado && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-semibold">
                            Traslado
                          </span>
                        )}
                      </div>
                      <div className="text-[11px]" style={{ color: "#49454f" }}>
                        <span className="font-semibold">{s.cuenta_debito_nombre}</span>
                        <span style={{ color: "#9e9a97" }}> → </span>
                        <span className="font-semibold">{s.cuenta_credito_nombre}</span>
                      </div>
                      <div className="text-[10px] mt-0.5" style={{ color: "#9e9a97" }}>{s.razon}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Descripción del journal */}
            <div className="mb-4">
              <label className="text-xs font-semibold block mb-1" style={{ color: "#49454f" }}>
                Descripción del journal en Alegra
              </label>
              <input
                type="text"
                value={obs}
                onChange={e => setObs(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                style={{ borderColor: "rgba(28,27,31,0.15)" }}
              />
            </div>

            {/* Aviso traslado */}
            {esTraslado && (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-xs text-amber-700">
                  ⚠️ Este movimiento es un traslado interno. Se recomienda <strong>Descartar</strong> en su lugar.
                </p>
              </div>
            )}
          </>
        )}

        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
            Cancelar
          </Button>
          <Button
            className="flex-1"
            style={{ background: esTraslado ? "#9e9a97" : "#006e2a", color: "#fff" }}
            onClick={() => sug && onConfirm(sug.cuenta_debito, sug.cuenta_credito, obs)}
            disabled={loading || loadingSug || !sug}
          >
            {loading ? "Causando..." : esTraslado ? "Causar de todas formas" : "Causar en Alegra"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Modal Descartar ───────────────────────────────────────────────────────────

function ModalDescartar({
  item, onClose, onConfirm, loading,
}: {
  item: BacklogItem;
  onClose: () => void;
  onConfirm: (razon: string) => void;
  loading: boolean;
}) {
  const [razon, setRazon] = useState("No corresponde a RODDOS");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-base font-bold mb-1" style={{ color: "#1c1b1f" }}>Descartar movimiento</h2>
        <p className="text-xs mb-4 truncate" style={{ color: "#9e9a97" }}>
          {item.fecha} · {item.descripcion}
        </p>
        <div>
          <label className="text-xs font-semibold block mb-1" style={{ color: "#49454f" }}>Razón</label>
          <input
            type="text"
            value={razon}
            onChange={e => setRazon(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm"
            style={{ borderColor: "rgba(28,27,31,0.15)" }}
          />
        </div>
        <div className="flex gap-2 mt-5">
          <Button variant="outline" className="flex-1" onClick={onClose} disabled={loading}>Cancelar</Button>
          <Button
            className="flex-1"
            style={{ background: "#dc2626", color: "#fff" }}
            onClick={() => onConfirm(razon)}
            disabled={loading || !razon}
          >
            {loading ? "Descartando..." : "Descartar"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BacklogPage() {
  const { api } = useAuth();

  const [items, setItems] = useState<BacklogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const [filterBanco, setFilterBanco] = useState("");
  const [filterEstado, setFilterEstado] = useState("pendiente");
  const [filterMes, setFilterMes] = useState("");

  const [stats, setStats] = useState<{
    total_pendientes: number; total_causados: number; total_descartados: number;
    por_banco: Record<string, number>;
  } | null>(null);

  const [causarItem, setCausarItem] = useState<BacklogItem | null>(null);
  const [descartarItem, setDescartarItem] = useState<BacklogItem | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get("/contabilidad_pendientes/backlog/stats");
      setStats(res.data);
    } catch { /* silent */ }
  }, [api]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page };
      if (filterBanco) params.banco = filterBanco;
      if (filterEstado) params.estado = filterEstado;
      if (filterMes) params.mes = filterMes;
      const res = await api.get("/contabilidad_pendientes/backlog/listado", { params });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch {
      toast.error("Error cargando backlog");
    } finally {
      setLoading(false);
    }
  }, [api, page, filterBanco, filterEstado, filterMes]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { setPage(1); }, [filterBanco, filterEstado, filterMes]);
  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleCausar = async (id: string, d: number, c: number, obs: string) => {
    setActionLoading(true);
    try {
      await api.patch(`/contabilidad_pendientes/backlog/${id}/causar`, {
        cuenta_debito: d, cuenta_credito: c, observaciones: obs,
      });
      toast.success("Movimiento causado en Alegra ✅");
      setCausarItem(null);
      fetchItems(); fetchStats();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Error al causar");
    } finally { setActionLoading(false); }
  };

  const handleDescartar = async (id: string, razon: string) => {
    setActionLoading(true);
    try {
      await api.patch(`/contabilidad_pendientes/backlog/${id}/descartar`, { razon });
      toast.success("Movimiento descartado");
      setDescartarItem(null);
      fetchItems(); fetchStats();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Error al descartar");
    } finally { setActionLoading(false); }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="max-w-6xl mx-auto space-y-5">

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {[
            { label: "Pendientes", value: stats.total_pendientes, color: "#b45309" },
            { label: "Causados", value: stats.total_causados, color: "#166534" },
            { label: "Descartados", value: stats.total_descartados, color: "#64748b" },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl p-4 shadow-sm border" style={{ borderColor: "rgba(28,27,31,0.06)" }}>
              <div className="text-xs font-medium mb-1" style={{ color: "#9e9a97" }}>{s.label}</div>
              <div className="text-2xl font-black" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
          {Object.entries(stats.por_banco || {}).map(([banco, count]) => (
            <div key={banco} className="bg-white rounded-xl p-4 shadow-sm border" style={{ borderColor: "rgba(28,27,31,0.06)" }}>
              <div className="text-xs font-medium mb-1" style={{ color: "#9e9a97" }}>{banco.toUpperCase()}</div>
              <div className="text-2xl font-black" style={{ color: "#0f2a5c" }}>{count as number}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl p-4 shadow-sm border flex flex-wrap gap-3 items-center" style={{ borderColor: "rgba(28,27,31,0.06)" }}>
        <select value={filterEstado} onChange={e => setFilterEstado(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5" style={{ borderColor: "rgba(28,27,31,0.15)" }}>
          <option value="">Todos los estados</option>
          <option value="pendiente">Pendiente</option>
          <option value="causado">Causado</option>
          <option value="descartado">Descartado</option>
        </select>
        <select value={filterBanco} onChange={e => setFilterBanco(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5" style={{ borderColor: "rgba(28,27,31,0.15)" }}>
          <option value="">Todos los bancos</option>
          <option value="bbva">BBVA</option>
          <option value="bancolombia">Bancolombia</option>
          <option value="nequi">Nequi</option>
          <option value="davivienda">Davivienda</option>
        </select>
        <input type="month" value={filterMes} onChange={e => setFilterMes(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5" style={{ borderColor: "rgba(28,27,31,0.15)" }} />
        <button onClick={() => { fetchItems(); fetchStats(); }}
          className="ml-auto p-1.5 rounded-lg hover:bg-black/[0.04] transition" style={{ color: "#49454f" }}>
          <RefreshCw size={15} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden" style={{ borderColor: "rgba(28,27,31,0.06)" }}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-4 border-[#0F2A5C] border-t-[#C9A84C] rounded-full animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <AlertCircle size={32} style={{ color: "#9e9a97" }} />
            <p className="text-sm" style={{ color: "#9e9a97" }}>No hay movimientos</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(28,27,31,0.07)", background: "rgba(28,27,31,0.02)" }}>
                  {["Fecha", "Banco", "Descripción", "Monto", "Confianza", "Estado", "Acciones"].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "#9e9a97" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={item.backlog_hash || i}
                    style={{ borderBottom: "1px solid rgba(28,27,31,0.05)" }}
                    className="hover:bg-black/[0.01] transition">
                    <td className="px-4 py-3 text-xs font-mono" style={{ color: "#49454f" }}>{item.fecha}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-bold uppercase" style={{ color: "#0f2a5c" }}>{item.banco}</span>
                    </td>
                    <td className="px-4 py-3 max-w-[220px]">
                      <p className="text-xs truncate" style={{ color: "#1c1b1f" }} title={item.descripcion}>{item.descripcion}</p>
                      {item.razon_baja_confianza && (
                        <p className="text-[10px] mt-0.5" style={{ color: "#9e9a97" }}>{item.razon_baja_confianza}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs font-semibold font-mono" style={{ color: item.monto < 0 ? "#dc2626" : "#166534" }}>
                      {formatCOP(item.monto)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                          <div className="h-full rounded-full" style={{
                            width: `${Math.round(item.confianza_motor * 100)}%`,
                            background: item.confianza_motor < 0.5 ? "#dc2626" : item.confianza_motor < 0.7 ? "#f59e0b" : "#16a34a",
                          }} />
                        </div>
                        <span className="text-[10px]" style={{ color: "#9e9a97" }}>
                          {Math.round(item.confianza_motor * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3"><EstadoBadge estado={item.estado} /></td>
                    <td className="px-4 py-3">
                      {item.estado === "pendiente" && (
                        <div className="flex gap-1.5">
                          <button onClick={() => setCausarItem(item)}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition hover:opacity-80"
                            style={{ background: "rgba(0,110,42,0.08)", color: "#006e2a" }}>
                            Causar
                          </button>
                          <button onClick={() => setDescartarItem(item)}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition hover:opacity-80"
                            style={{ background: "rgba(220,38,38,0.08)", color: "#dc2626" }}>
                            Descartar
                          </button>
                        </div>
                      )}
                      {item.estado === "causado" && item.journal_alegra_id && (
                        <span className="text-[10px] font-mono" style={{ color: "#9e9a97" }}>
                          J-{item.journal_alegra_id}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: "1px solid rgba(28,27,31,0.06)" }}>
            <span className="text-xs" style={{ color: "#9e9a97" }}>
              {total} movimientos · página {page} de {totalPages}
            </span>
            <div className="flex gap-1.5">
              <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Anterior</Button>
              <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Siguiente</Button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {causarItem && (
        <ModalCausar
          item={causarItem}
          api={api}
          onClose={() => setCausarItem(null)}
          onConfirm={(d, c, o) => handleCausar(causarItem._id || causarItem.backlog_hash, d, c, o)}
          loading={actionLoading}
        />
      )}
      {descartarItem && (
        <ModalDescartar
          item={descartarItem}
          onClose={() => setDescartarItem(null)}
          onConfirm={(r) => handleDescartar(descartarItem._id || descartarItem.backlog_hash, r)}
          loading={actionLoading}
        />
      )}
    </div>
  );
}
