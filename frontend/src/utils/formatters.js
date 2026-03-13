/**
 * Formatters for Colombian accounting (COP currency, dates)
 */

/** Format number as Colombian Pesos */
export function formatCOP(amount) {
  if (amount === null || amount === undefined) return "$0";
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Format as number with thousand separators (no currency symbol) */
export function formatNumber(amount) {
  if (!amount && amount !== 0) return "0";
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Format date as DD/MM/YYYY */
export function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/**
 * Get invoice/bill number — works with both mock (inv.number) and
 * real Alegra data (inv.numberTemplate.fullNumber)
 */
export function getDocNumber(doc) {
  return doc?.numberTemplate?.fullNumber || doc?.number || doc?.id || "—";
}

/**
 * Get provider/vendor name — real Alegra bills use `provider`, mock uses `vendor`
 */
export function getVendorName(bill) {
  return bill?.provider?.name || bill?.vendor?.name || "—";
}

/** Format date as "15 oct. 2025" */
export function formatShortDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

/** Get today's date as YYYY-MM-DD */
export function todayStr() {
  return new Date().toISOString().split("T")[0];
}

/** Add N days to date string */
export function addDays(dateStr, days) {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

/** Get invoice status label and classes */
export function getStatusInfo(status) {
  const map = {
    open: { label: "Pendiente", className: "status-open" },
    paid: { label: "Pagada", className: "status-paid" },
    overdue: { label: "Vencida", className: "status-overdue" },
    draft: { label: "Borrador", className: "status-draft" },
    voided: { label: "Anulada", className: "status-voided" },
  };
  return map[status] || { label: status, className: "status-draft" };
}

/** Calculate IVA amount */
export function calcIVA(amount, percentage) {
  return Math.round(amount * (percentage / 100));
}

/** Calculate retención */
export function calcRetencion(amount, percentage) {
  return Math.round(amount * (percentage / 100));
}

/** Get current month range as {from: YYYY-MM-DD, to: YYYY-MM-DD} */
export function getMonthRange(offsetMonths = 0) {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() + offsetMonths, 1);
  const from = d.toISOString().split("T")[0];
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const to = last.toISOString().split("T")[0];
  return { from, to };
}

/** Format month/year label in Spanish (e.g. "Marzo 2026") */
export function formatMonthYear(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("es-CO", { month: "long", year: "numeric" });
}

/** Parse COP input string to number */
export function parseCOP(str) {
  if (!str) return 0;
  return parseInt(String(str).replace(/[^\d]/g, ""), 10) || 0;
}

/** Get month name in Spanish */
export function getMonthName(month) {
  const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return months[month] || "";
}
