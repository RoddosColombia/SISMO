/**
 * FiltroFecha — Reusable date range selector for RODDOS.
 * Persists selection per module in localStorage.
 */
import React, { useState, useEffect, useRef } from "react";
import { Calendar, ChevronDown, X } from "lucide-react";

export interface DateRange {
  desde: string; // YYYY-MM-DD
  hasta: string; // YYYY-MM-DD
  label: string;
  preset: string;
}

interface Props {
  moduleKey: string;
  onChange: (range: DateRange) => void;
  compact?: boolean;
}

const now = new Date();
const y = now.getFullYear();
const m = now.getMonth() + 1;

function pad(n: number) { return String(n).padStart(2, "0"); }
function lastDay(year: number, month: number) { return new Date(year, month, 0).getDate(); }
function fmtDate(d: Date) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function addDays(d: Date, days: number) { const r = new Date(d); r.setDate(r.getDate() + days); return r; }
function monday(d: Date) {
  const r = new Date(d);
  const day = r.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  r.setDate(r.getDate() + diff);
  return r;
}

function ivaQuarter(year: number, month: number) {
  if (month <= 4)  return { label: `Cuatrimestre IVA Ene-Abr ${year}`, desde: `${year}-01-01`, hasta: `${year}-04-30` };
  if (month <= 8)  return { label: `Cuatrimestre IVA May-Ago ${year}`, desde: `${year}-05-01`, hasta: `${year}-08-31` };
  return { label: `Cuatrimestre IVA Sep-Dic ${year}`, desde: `${year}-09-01`, hasta: `${year}-12-31` };
}

function prevIvaQuarter(year: number, month: number) {
  if (month <= 4)  return { label: `Cuatrimestre IVA Sep-Dic ${year - 1}`, desde: `${year - 1}-09-01`, hasta: `${year - 1}-12-31` };
  if (month <= 8)  return { label: `Cuatrimestre IVA Ene-Abr ${year}`, desde: `${year}-01-01`, hasta: `${year}-04-30` };
  return { label: `Cuatrimestre IVA May-Ago ${year}`, desde: `${year}-05-01`, hasta: `${year}-08-31` };
}

const MES_NAMES = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

function buildPresets() {
  const today = fmtDate(now);
  const weekStart = fmtDate(monday(now));
  const weekEnd = fmtDate(addDays(monday(now), 6));
  const last7 = fmtDate(addDays(now, -6));
  const last15 = fmtDate(addDays(now, -14));
  const last30 = fmtDate(addDays(now, -29));

  const curMonthStart = `${y}-${pad(m)}-01`;
  const curMonthEnd = `${y}-${pad(m)}-${pad(lastDay(y, m))}`;
  const curMonthLabel = `${MES_NAMES[m]} ${y}`;

  const pm = m === 1 ? 12 : m - 1;
  const py = m === 1 ? y - 1 : y;
  const prevMonthStart = `${py}-${pad(pm)}-01`;
  const prevMonthEnd = `${py}-${pad(pm)}-${pad(lastDay(py, pm))}`;
  const prevMonthLabel = `${MES_NAMES[pm]} ${py}`;

  const first10End = `${y}-${pad(m)}-10`;
  const mid11Start = `${y}-${pad(m)}-11`;
  const mid11End = `${y}-${pad(m)}-20`;
  const last21Start = `${y}-${pad(m)}-21`;

  const curIva = ivaQuarter(y, m);
  const prevIva = prevIvaQuarter(y, m);

  return [
    {
      group: "Rápidos",
      presets: [
        { id: "today", label: "Hoy", desde: today, hasta: today },
        { id: "week", label: "Esta semana", desde: weekStart, hasta: weekEnd },
        { id: "7d", label: "Últimos 7 días", desde: last7, hasta: today },
        { id: "15d", label: "Últimos 15 días", desde: last15, hasta: today },
        { id: "30d", label: "Últimos 30 días", desde: last30, hasta: today },
      ],
    },
    {
      group: "Por Mes",
      presets: [
        { id: "cur_month", label: `Mes actual (${curMonthLabel})`, desde: curMonthStart, hasta: curMonthEnd },
        { id: "prev_month", label: `Mes anterior (${prevMonthLabel})`, desde: prevMonthStart, hasta: prevMonthEnd },
      ],
    },
    {
      group: "Por Año",
      presets: [
        { id: "cur_year", label: `Año actual (${y})`, desde: `${y}-01-01`, hasta: `${y}-12-31` },
        { id: "prev_year", label: `Año anterior (${y - 1})`, desde: `${y - 1}-01-01`, hasta: `${y - 1}-12-31` },
      ],
    },
    {
      group: "Períodos del Mes",
      presets: [
        { id: "first10", label: `Primeros 10 días (${curMonthLabel})`, desde: curMonthStart, hasta: first10End },
        { id: "mid", label: `Del 11 al 20 (${curMonthLabel})`, desde: mid11Start, hasta: mid11End },
        { id: "last21", label: `Del 21 al fin (${curMonthLabel})`, desde: last21Start, hasta: curMonthEnd },
      ],
    },
    {
      group: "Fiscal RODDOS (IVA)",
      presets: [
        { id: "iva_cur", label: curIva.label, desde: curIva.desde, hasta: curIva.hasta },
        { id: "iva_prev", label: prevIva.label, desde: prevIva.desde, hasta: prevIva.hasta },
      ],
    },
  ];
}

