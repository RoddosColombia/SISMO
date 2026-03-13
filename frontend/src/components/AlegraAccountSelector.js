import React, { useState, useMemo } from "react";
import { BookOpen, ChevronDown, Search, ExternalLink } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { ScrollArea } from "./ui/scroll-area";
import { Input } from "./ui/input";
import { useAlegra } from "../contexts/AlegraContext";

const TYPE_ICONS = {
  income: { icon: "↑", color: "text-green-600 bg-green-50", label: "Ingreso" },
  expense: { icon: "↓", color: "text-red-600 bg-red-50", label: "Gasto" },
  cost: { icon: "↓", color: "text-orange-600 bg-orange-50", label: "Costo" },
  asset: { icon: "A", color: "text-blue-600 bg-blue-50", label: "Activo" },
  liability: { icon: "P", color: "text-orange-600 bg-orange-50", label: "Pasivo" },
  equity: { icon: "E", color: "text-purple-600 bg-purple-50", label: "Patrimonio" },
};

const CLASS_LABELS = {
  "1": "1xxx — Activos",
  "2": "2xxx — Pasivos",
  "3": "3xxx — Patrimonio",
  "4": "4xxx — Ingresos",
  "5": "5xxx — Gastos Administración",
  "6": "6xxx — Costos de Ventas",
  "52": "52xx — Gastos de Ventas",
  "53": "53xx — Gastos No Operacionales",
  "54": "54xx — Impuestos",
  // Type-based groups for NIIF accounts without PUC codes
  "asset": "Activos",
  "liability": "Pasivos",
  "equity": "Patrimonio",
  "income": "Ingresos",
  "expense": "Gastos",
  "cost": "Costos de Ventas",
};

