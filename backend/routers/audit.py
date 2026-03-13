"""Audit log router — paginated access log for admins."""
from typing import Optional

from fastapi import APIRouter, Depends

from database import db
from dependencies import require_admin

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
async def get_audit_logs(
    user_email: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    only_errors: bool = False,
    page: int = 1,
    limit: int = 50,
    current_user=Depends(require_admin),
):
    query = {}
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if date_start:
        query.setdefault("timestamp", {})["$gte"] = date_start
    if date_end:
        query.setdefault("timestamp", {})["$lte"] = date_end + "T23:59:59"
    if only_errors:
        query["response_status"] = {"$gte": 400}

    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "page": page, "limit": limit, "logs": logs}
