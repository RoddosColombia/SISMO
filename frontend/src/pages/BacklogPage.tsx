import React, { useState, useEffect, useCallback } from "react";
import { Clock, CheckCircle, XCircle, AlertCircle, RefreshCw, AlertTriangle } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

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

// ── Plan de cuentas RODDOS completo (IDs reales de Alegra) ────────────────────
// Nunca usar ID 5495 — fallback siempre es 5493
const CUENTAS_GASTOS: { id: number; nombre: string; categoria: string; cuando_usar: string }[] = [
  { id: 5462, nombre: "Sueldos y salarios",       categoria: "Personal",     cuando_usar: "Pago de nómina a Alexa, Liz u otro empleado directo de RODDOS" },
  { id: 5470, nombre: "Honorarios",                categoria: "Personal",     cuando_usar: "Pagos a abogados, asesores, consultores o freelancers. PN 10% ReteFuente, PJ 11%" },
  { id: 5471, nombre: "Seguridad social",          categoria: "Personal",     cuando_usar: "Aportes a salud, pensión y ARL de empleados" },
  { id: 5472, nombre: "Dotaciones",                categoria: "Personal",     cuando_usar: "Compra de uniformes, elementos de protección o dotación para empleados" },
  { id: 5480, nombre: "Arrendamientos",            categoria: "Operaciones",  cuando_usar: "Pago mensual del arriendo del local. ReteFuente 3.5% + ReteICA 0.414%" },
  { id: 5484, nombre: "Servicios públicos / Tech", categoria: "Operaciones",  cuando_usar: "Facturas de Alegra, Mercately, software de gestión, servicios cloud (AWS, MongoDB)" },
  { id: 5487, nombre: "Teléfono / Internet",       categoria: "Operaciones",  cuando_usar: "Facturas de Tigo, Claro, ETB, planes de datos para el equipo" },
  { id: 5490, nombre: "Mantenimiento",             categoria: "Operaciones",  cuando_usar: "Reparaciones de equipos, muebles, moto de prueba, instalaciones del local" },
  { id: 5491, nombre: "Transporte",                categoria: "Operaciones",  cuando_usar: "Taxis, combustible, peajes, fletes para operación de RODDOS" },
  { id: 5493, nombre: "Gastos generales",          categoria: "Otros",        cuando_usar: "COMODÍN — usar cuando no encaja en ninguna cuenta específica. Revisar después." },
  { id: 5497, nombre: "Papelería y útiles",        categoria: "Operaciones",  cuando_usar: "Compra de papel, tinta, elementos de papelería y útiles de oficina" },
  { id: 5500, nombre: "Publicidad",                categoria: "Marketing",    cuando_usar: "Meta Ads, Instagram, volantes, pendones, cualquier pauta publicitaria de RODDOS" },
  { id: 5501, nombre: "Eventos",                   categoria: "Marketing",    cuando_usar: "Gastos de eventos comerciales, ferias, lanzamientos de productos" },
  { id: 5505, nombre: "ICA",                       categoria: "Impuestos",    cuando_usar: "Pago bimestral del Impuesto de Industria y Comercio a la Secretaría de Hacienda Bogotá" },
  { id: 5507, nombre: "IVA comisión bancaria",     categoria: "Financiero",   cuando_usar: "IVA cobrado sobre comisiones bancarias. Separar del gasto principal." },
  { id: 5508, nombre: "Comisiones bancarias",      categoria: "Financiero",   cuando_usar: "Cuota de manejo, comisiones por transferencias, cargos bancarios fijos mensuales" },
  { id: 5509, nombre: "GMF 4×1000",               categoria: "Financiero",   cuando_usar: "Gravamen al Movimiento Financiero. Aparece en extracto como '4X1000' o 'GMF'" },
  { id: 5510, nombre: "Seguros",                   categoria: "Financiero",   cuando_usar: "Pólizas de seguro del local, motos de demostración, responsabilidad civil" },
  { id: 5533, nombre: "Intereses financieros",     categoria: "Financiero",   cuando_usar: "Intereses pagados por préstamos bancarios o créditos de proveedores" },
  { id: 5534, nombre: "Intereses rentistas",       categoria: "Financiero",   cuando_usar: "Intereses pagados a personas naturales que prestan dinero a RODDOS (socios, terceros)" },
];

