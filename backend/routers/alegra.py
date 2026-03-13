"""Alegra proxy router — all Alegra API pass-through endpoints."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user, log_action

router = APIRouter(prefix="/alegra", tags=["alegra"])


@router.post("/test-connection")
async def test_connection(current_user=Depends(get_current_user)):
    return await AlegraService(db).test_connection()


@router.get("/company")
async def get_company(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("company")


@router.get("/accounts")
async def get_accounts(current_user=Depends(get_current_user)):
    """Fetch chart of accounts via /categories (works on Alegra Contabilidad plan)."""
    return await AlegraService(db).get_accounts_from_categories()


@router.get("/contacts")
async def get_contacts(name: Optional[str] = Query(None), current_user=Depends(get_current_user)):
    return await AlegraService(db).request("contacts", params={"name": name} if name else None)


@router.get("/items")
async def get_items(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("items")


@router.get("/taxes")
async def get_taxes(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("taxes")


@router.get("/retentions")
async def get_retentions(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("retentions")


@router.get("/cost-centers")
async def get_cost_centers(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("cost-centers")


@router.get("/bank-accounts")
async def get_bank_accounts(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("bank-accounts")


@router.get("/invoices")
async def get_invoices(
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    params: dict = {"limit": 30}
    if date_start:
        params["date_afterOrNow"] = date_start
    if date_end:
        params["date_beforeOrNow"] = date_end
    if status:
        params["status"] = status
    return await AlegraService(db).request("invoices", params=params)


@router.post("/invoices")
async def create_invoice(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("invoices", "POST", body)
    await log_action(current_user, "/alegra/invoices", "POST", body)
    return result


@router.post("/invoices/{invoice_id}/void")
async def void_invoice(invoice_id: str, current_user=Depends(get_current_user)):
    return await AlegraService(db).request(f"invoices/{invoice_id}/void", "POST")


@router.get("/bills")
async def get_bills(
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    params: dict = {"limit": 30}
    if date_start:
        params["date_afterOrNow"] = date_start
    if date_end:
        params["date_beforeOrNow"] = date_end
    return await AlegraService(db).request("bills", params=params)


@router.post("/bills")
async def create_bill(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("bills", "POST", body)
    await log_action(current_user, "/alegra/bills", "POST", body)
    return result


@router.get("/payments")
async def get_payments(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("payments")


@router.post("/payments")
async def create_payment(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("payments", "POST", body)
    await log_action(current_user, "/alegra/payments", "POST", body)
    return result


@router.get("/journal-entries")
async def get_journal_entries(
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    params: dict = {"limit": 30}
    if date_start:
        params["date_afterOrNow"] = date_start
    if date_end:
        params["date_beforeOrNow"] = date_end
    return await AlegraService(db).request("journal-entries", params=params)


@router.post("/journal-entries")
async def create_journal_entry(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("journal-entries", "POST", body)
    await log_action(current_user, "/alegra/journal-entries", "POST", body)
    return result


@router.get("/bank-accounts/{account_id}/reconciliations")
async def get_reconciliations(account_id: str, current_user=Depends(get_current_user)):
    return await AlegraService(db).request(f"bank-accounts/{account_id}/reconciliations")


@router.post("/bank-accounts/{account_id}/reconciliations")
async def create_reconciliation(account_id: str, body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request(f"bank-accounts/{account_id}/reconciliations", "POST", body)
    await log_action(current_user, f"/alegra/bank-accounts/{account_id}/reconciliations", "POST", body)
    return result