export default function AlegraAccountSelector({
  label,
  value,
  onChange,
  filterType = "all",
  required = false,
  placeholder = "Buscar por código o nombre...",
  helpText,
  allowedCodes = null,
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const { searchAccounts, loadingAccounts } = useAlegra();

  const filteredAccounts = useMemo(() => {
    return searchAccounts(search, filterType === "all" ? null : filterType, allowedCodes);
  }, [search, filterType, allowedCodes, searchAccounts]);

  // Group by first digit of code (demo/PUC) or by type (real NIIF without codes)
  const grouped = useMemo(() => {
    const groups = {};
    for (const acc of filteredAccounts) {
      const key = acc.code ? acc.code.charAt(0) : (acc.type || "?");
      if (!groups[key]) groups[key] = [];
      groups[key].push(acc);
    }
    return groups;
  }, [filteredAccounts]);

  const handleSelect = (account) => {
    onChange(account);
    setOpen(false);
    setSearch("");
  };

  const typeInfo = value ? TYPE_ICONS[value.type] || TYPE_ICONS.asset : null;

  return (
    <div className="alegra-selector-container" data-testid="alegra-account-selector">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-semibold text-[#0F2A5C] flex items-center gap-1.5">
          <BookOpen size={13} className="text-[#00A9E0]" />
          {label}
          {required && <span className="text-red-500">*</span>}
        </label>
        <span className="bg-[#00A9E0] text-white text-[10px] font-bold px-2 py-0.5 rounded-full tracking-wide">
          CUENTA ALEGRA
        </span>
      </div>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            className="w-full flex items-center justify-between px-3 py-2.5 bg-white border border-slate-200 rounded-md hover:border-[#00A9E0] transition-colors text-sm text-left"
            data-testid="account-selector-trigger"
          >
            {value ? (
              <div className="flex items-center gap-2 min-w-0">
                {typeInfo && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${typeInfo.color} flex-shrink-0`}>
                    {typeInfo.icon}
                  </span>
                )}
                {value.code && (
                  <span className="font-mono text-xs text-slate-500 flex-shrink-0">[{value.code}]</span>
                )}
                <span className="text-slate-700 truncate">{value.name}</span>
              </div>
            ) : (
              <span className="text-slate-400 text-sm">{placeholder}</span>
            )}
            <ChevronDown size={14} className="text-slate-400 flex-shrink-0 ml-2" />
          </button>
        </PopoverTrigger>

        <PopoverContent className="w-[420px] p-0 shadow-xl border-slate-200" align="start" data-testid="account-selector-dropdown">
          {/* Search */}
          <div className="p-3 border-b border-slate-100">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Buscar por código o nombre..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-9 text-sm"
                autoFocus
                data-testid="account-search-input"
              />
            </div>
          </div>

          <ScrollArea className="h-72">
            {loadingAccounts ? (
              <div className="flex flex-col items-center justify-center p-6 gap-2 text-center">
                <div className="w-5 h-5 border-2 border-[#00A9E0] border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-slate-500">Cargando catálogo de cuentas desde Alegra...</span>
              </div>
            ) : filteredAccounts.length === 0 && !search ? (
              <div className="flex flex-col items-center justify-center p-6 gap-3 text-center">
                <BookOpen size={28} className="text-slate-300" />
                <div>
                  <p className="text-sm font-semibold text-slate-600">Catálogo de cuentas no disponible</p>
                  <p className="text-xs text-slate-400 mt-1">
                    Verifica que tu token de Alegra sea válido en{" "}
                    <span className="font-medium text-[#00A9E0]">Configuración → Integración Alegra</span>
                  </p>
                </div>
                <a
                  href="https://app.alegra.com/configuration/api"
                  target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-[#00A9E0] hover:underline"
                >
                  Obtener nuevo token en Alegra <ExternalLink size={11} />
                </a>
              </div>
            ) : filteredAccounts.length === 0 ? (
              <div className="p-4 text-center text-sm text-slate-400">Sin resultados para "{search}"</div>
            ) : (
              <div className="p-2">
                {Object.entries(grouped).map(([groupKey, accs]) => (
                  <div key={groupKey} className="mb-2">
                    {!search && (
                      <div className="px-2 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        {CLASS_LABELS[groupKey] || `${groupKey}xxx`}
                      </div>
                    )}
                    {accs.map((acc) => {
                      const info = TYPE_ICONS[acc.type] || TYPE_ICONS.asset;
                      const isLeaf = !acc.hasChildren;
                      return (
                        <button
                          key={acc.id}
                          onClick={() => isLeaf ? handleSelect(acc) : null}
                          disabled={!isLeaf}
                          className={`
                            w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left transition-colors
                            ${isLeaf
                              ? "hover:bg-[#F0F4FF] cursor-pointer text-slate-700"
                              : "cursor-default text-slate-400 bg-slate-50/50"
                            }
                            ${value?.id === acc.id ? "bg-[#F0F4FF] font-medium" : ""}
                          `}
                          style={{ paddingLeft: `${(acc.depth || 0) * 12 + 8}px` }}
                          data-testid={`account-option-${acc.id}`}
                        >
                          <span className={`text-[10px] font-bold px-1 py-0.5 rounded ${info.color} flex-shrink-0 w-5 text-center`}>
                            {info.icon}
                          </span>
                          {acc.code && (
                            <span className="font-mono text-xs text-slate-400 flex-shrink-0 w-14">{acc.code}</span>
                          )}
                          <span className="truncate flex-1">{acc.name}</span>
                          {!isLeaf && (
                            <span className="text-[10px] text-slate-400 flex-shrink-0 bg-slate-100 px-1 rounded">grupo</span>
                          )}
                          {value?.id === acc.id && (
                            <span className="text-[#00A9E0] flex-shrink-0">✓</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>

          {value && (
            <div className="p-2 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Seleccionada: <strong>[{value.code}] {value.name}</strong>
              </span>
              <button
                className="text-xs text-[#00A9E0] hover:underline flex items-center gap-1"
                onClick={() => window.open(`https://app.alegra.com/accounts/${value.id}`, "_blank")}
              >
                <ExternalLink size={11} /> Ver en Alegra
              </button>
            </div>
          )}
        </PopoverContent>
      </Popover>

      {helpText && <p className="text-xs text-slate-500 mt-1.5">{helpText}</p>}
    </div>
  );
}
