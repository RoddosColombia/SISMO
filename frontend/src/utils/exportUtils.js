import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const NAVY = [15, 42, 92];    // #0F2A5C
const GOLD = [201, 168, 76];  // #C9A84C
const WHITE = [255, 255, 255];

function formatCOPRaw(value) {
  const n = parseFloat(value) || 0;
  return "$ " + n.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function today() {
  return new Date().toLocaleDateString("es-CO", { day: "2-digit", month: "long", year: "numeric" });
}

// ─── PDF Export ───────────────────────────────────────────────────────────────
/**
 * exportPDF({ title, subtitle, kpis, tables, filename })
 * kpis: [{ label, value, color? }]
 * tables: [{ title, head: [[...]], body: [[...]] }]
 */
export function exportPDF({ title, subtitle = "", kpis = [], tables = [], filename = "reporte" }) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();

  // ── Header banner ──────────────────────────────────────────────────────────
  doc.setFillColor(...NAVY);
  doc.rect(0, 0, pageW, 28, "F");

  // Logo box
  doc.setFillColor(...GOLD);
  doc.roundedRect(12, 6, 16, 16, 3, 3, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(...WHITE);
  doc.text("R", 20, 17, { align: "center" });

  // Title
  doc.setFontSize(15);
  doc.setTextColor(...WHITE);
  doc.text("RODDOS Contable IA", 33, 12);
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(200, 200, 200);
  doc.text("Powered by Alegra", 33, 18);

  // Date right
  doc.setFontSize(8);
  doc.setTextColor(200, 200, 200);
  doc.text(today(), pageW - 12, 14, { align: "right" });

  // ── Report title ───────────────────────────────────────────────────────────
  let y = 38;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(...NAVY);
  doc.text(title, 14, y);

  if (subtitle) {
    y += 6;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    doc.text(subtitle, 14, y);
  }

  // Divider
  y += 4;
  doc.setDrawColor(...GOLD);
  doc.setLineWidth(0.8);
  doc.line(14, y, pageW - 14, y);
  y += 6;

  // ── KPI boxes ─────────────────────────────────────────────────────────────
  if (kpis.length > 0) {
    const boxW = (pageW - 28 - (kpis.length - 1) * 4) / kpis.length;
    kpis.forEach((kpi, i) => {
      const x = 14 + i * (boxW + 4);
      doc.setFillColor(248, 250, 252);
      doc.setDrawColor(226, 232, 240);
      doc.setLineWidth(0.3);
      doc.roundedRect(x, y, boxW, 18, 2, 2, "FD");
      doc.setFont("helvetica", "normal");
      doc.setFontSize(7);
      doc.setTextColor(100, 100, 100);
      doc.text(kpi.label.toUpperCase(), x + boxW / 2, y + 5.5, { align: "center" });
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      const rgb = kpi.color || NAVY;
      doc.setTextColor(...rgb);
      doc.text(kpi.value, x + boxW / 2, y + 13, { align: "center" });
    });
    y += 24;
  }

  // ── Tables ─────────────────────────────────────────────────────────────────
  tables.forEach((table) => {
    if (table.title) {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9);
      doc.setTextColor(...NAVY);
      doc.text(table.title, 14, y);
      y += 4;
    }
    autoTable(doc, {
      startY: y,
      head: table.head,
      body: table.body,
      theme: "grid",
      headStyles: { fillColor: NAVY, textColor: WHITE, fontSize: 8, fontStyle: "bold", cellPadding: 3 },
      bodyStyles: { fontSize: 8, cellPadding: 2.5 },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      margin: { left: 14, right: 14 },
      tableLineColor: [226, 232, 240],
      tableLineWidth: 0.2,
    });
    y = doc.lastAutoTable.finalY + 8;
  });

  // ── Footer ─────────────────────────────────────────────────────────────────
  const pageH = doc.internal.pageSize.getHeight();
  doc.setFillColor(...NAVY);
  doc.rect(0, pageH - 10, pageW, 10, "F");
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  doc.setTextColor(180, 180, 180);
  doc.text("RODDOS Contable IA — Documento generado automáticamente", pageW / 2, pageH - 4, { align: "center" });

  doc.save(`${filename}.pdf`);
}

// ─── Excel Export ─────────────────────────────────────────────────────────────
/**
 * exportExcel({ filename, sheets })
 * sheets: [{ name, columns: [{ key, label, width? }], rows: [{...}] }]
 */
export function exportExcel({ filename = "reporte", sheets }) {
  const wb = XLSX.utils.book_new();

  sheets.forEach((sheet) => {
    // Header row
    const header = sheet.columns.map((c) => c.label);
    const data = sheet.rows.map((row) =>
      sheet.columns.map((c) => row[c.key] ?? "")
    );

    const ws = XLSX.utils.aoa_to_sheet([header, ...data]);

    // Column widths
    ws["!cols"] = sheet.columns.map((c) => ({ wch: c.width || 18 }));

    // Style header row (bold via XLSX community is limited — we set a comment for branding)
    XLSX.utils.book_append_sheet(wb, ws, sheet.name.slice(0, 31));
  });

  XLSX.writeFile(wb, `${filename}.xlsx`);
}
