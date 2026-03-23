"""Create test extracto file - alternative implementation using CSV and conversion"""
import csv
import json

# Create a JSON representation that can be converted to Excel
data = {
    "sheet_name": "Extracto",
    "headers": ["Fecha", "Descripción", "Valor", "Tipo"],
    "rows": [
        ["2026-03-20", "Cargo 4x1000", 340, "DB"],
        ["2026-03-20", "Pago arriendo oficina", 3614953, "DB"],
        ["2026-03-20", "Transferencia Andres Sanjuan", 85000, "DB"],
        ["2026-03-20", "Pago Claude.ai", 330682, "DB"],
        ["2026-03-20", "Movimiento diverso sin contexto", 1500000, "DB"],
    ]
}

print(json.dumps(data, indent=2))
