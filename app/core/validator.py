"""Business-rule validation and confidence scoring for extracted documents."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.config import AUTO_CONFIRM_CONFIDENCE, DOC_TYPES

PLATE_RE = re.compile(r"^\s*(\d{1,2}\s*[ก-ฮ]{0,2}|[ก-ฮ]{1,3})\s*-?\s*\d{1,4}")
KEY_FIELDS = ("doc_type", "expiry_date", "doc_number", "holder_name")


def validate(ex: dict, today: date | None = None) -> list[str]:
    """Return a list of human-readable problems (Thai). Empty list = passes all rules."""
    today = today or date.today()
    problems: list[str] = []
    issue, expiry = ex.get("issue_date"), ex.get("expiry_date")

    if ex.get("doc_type") not in DOC_TYPES:
        problems.append("ไม่ทราบประเภทเอกสาร")
    if not expiry:
        problems.append("ไม่พบวันหมดอายุ")
    else:
        if issue and expiry <= issue:
            problems.append("วันหมดอายุต้องอยู่หลังวันออกเอกสาร")
        if expiry > today + timedelta(days=365 * 12):
            problems.append("วันหมดอายุไกลเกิน 12 ปี — อาจอ่านปี พ.ศ./ค.ศ. ผิด")
        if expiry < today - timedelta(days=365 * 5):
            problems.append("วันหมดอายุผ่านมาเกิน 5 ปี — อาจอ่านปีผิด")
    if issue and issue > today + timedelta(days=1):
        problems.append("วันออกเอกสารอยู่ในอนาคต")
    if not ex.get("doc_number"):
        problems.append("ไม่พบเลขที่เอกสาร")
    if not (ex.get("holder_name") or ex.get("vehicle_plate")):
        problems.append("ไม่พบชื่อผู้ถือ/ทะเบียนรถ")

    owner_type = DOC_TYPES.get(ex.get("doc_type", ""), ("", ""))[1]
    plate = ex.get("vehicle_plate")
    if owner_type == "VEHICLE":
        if not plate:
            problems.append("เอกสารรถแต่ไม่พบทะเบียนรถ")
        elif not PLATE_RE.match(plate):
            problems.append(f"รูปแบบทะเบียนรถไม่ถูกต้อง: {plate}")
    return problems


def score(ex: dict, problems: list[str]) -> float:
    """confidence = min(confidence of key fields) × (1 if rules pass else 0.5)."""
    fc = ex.get("field_confidence") or {}
    vals = [float(fc.get(k, 0.5 if ex.get(k) else 0.0)) for k in KEY_FIELDS]
    base = min(vals) if vals else 0.0
    return round(base * (1.0 if not problems else 0.5), 3)


def needs_review(confidence: float, problems: list[str]) -> bool:
    return bool(problems) or confidence < AUTO_CONFIRM_CONFIDENCE
