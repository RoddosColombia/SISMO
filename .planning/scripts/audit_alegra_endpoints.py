"""
audit_alegra_endpoints.py — Auditoria HTTP de endpoints criticos de Alegra
Uso: python audit_alegra_endpoints.py
Requisito: ALEGRA_EMAIL y ALEGRA_TOKEN en variables de entorno
Si no estan presentes, documenta CREDENCIALES AUSENTES y hace analisis estatico.
NO modifica datos en produccion (solo GETs).
"""

import os
import sys
import base64
import json

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"
ALEGRA_EMAIL = os.environ.get("ALEGRA_EMAIL", "").strip()
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "").strip()

TIMEOUT = 15.0

ENDPOINTS = [
    {
        "name": "GET /categories",
        "path": "categories",
        "method": "GET",
        "params": None,
        "description": "Plan de cuentas — endpoint correcto (NO /accounts que da 403)",
        "extract": lambda r: _extract_list(r, ["id", "name", "code"]),
    },
    {
        "name": "GET /invoices",
        "path": "invoices",
        "method": "GET",
        "params": {"limit": 3},
        "description": "Facturas de venta recientes",
        "extract": lambda r: _extract_list(r, ["id", "date", "total", "status"]),
    },
    {
        "name": "GET /payments",
        "path": "payments",
        "method": "GET",
        "params": {"limit": 3},
        "description": "Pagos recientes",
        "extract": lambda r: _extract_list(r, ["id", "date", "amount"]),
    },
    {
        "name": "GET /journals",
        "path": "journals",
        "method": "GET",
        "params": {"limit": 3},
        "description": "Asientos contables recientes (endpoint correcto, NO /journal-entries)",
        "extract": lambda r: _extract_list(r, ["id", "date", "observations"]),
    },
    {
        "name": "GET /contacts",
        "path": "contacts",
        "method": "GET",
        "params": {"limit": 3},
        "description": "Contactos",
        "extract": lambda r: _extract_list(r, ["id", "name"]),
    },
    {
        "name": "GET /company",
        "path": "company",
        "method": "GET",
        "params": None,
        "description": "Datos empresa — sanity check",
        "extract": lambda r: _extract_company(r),
    },
    {
        "name": "GET /accounts",
        "path": "accounts",
        "method": "GET",
        "params": None,
        "description": "ESTE DEBE FALLAR con 403 — confirmar restriccion real",
        "extract": lambda r: _extract_list(r, ["id", "name"]),
    },
]


def _extract_list(data, fields):
    """Extrae campos de una lista de objetos o de objeto unico."""
    if isinstance(data, list):
        items = data[:3]
    elif isinstance(data, dict):
        items = [data]
    else:
        return str(data)[:200]

    result = []
    for item in items:
        if isinstance(item, dict):
            extracted = {f: item.get(f, "N/A") for f in fields}
            result.append(extracted)
        else:
            result.append(str(item)[:100])
    return result


def _extract_company(data):
    if isinstance(data, dict):
        return {"name": data.get("name", "N/A"), "id": data.get("id", "N/A")}
    return str(data)[:200]


def _get_auth_header():
    token = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def run_http_audit():
    """Ejecuta requests HTTP reales contra Alegra API."""
    results = []
    headers = _get_auth_header()

    with httpx.Client(timeout=TIMEOUT) as client:
        for ep in ENDPOINTS:
            url = f"{ALEGRA_BASE_URL}/{ep['path']}"
            try:
                resp = client.request(
                    method=ep["method"],
                    url=url,
                    params=ep.get("params"),
                    headers=headers,
                )
                status = resp.status_code
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text[:500]

                if status == 200:
                    veredicto = "FUNCIONA"
                    extracto = ep["extract"](body)
                    count = len(body) if isinstance(body, list) else 1
                elif status == 403:
                    veredicto = "BLOQUEADO"
                    extracto = body if isinstance(body, (str, dict)) else str(body)[:200]
                    count = 0
                elif status == 401:
                    veredicto = "FALLA"
                    extracto = "401 — Credenciales invalidas o no autorizadas"
                    count = 0
                elif status == 404:
                    veredicto = "FALLA"
                    extracto = body if isinstance(body, (str, dict)) else str(body)[:200]
                    count = 0
                else:
                    veredicto = "FALLA"
                    extracto = body if isinstance(body, (str, dict)) else str(body)[:200]
                    count = 0

                results.append({
                    "name": ep["name"],
                    "url": url,
                    "status": status,
                    "count": count,
                    "extracto": extracto,
                    "veredicto": veredicto,
                    "descripcion": ep["description"],
                })

            except httpx.TimeoutException:
                results.append({
                    "name": ep["name"],
                    "url": url,
                    "status": "timeout",
                    "count": 0,
                    "extracto": "Request excedio 15 segundos",
                    "veredicto": "FALLA",
                    "descripcion": ep["description"],
                })
            except Exception as e:
                results.append({
                    "name": ep["name"],
                    "url": url,
                    "status": "error",
                    "count": 0,
                    "extracto": str(e)[:200],
                    "veredicto": "FALLA",
                    "descripcion": ep["description"],
                })

    return results