const ALL_PRESETS = buildPresets().flatMap(g => g.presets);
const DEFAULT_PRESET_ID = "cur_month";

export function getDefaultRange(): DateRange {
  const p = ALL_PRESETS.find(x => x.id === DEFAULT_PRESET_ID) || ALL_PRESETS[0];
  return { desde: p.desde, hasta: p.hasta, label: p.label, preset: p.id };
}

export function loadRange(moduleKey: string): DateRange {
  try {
    const raw = localStorage.getItem(`filtro_fecha_${moduleKey}`);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return getDefaultRange();
}

function saveRange(moduleKey: string, range: DateRange) {
  try { localStorage.setItem(`filtro_fecha_${moduleKey}`, JSON.stringify(range)); } catch { /* ignore */ }
}

export const FiltroFecha: React.FC<Props> = ({ moduleKey, onChange, compact }) => {
  const [range, setRange] = useState<DateRange>(() => loadRange(moduleKey));
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(false);
  const [customDesde, setCustomDesde] = useState(range.desde);
  const [customHasta, setCustomHasta] = useState(range.hasta);
  const ref = useRef<HTMLDivElement>(null);
  const allGroups = buildPresets();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => { onChange(range); }, [range]); // eslint-disable-line

  const select = (preset: typeof ALL_PRESETS[0]) => {
    const r: DateRange = { desde: preset.desde, hasta: preset.hasta, label: preset.label, preset: preset.id };
    setRange(r);
    saveRange(moduleKey, r);
    setOpen(false);
    setCustom(false);
  };

  const applyCustom = () => {
    if (!customDesde || !customHasta) return;
    const r: DateRange = { desde: customDesde, hasta: customHasta, label: `${customDesde} al ${customHasta}`, preset: "custom" };
    setRange(r);
    saveRange(moduleKey, r);
    setOpen(false);
    setCustom(false);
  };

  return (
    <div ref={ref} className="relative inline-block" data-testid={`filtro-fecha-${moduleKey}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1.5 border border-slate-200 bg-white rounded-lg px-3 hover:border-blue-300 hover:bg-blue-50 transition-colors ${compact ? "py-1.5 text-xs" : "py-2 text-sm"}`}
      >
        <Calendar size={compact ? 12 : 14} className="text-slate-500 flex-shrink-0" />
        <span className="font-medium text-slate-700 max-w-[180px] truncate">{range.label}</span>
        <ChevronDown size={12} className={`text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full mt-1 left-0 z-50 bg-white border border-slate-200 rounded-xl shadow-xl w-72 py-1 max-h-[70vh] overflow-y-auto">
          {allGroups.map(group => (
            <div key={group.group}>
              <p className="px-3 pt-2 pb-1 text-[10px] font-bold text-slate-400 uppercase tracking-wide">{group.group}</p>
              {group.presets.map(preset => (
                <button
                  key={preset.id}
                  onClick={() => select(preset)}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 hover:text-blue-700 transition-colors ${
                    range.preset === preset.id ? "bg-blue-50 text-blue-700 font-semibold" : "text-slate-700"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          ))}

          <div>
            <p className="px-3 pt-2 pb-1 text-[10px] font-bold text-slate-400 uppercase tracking-wide">Personalizado</p>
            {!custom ? (
              <button
                onClick={() => setCustom(true)}
                className="w-full text-left px-3 py-1.5 text-xs text-slate-600 hover:bg-blue-50 hover:text-blue-700"
              >
                Seleccionar rango personalizado...
              </button>
            ) : (
              <div className="px-3 pb-3 space-y-2">
                <div className="flex gap-2 items-center">
                  <label className="text-[10px] text-slate-500 w-10">Desde</label>
                  <input type="date" value={customDesde} onChange={e => setCustomDesde(e.target.value)}
                    className="flex-1 border border-slate-200 rounded-md text-xs px-2 py-1" />
                </div>
                <div className="flex gap-2 items-center">
                  <label className="text-[10px] text-slate-500 w-10">Hasta</label>
                  <input type="date" value={customHasta} onChange={e => setCustomHasta(e.target.value)}
                    className="flex-1 border border-slate-200 rounded-md text-xs px-2 py-1" />
                </div>
                <div className="flex gap-2">
                  <button onClick={applyCustom} className="flex-1 bg-blue-600 text-white text-xs py-1.5 rounded-md hover:bg-blue-700">
                    Aplicar
                  </button>
                  <button onClick={() => setCustom(false)} className="px-2 text-slate-400 hover:text-slate-600">
                    <X size={14} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default FiltroFecha;