const CUENTAS_BANCOS: { id: number; nombre: string }[] = [
  { id: 5314, nombre: "Bancolombia 2029" },
  { id: 5318, nombre: "BBVA 0210" },
  { id: 5322, nombre: "Davivienda 482" },
  { id: 5310, nombre: "Nequi / Caja" },
  { id: 5311, nombre: "Caja Menor RODDOS (cód.PUC 11050502)" },
  { id: 11100507, nombre: "Global66 Colombia" },
];

const CUENTAS_INGRESOS: { id: number; nombre: string; cuando_usar: string }[] = [
  { id: 5327, nombre: "Créditos Directos RODDOS (cartera)", cuando_usar: "Pago de cuotas semanales de loanbooks activos" },
  { id: 5329, nombre: "CXC Socios",                         cuando_usar: "SOLO para retiros o gastos PERSONALES de Andrés (CC 80075452) o Iván (CC 80086601). NO para gastos operativos." },
];

const CUENTAS_RETENCIONES: { id: number; nombre: string }[] = [
  { id: 236505, nombre: "ReteFuente por pagar" },
  { id: 236560, nombre: "ReteICA por pagar" },
];

const BANCO_CUENTA: Record<string, number> = {
  bbva: 5318, bancolombia: 5314, davivienda: 5322, nequi: 5310, global66: 11100507,
};

const TODAS_CUENTAS_DEBITO = [
  ...CUENTAS_GASTOS,
  ...CUENTAS_BANCOS.map(c => ({ ...c, categoria: "Banco", cuando_usar: "Cuenta bancaria como débito (ingreso)" })),
  ...CUENTAS_INGRESOS.map(c => ({ ...c, categoria: "CXC/Ingresos" })),
  ...CUENTAS_RETENCIONES.map(c => ({ ...c, categoria: "Retenciones", cuando_usar: "Retención practicada" })),
];

const TODAS_CUENTAS_CREDITO = [
  ...CUENTAS_BANCOS.map(c => ({ ...c, categoria: "Banco", cuando_usar: "Cuenta bancaria origen del pago" })),
  ...CUENTAS_GASTOS,
  ...CUENTAS_INGRESOS.map(c => ({ ...c, categoria: "CXC/Ingresos" })),
  ...CUENTAS_RETENCIONES.map(c => ({ ...c, categoria: "Retenciones", cuando_usar: "Retención practicada" })),
];