def run_static_audit():
    """Cuando no hay credenciales, produce resultados de analisis estatico."""
    results = []
    for ep in ENDPOINTS:
        url = f"{ALEGRA_BASE_URL}/{ep['path']}"
        if ep["path"] == "accounts":
            veredicto = "BLOQUEADO"
            extracto = "Confirmado en ALEGRA-CODE-AUDIT.md seccion 3 — NUNCA usar /accounts, usar /categories"
            status = "403-ESTATICO"
        else:
            veredicto = "PENDIENTE"
            extracto = "CREDENCIALES AUSENTES — no fue posible probar con HTTP real. Ver analisis estatico en ALEGRA-CODE-AUDIT.md"
            status = "CREDENCIALES_AUSENTES"

        results.append({
            "name": ep["name"],
            "url": url,
            "status": status,
            "count": 0,
            "extracto": extracto,
            "veredicto": veredicto,
            "descripcion": ep["description"],
        })

    return results


def format_results_markdown(results, mode):
    """Formatea resultados como Markdown."""
    lines = [
        "# ALEGRA-ENDPOINT-RESULTS.md — Resultados de Auditoria HTTP",
        "",
        f"**Fecha:** 2026-03-30",
        f"**Modo:** {'HTTP Real' if mode == 'http' else 'Analisis Estatico (CREDENCIALES AUSENTES)'}",
        f"**URL Base:** {ALEGRA_BASE_URL}",
        "",
    ]

    if mode == "static":
        lines += [
            "## NOTA: Credenciales No Disponibles en Entorno de Ejecucion",
            "",
            "Las variables `ALEGRA_EMAIL` y `ALEGRA_TOKEN` no estan configuradas en este entorno.",
            "Los resultados a continuacion usan el analisis estatico de `ALEGRA-CODE-AUDIT.md` como evidencia.",
            "Para obtener evidencia HTTP real, ejecutar con credenciales en Render o entorno local con .env.",
            "",
        ]

    lines.append("## Resumen")
    lines.append("")
    lines.append("| Endpoint | HTTP Status | Veredicto | Items |")
    lines.append("|----------|-------------|-----------|-------|")
    for r in results:
        lines.append(f"| {r['name']} | {r['status']} | {r['veredicto']} | {r['count']} |")
    lines.append("")

    for r in results:
        lines += [
            f"---",
            "",
            f"### {r['name']}",
            f"- **URL:** {r['url']}",
            f"- **Descripcion:** {r['descripcion']}",
            f"- **HTTP Status:** {r['status']}",
            f"- **Items retornados:** {r['count']}",
            f"- **Extracto:**",
            "```",
            json.dumps(r['extracto'], ensure_ascii=False, indent=2) if isinstance(r['extracto'], (dict, list)) else str(r['extracto']),
            "```",
            f"- **Veredicto:** {r['veredicto']}",
            "",
        ]

    return "\n".join(lines)


def main():
    has_credentials = bool(ALEGRA_EMAIL and ALEGRA_TOKEN)

    if has_credentials and HTTPX_AVAILABLE:
        print("[INFO] Credenciales encontradas — ejecutando auditoria HTTP real")
        results = run_http_audit()
        mode = "http"
    else:
        if not has_credentials:
            print("[WARN] ALEGRA_EMAIL o ALEGRA_TOKEN no configurados — usando analisis estatico")
        if not HTTPX_AVAILABLE:
            print("[WARN] httpx no disponible — usando analisis estatico")
        results = run_static_audit()
        mode = "static"

    output = format_results_markdown(results, mode)
    print(output)
    return results, mode


if __name__ == "__main__":
    results, mode = main()
