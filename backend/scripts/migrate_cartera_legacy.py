"""
migrate_cartera_legacy.py — BUILD 0.2

Migra créditos desde Excel de scoring a la colección loanbook_legacy en MongoDB.
Dedup por codigo_sismo (LG-{cedula}-{num_credito}).
Upsert: no destruye pagos_recibidos ni alegra_contact_id ya existentes.

Uso:
    python backend/scripts/migrate_cartera_legacy.py \
        --excel "C:/ruta/al/archivo.xlsx" \
        --mongo-url "mongodb+srv://..." \
        --db-name "sismo-prod" \
        [--sheet "Créditos Activos"] \
        [--dry-run]

Si MONGO_URL y DB_NAME están en el entorno, no hace falta pasarlos como args.
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import pandas as pd

# ── constants ─────────────────────────────────────────────────────────────────
SHEET_NAME  = "Créditos Activos"
SKIPROWS    = 2          # título + subtítulo antes del header real
ESTADO_FIJO = "activo"   # todos vienen del sheet Créditos Activos


# ── helpers ───────────────────────────────────────────────────────────────────

def _str(val, default=None):
    try:
        if val is None or (hasattr(val, '__class__') and val.__class__.__name__ == 'float' and val != val):
            return default
        import math
        if isinstance(val, float) and math.isnan(val):
            return default
    except Exception:
        pass
    s = str(val).strip()
    return s if s else default


def _float(val, default=None):
    try:
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _int(val, default=None):
    try:
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def parse_row(row) -> dict | None:
    """
    Convierte una fila del Excel en un documento loanbook_legacy.
    Retorna None si la fila no tiene Id crédito válido.
    """
    import pandas as pd

    id_credito = _str(row.get("Id crédito"))
    if not id_credito:
        return None

    # Separar cedula y numero_credito: "1015994188-45541"
    partes = id_credito.split("-")
    if len(partes) < 2:
        print(f"  [SKIP] Id crédito sin guión: {id_credito!r}")
        return None
    cedula              = partes[0].strip()
    numero_credito_orig = partes[1].strip()
    codigo_sismo        = f"LG-{cedula}-{numero_credito_orig}"

    nombre    = _str(row.get("Nombre"), "")
    apellidos = _str(row.get("Apellidos"), "")
    nombre_completo = f"{nombre} {apellidos}".strip() or "SIN NOMBRE"

    aliado       = _str(row.get("Aliado"), "Sin aliado")
    estado_excel = _str(row.get("Estado"), "En Mora")
    # Normalize encoding edge-cases ("Al DÃ­a" in some terminals → "Al Día")
    if estado_excel and "Al D" in estado_excel and estado_excel != "Al Día":
        estado_excel = "Al Día"

    saldo_actual  = _float(row.get("Saldo\nx Cobrar"), 0.0)
    saldo_inicial = saldo_actual   # no disponible en Excel → mismo valor

    placa              = _str(row.get("Placa"))
    score_total        = _float(row.get("Score Total"))
    pct_on_time        = _float(row.get("% On Time"))   # decimal 0-1
    dias_mora_maxima   = _int(row.get("Días Máx"))
    decision_historica = _str(row.get("DECISIÓN"))
    analisis_texto     = _str(row.get("Análisis"))

    return {
        "codigo_sismo":            codigo_sismo,
        "cedula":                  cedula,
        "numero_credito_original": numero_credito_orig,
        "nombre_completo":         nombre_completo,
        "placa":                   placa,
        "aliado":                  aliado,
        "estado":                  ESTADO_FIJO,
        "estado_legacy_excel":     estado_excel,
        "saldo_actual":            saldo_actual,
        "saldo_inicial":           saldo_inicial,
        "score_total":             score_total,
        "pct_on_time":             pct_on_time,
        "dias_mora_maxima":        dias_mora_maxima,
        "decision_historica":      decision_historica,
        "analisis_texto":          analisis_texto,
        "fecha_importacion":       datetime.now(timezone.utc),
        "updated_at":              datetime.now(timezone.utc),
    }


def run(excel_path: str, sheet: str, dry_run: bool, mongo_url: str, db_name: str):
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}BUILD 0.2 — migrate_cartera_legacy")
    print(f"Excel : {excel_path}")
    print(f"Sheet : {sheet}")
    if not dry_run:
        print(f"DB    : {db_name}")
    print()

    # ── 1. Leer Excel ────────────────────────────────────────────────────────
    df = pd.read_excel(excel_path, sheet_name=sheet, skiprows=SKIPROWS)
    print(f"Filas brutas : {len(df)}")

    # Dedup exacto por Id crédito (keep first)
    df = df.drop_duplicates(subset=["Id crédito"], keep="first")
    print(f"Tras dedup   : {len(df)}")

    # ── 2. Parsear filas ─────────────────────────────────────────────────────
    docs = []
    skipped = 0
    for _, row in df.iterrows():
        doc = parse_row(row.to_dict())
        if doc is None:
            skipped += 1
        else:
            docs.append(doc)

    print(f"Docs válidos : {len(docs)}  |  Skips: {skipped}")
    print()

    if dry_run:
        def _safe(s, width=30):
            return s[:width].encode("ascii", "replace").decode("ascii")

        for d in docs[:5]:
            print(
                f"  {d['codigo_sismo']} | {_safe(d['nombre_completo']):<30} "
                f"| {_safe(d['aliado'], 16):<16} | {d['estado_legacy_excel'][:8]:<8} "
                f"| ${d['saldo_actual']:>10,.0f}"
            )
        if len(docs) > 5:
            print(f"  ... y {len(docs)-5} mas")
        print("\n[DRY-RUN] Nada escrito en MongoDB.")
        return

    # ── 3. Upsert a MongoDB ──────────────────────────────────────────────────
    if not mongo_url or not db_name:
        print("ERROR: Se requiere --mongo-url y --db-name (o MONGO_URL / DB_NAME en el entorno).")
        sys.exit(1)

    from pymongo import MongoClient, UpdateOne

    client = MongoClient(mongo_url)
    col = client[db_name]["loanbook_legacy"]

    # Índice único en codigo_sismo
    col.create_index("codigo_sismo", unique=True, background=True)

    ops = []
    for doc in docs:
        codigo = doc["codigo_sismo"]
        set_fields = {k: v for k, v in doc.items()}
        ops.append(UpdateOne(
            {"codigo_sismo": codigo},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "pagos_recibidos": [],
                    "alegra_contact_id": None,
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        ))

    result = col.bulk_write(ops, ordered=False)
    client.close()

    print("✅ Resultado MongoDB:")
    print(f"   Insertados  : {result.upserted_count}")
    print(f"   Actualizados: {result.modified_count}")
    print(f"   Total ops   : {len(ops)}")

    # Verificación
    client2 = MongoClient(mongo_url)
    total_col = client2[db_name]["loanbook_legacy"].count_documents({})
    client2.close()
    print(f"   Total en colección: {total_col}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra créditos legacy a MongoDB")
    parser.add_argument("--excel",     required=True, help="Ruta al archivo .xlsx")
    parser.add_argument("--sheet",     default=SHEET_NAME, help="Nombre del sheet")
    parser.add_argument("--mongo-url", default=os.environ.get("MONGO_URL", ""),
                        help="MongoDB connection string")
    parser.add_argument("--db-name",   default=os.environ.get("DB_NAME", ""),
                        help="Nombre de la base de datos")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Solo parsear, no escribir en MongoDB")
    args = parser.parse_args()

    run(
        excel_path=args.excel,
        sheet=args.sheet,
        dry_run=args.dry_run,
        mongo_url=args.mongo_url,
        db_name=args.db_name,
    )
