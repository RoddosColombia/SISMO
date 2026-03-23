#!/usr/bin/env python3
"""Create test extracto file for bank reconciliation smoke test."""

from openpyxl import Workbook
import os

def create_test_extracto():
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Extracto"

    # Add 8 header rows (Bancolombia format requires skip_rows=8)
    for i in range(1, 9):
        sheet[f'A{i}'] = "BANCOLOMBIA"

    # Row 9 = column headers
    sheet['A9'] = "Fecha"
    sheet['B9'] = "Descripción"
    sheet['C9'] = "Valor"
    sheet['D9'] = "Tipo"

    # 5 synthetic movements for smoke test
    data = [
        ["2026-03-20", "Cargo 4x1000", 340, "DB"],
        ["2026-03-20", "Pago arriendo oficina", 3614953, "DB"],
        ["2026-03-20", "Transferencia Andres Sanjuan", 85000, "DB"],
        ["2026-03-20", "Pago Claude.ai", 330682, "DB"],
        ["2026-03-20", "Movimiento diverso sin contexto", 1500000, "DB"],
    ]

    for idx, row_data in enumerate(data, start=10):
        sheet[f'A{idx}'] = row_data[0]
        sheet[f'B{idx}'] = row_data[1]
        sheet[f'C{idx}'] = row_data[2]
        sheet[f'D{idx}'] = row_data[3]

    output_path = os.path.join(os.path.dirname(__file__), "test_extracto_bancolombia.xlsx")
    wb.save(output_path)
    print(f"✓ Created test extracto: {output_path}")
    return output_path

if __name__ == "__main__":
    create_test_extracto()
