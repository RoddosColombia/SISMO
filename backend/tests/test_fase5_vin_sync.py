"""test_fase5_vin_sync.py — FASE 5: VIN sync fix en alegra_webhooks.py.

5 tests de análisis estático. No requieren FastAPI ni MongoDB en ejecución.

Verifica:
- T1: find_one no usa solo {"chasis": chasis} — debe usar $or
- T2: update_one en bloque "if moto" usa $or (no solo chasis)
- T3: existe bloque anti-duplicado con existing_vin antes de insert_one
- T4: update_one del anti-duplicado usa $or también
- T5: insert_one de nueva moto sigue existiendo (caso genuinamente nueva)
"""

from pathlib import Path

WEBHOOKS_SOURCE = (
    Path(__file__).parent.parent / "routers" / "alegra_webhooks.py"
).read_text(encoding="utf-8")


def test_t1_find_one_usa_or_no_solo_chasis():
    """find_one para inventario_motos usa $or [chasis, vin], no solo {"chasis": chasis}."""
    # No debe haber find_one con solo chasis (sin $or)
    assert 'find_one({"chasis": chasis}' not in WEBHOOKS_SOURCE, (
        'alegra_webhooks.py aún usa find_one({"chasis": chasis}) — debe usar $or'
    )
    # Debe haber $or con ambos campos
    assert '"$or": [{"chasis": chasis}, {"vin": chasis}]' in WEBHOOKS_SOURCE or \
           '"$or"' in WEBHOOKS_SOURCE and '"vin": chasis' in WEBHOOKS_SOURCE, (
        "alegra_webhooks.py no usa $or con vin y chasis en find_one"
    )


def test_t2_update_one_principal_usa_or():
    """update_one que marca Vendida usa $or, no solo {"chasis": chasis}."""
    assert 'update_one(\n                    {"chasis": chasis}' not in WEBHOOKS_SOURCE and \
           'update_one({"chasis": chasis}' not in WEBHOOKS_SOURCE, (
        'alegra_webhooks.py aún usa update_one({"chasis": chasis}) — debe usar $or'
    )
    # Verificar que update_one referencia el $or
    update_pos = WEBHOOKS_SOURCE.find('update_one(')
    assert update_pos > 0, "No se encontró update_one en alegra_webhooks.py"
    update_section = WEBHOOKS_SOURCE[update_pos:update_pos + 300]
    assert '"$or"' in update_section or '$or' in update_section, (
        "El primer update_one en inventario_motos no usa $or"
    )


def test_t3_anti_duplicado_existing_vin_antes_de_insert():
    """Existe bloque anti-duplicado con existing_vin antes de inventario_motos.insert_one."""
    assert "existing_vin" in WEBHOOKS_SOURCE, (
        "alegra_webhooks.py no tiene variable existing_vin — falta anti-duplicado"
    )
    existing_pos = WEBHOOKS_SOURCE.find("existing_vin")
    # Buscar insert_one específico de inventario_motos (no de roddos_events u otros)
    inv_insert_pos = WEBHOOKS_SOURCE.find("inventario_motos.insert_one(")
    assert inv_insert_pos > 0, (
        "No se encontró inventario_motos.insert_one en alegra_webhooks.py"
    )
    assert existing_pos < inv_insert_pos, (
        "El bloque existing_vin debe aparecer ANTES del inventario_motos.insert_one"
    )


def test_t4_anti_duplicado_update_usa_or():
    """El update_one del bloque anti-duplicado usa $or."""
    existing_pos = WEBHOOKS_SOURCE.find("existing_vin")
    assert existing_pos > 0, "No se encontró existing_vin"
    antiduplicate_section = WEBHOOKS_SOURCE[existing_pos:existing_pos + 600]
    assert '"$or"' in antiduplicate_section or "$or" in antiduplicate_section, (
        "El update_one del anti-duplicado no usa $or"
    )
    assert '"vin": chasis' in antiduplicate_section or "vin" in antiduplicate_section, (
        "El anti-duplicado no cubre el campo vin"
    )


def test_t5_insert_one_nueva_moto_sigue_existiendo():
    """insert_one para nueva moto sigue existiendo (caso genuino)."""
    assert "insert_one({" in WEBHOOKS_SOURCE, (
        "alegra_webhooks.py eliminó insert_one — debe mantenerse para motos genuinamente nuevas"
    )
    assert '"chasis": chasis' in WEBHOOKS_SOURCE, (
        "insert_one no setea campo chasis"
    )
    assert '"estado": "Vendida"' in WEBHOOKS_SOURCE, (
        "insert_one no setea estado Vendida"
    )
