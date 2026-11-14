"""Expiry status rules."""
from __future__ import annotations

from datetime import date

from app.config import DOC_TYPES

STATUS_LABEL = {
    "EXPIRED": "หมดอายุแล้ว",
    "EXPIRING": "ใกล้หมดอายุ",
    "VALID": "ปกติ",
    "RENEWED": "ต่ออายุแล้ว",
    "PENDING_REVIEW": "รอตรวจทาน",
    "UNKNOWN": "ไม่ทราบวันหมดอายุ",
}
STATUS_ICON = {
    "EXPIRED": "🔴", "EXPIRING": "🟡", "VALID": "🟢",
    "RENEWED": "🔵", "PENDING_REVIEW": "🟣", "UNKNOWN": "⚪",
}


def _as_date(v) -> date | None:
    if not v:
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def days_left(doc: dict, today: date | None = None) -> int | None:
    exp = _as_date(doc.get("expiry_date"))
    if not exp:
        return None
    return (exp - (today or date.today())).days


def compute_status(doc: dict, today: date | None = None) -> str:
    if doc.get("review_status") == "PENDING_REVIEW":
        return "PENDING_REVIEW"
    if doc.get("renewed"):
        return "RENEWED"
    left = days_left(doc, today)
    if left is None:
        return "UNKNOWN"
    if left < 0:
        return "EXPIRED"
    window = DOC_TYPES.get(doc.get("doc_type", ""), ("", "", 30))[2]
    return "EXPIRING" if left <= window else "VALID"


def enrich(docs: list[dict], today: date | None = None) -> list[dict]:
    for d in docs:
        d["days_left"] = days_left(d, today)
        d["status"] = compute_status(d, today)
    return docs