function nombreCuenta(id: number): string {
  const todas = [...CUENTAS_GASTOS, ...CUENTAS_BANCOS, ...CUENTAS_INGRESOS, ...CUENTAS_RETENCIONES];
  return todas.find(c => c.id === id)?.nombre ?? `Cuenta ${id}`;
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

// ── Modal Causar ──────────────────────────────────────────────────────────────

function ModalCausar({
  item, onClose, onConfirm, loading,
}: {
  item: BacklogItem;
  onClose: () => void;
  onConfirm: (cuentaDebito: number, cuentaCredito: number, obs: string) => void;
  loading: boolean;
}) {
  const banco = item.banco?.toLowerCase() ?? "bbva";
  const cuentaBanco = BANCO_CUENTA[banco] ?? 5318;
  const tipo = (item.tipo ?? "EGRESO").toUpperCase();

  // Pre-seleccionar con la sugerencia del motor
  const defaultDebito = tipo === "EGRESO"
    ? (item.cuenta_debito_sugerida ?? 5493)
    : cuentaBanco;
  const defaultCredito = tipo === "EGRESO"
    ? cuentaBanco
    : (item.cuenta_credito_sugerida ?? 5327);

  const [cuentaDebito, setCuentaDebito] = useState<number>(defaultDebito);
  const [cuentaCredito, setCuentaCredito] = useState<number>(defaultCredito);
  const [obs, setObs] = useState(item.descripcion ?? "");

  const esCxcSocios = cuentaDebito === 5329 || cuentaCredito === 5329;
  const esCxcSociosDebito = cuentaDebito === 5329;

  // Hint de la cuenta seleccionada
  const hintDebito = TODAS_CUENTAS_DEBITO.find(c => c.id === cuentaDebito)?.cuando_usar ?? "";
  const hintCredito = TODAS_CUENTAS_CREDITO.find(c => c.id === cuentaCredito)?.cuando_usar ?? "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl mx-4 p-6 max-h-[92vh] overflow-y-auto">

        {/* Header */}
        <h2 className="text-base font-bold mb-1" style={{ color: "#1c1b1f" }}>Causar movimiento</h2>
        <div className="flex flex-wrap gap-2 mb-1">
          <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100" style={{ color: "#49454f" }}>{item.fecha}</span>
          <span className="text-xs font-bold uppercase px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">{item.banco}</span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: "rgba(0,110,42,0.08)", color: "#006e2a" }}>
            {formatCOP(Math.abs(item.monto))}
          </span>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${tipo === "EGRESO" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
            {tipo}
          </span>
        </div>
        <p className="text-xs font-medium mb-4 truncate" style={{ color: "#49454f" }} title={item.descripcion}>
          {item.descripcion}
        </p>
        {item.razon_baja_confianza && (
          <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200">
            <p className="text-[11px] text-amber-700">⚠️ Baja confianza del motor: {item.razon_baja_confianza}</p>
          </div>
        )}

        {/* Alerta CXC Socios */}
        {esCxcSocios && (
          <div className="mb-4 px-3 py-2.5 rounded-lg bg-red-50 border border-red-200 flex gap-2 items-start">
            <AlertTriangle size={14} className="text-red-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-bold text-red-700 mb-0.5">⛔ CXC Socios — revisar antes de causar</p>
              <p className="text-[11px] text-red-600">
                Esta cuenta es EXCLUSIVA para gastos personales de <strong>Andrés Sanjuan (CC 80075452)</strong> o <strong>Iván Echeverri (CC 80086601)</strong>. 
                Si es un gasto operativo de RODDOS, selecciona la cuenta correcta arriba.
                Causar gastos operativos en CXC Socios distorsiona el P&L.
              </p>
            </div>
          </div>
        )}

        {/* Cuenta Débito */}
        <div className="mb-4">
          <label className="text-xs font-semibold block mb-1.5" style={{ color: "#49454f" }}>
            Cuenta Débito {tipo === "EGRESO" ? <span className="text-[10px] font-normal text-slate-400">(el gasto va aquí)</span> : <span className="text-[10px] font-normal text-slate-400">(banco que recibió)</span>}
          </label>
          <select
            value={cuentaDebito}
            onChange={e => setCuentaDebito(Number(e.target.value))}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
            style={{ borderColor: "rgba(28,27,31,0.2)" }}
          >
            {tipo === "EGRESO" ? (
              <>
                <optgroup label="── Gastos operativos ──">
                  {CUENTAS_GASTOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── CXC / Ingresos ──">
                  {CUENTAS_INGRESOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Retenciones ──">
                  {CUENTAS_RETENCIONES.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Bancos ──">
                  {CUENTAS_BANCOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
              </>
            ) : (
              <>
                <optgroup label="── Bancos (ingreso al banco) ──">
                  {CUENTAS_BANCOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Gastos ──">
                  {CUENTAS_GASTOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
              </>
            )}
          </select>
          {hintDebito && (
            <p className="text-[11px] mt-1 px-1" style={{ color: "#9e9a97" }}>
              💡 {hintDebito}
            </p>
          )}
        </div>

        {/* Cuenta Crédito */}
        <div className="mb-4">
          <label className="text-xs font-semibold block mb-1.5" style={{ color: "#49454f" }}>
            Cuenta Crédito {tipo === "EGRESO" ? <span className="text-[10px] font-normal text-slate-400">(banco que pagó)</span> : <span className="text-[10px] font-normal text-slate-400">(origen del ingreso)</span>}
          </label>
          <select
            value={cuentaCredito}
            onChange={e => setCuentaCredito(Number(e.target.value))}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
            style={{ borderColor: "rgba(28,27,31,0.2)" }}
          >
            {tipo === "EGRESO" ? (
              <>
                <optgroup label="── Bancos (salió de aquí) ──">
                  {CUENTAS_BANCOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Retenciones ──">
                  {CUENTAS_RETENCIONES.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
              </>
            ) : (
              <>
                <optgroup label="── Ingresos / Cartera ──">
                  {CUENTAS_INGRESOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Gastos ──">
                  {CUENTAS_GASTOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
                <optgroup label="── Bancos ──">
                  {CUENTAS_BANCOS.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} ({c.id})</option>
                  ))}
                </optgroup>
              </>
            )}
          </select>
          {hintCredito && (
            <p className="text-[11px] mt-1 px-1" style={{ color: "#9e9a97" }}>
              💡 {hintCredito}
            </p>
          )}
        </div>

        {/* Resumen del asiento */}
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-slate-50 border" style={{ borderColor: "rgba(28,27,31,0.08)" }}>
          <p className="text-[11px] font-semibold mb-1" style={{ color: "#49454f" }}>Asiento que se creará en Alegra:</p>
          <p className="text-xs font-mono" style={{ color: "#0f2a5c" }}>
            DÉBITO: {nombreCuenta(cuentaDebito)} ({cuentaDebito}) = {formatCOP(Math.abs(item.monto))}
          </p>
          <p className="text-xs font-mono" style={{ color: "#006e2a" }}>
            CRÉDITO: {nombreCuenta(cuentaCredito)} ({cuentaCredito}) = {formatCOP(Math.abs(item.monto))}
          </p>
        </div>

        {/* Concepto editable */}
        <div className="mb-5">
          <label className="text-xs font-semibold block mb-1.5" style={{ color: "#49454f" }}>
            Concepto / Descripción en Alegra <span className="text-[10px] font-normal text-slate-400">(editable)</span>
          </label>
          <input
            type="text"
            value={obs}
            onChange={e => setObs(e.target.value)}
            placeholder="Descripción del movimiento"
            className="w-full border rounded-lg px-3 py-2 text-sm"
            style={{ borderColor: "rgba(28,27,31,0.2)" }}
          />
        </div>

        {/* Botones */}
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
            Cancelar
          </Button>
          <Button
            className="flex-1"
            style={{ background: esCxcSocios ? "#dc2626" : "#006e2a", color: "#fff" }}
            onClick={() => onConfirm(cuentaDebito, cuentaCredito, obs)}
            disabled={loading || !obs.trim()}
          >
            {loading ? "Causando..." : esCxcSocios ? "⚠️ Causar como CXC Socios" : "Causar en Alegra"}
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
            { label: "Causados",   value: stats.total_causados,   color: "#166534" },
            { label: "Descartados",value: stats.total_descartados,color: "#64748b" },
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
          <option value="global66">Global66</option>
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
                      {item.es_transferencia_interna && (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded mt-0.5" style={{ background: "rgba(15,42,92,0.08)", color: "#0f2a5c" }}>
                          ⇔ Traslado interno
                        </span>
                      )}
                      {item.razon_baja_confianza && !item.es_transferencia_interna && (
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
                          {!item.es_transferencia_interna && (
                            <button onClick={() => setCausarItem(item)}
                              className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition hover:opacity-80"
                              style={{ background: "rgba(0,110,42,0.08)", color: "#006e2a" }}>
                              Causar
                            </button>
                          )}
                          <button onClick={() => setDescartarItem(item)}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition hover:opacity-80"
                            style={item.es_transferencia_interna
                              ? { background: "rgba(15,42,92,0.08)", color: "#0f2a5c" }
                              : { background: "rgba(220,38,38,0.08)", color: "#dc2626" }}>
                            {item.es_transferencia_interna ? "Descartar traslado" : "Descartar"}
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
