"""Business-rule validation and confidence scoring for extracted documents."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.config import AUTO_CONFIRM_CONFIDENCE, DOC_TYPES

PLATE_RE = re.compile(r"^\s*(\d{1,2}\s*[ก-ฮ]{0,2}|[ก-ฮ]{1,3})\s*-?\s*\d{1,4}")
KEY_FIELDS = ("doc_type", "expiry_date", "doc_number", "vehicle_plate")


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
    if ex.get("doc_type") == "DRIVER_LICENSE":
        if not ex.get("holder_name"):
            problems.append("ไม่พบชื่อคนขับ")
        return problems
    plate = ex.get("vehicle_plate")
    if not plate:
        problems.append("ไม่พบทะเบียนรถ")
    elif not PLATE_RE.match(plate):
        problems.append(f"รูปแบบทะเบียนรถไม่ถูกต้อง: {plate}")
    return problems


def cross_check(ex: dict) -> list[str]:
    """Compare what was read against the master data (registered drivers and vehicles).

    A licence whose name does not match a registered driver (e.g. a missing tone mark: "พึงบุญ" vs "พึ่งบุญ")
    or a plate that is not in the fleet must be checked by a person — even when the model is confident.
    """
    import difflib

    from app.db import database as db

    owners = db.list_owners()
    if ex.get("doc_type") == "DRIVER_LICENSE":
        name = (ex.get("holder_name") or "").strip()
        names = [o["name"] for o in owners if o["owner_type"] == "DRIVER"]
        squash = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
        # accept "Mr. Boonlert Jaingam / นายบุญเลิศ ใจงาม" when it contains a registered Thai name
        if name and names and not any(squash(n) in squash(name) for n in names):
            close = difflib.get_close_matches(name, names, n=1, cutoff=0.8)
            hint = f" — หมายถึง \"{close[0]}\" ใช่ไหม?" if close else " (คนขับใหม่?)"
            return [f"ไม่พบคนขับชื่อ \"{name}\" ในระบบ{hint}"]
        return []
    plate = re.sub(r"\s+", "", ex.get("vehicle_plate") or "")
    idents = [o["identifier"] for o in owners if o["owner_type"] == "VEHICLE"]
    if plate and idents and not any(plate.startswith(i.replace(" ", "")) for i in idents):
        return [f"ทะเบียน \"{ex.get('vehicle_plate')}\" ยังไม่มีในระบบ (รถใหม่ หรืออ่านทะเบียนผิด?)"]
    return []


def key_fields(doc_type: str | None) -> tuple[str, ...]:
    """A driver's licence is identified by the driver's name; vehicle documents by the plate."""
    if doc_type == "DRIVER_LICENSE":
        return ("doc_type", "expiry_date", "doc_number", "holder_name")
    return KEY_FIELDS


def score(ex: dict, problems: list[str]) -> float:
    """confidence = min(confidence of key fields) × (1 if rules pass else 0.5)."""
    fc = ex.get("field_confidence") or {}
    vals = [float(fc.get(k, 0.5 if ex.get(k) else 0.0)) for k in key_fields(ex.get("doc_type"))]
    base = min(vals) if vals else 0.0
    return round(base * (1.0 if not problems else 0.5), 3)


def needs_review(confidence: float, problems: list[str]) -> bool:
    return bool(problems) or confidence < AUTO_CONFIRM_CONFIDENCE
