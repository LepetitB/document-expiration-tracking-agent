"""Tools the agent can call. Each returns JSON-serialisable data read from the database."""
from __future__ import annotations

from collections import Counter

from app.config import DOC_TYPES, OWNER_TYPES, doc_label
from app.core.status import STATUS_LABEL, enrich
from app.db import database as db
from app.extraction.thai_date import to_thai
from datetime import date


def _brief(d: dict) -> dict:
    return {
        "id": d["id"],
        "doc_type": doc_label(d["doc_type"]),
        "owner": d.get("owner_name"),
        "owner_type": OWNER_TYPES.get(d.get("owner_type"), ""),
        "owner_identifier": d.get("owner_identifier"),
        "doc_number": d.get("doc_number"),
        "expiry_date": to_thai(date.fromisoformat(d["expiry_date"])) if d.get("expiry_date") else None,
        "renew_by": to_thai(date.fromisoformat(d["renew_by"])) if d.get("renew_by") else None,
        "days_left": d.get("days_left"),
        "status": STATUS_LABEL[d["status"]],
    }


def _active() -> list[dict]:
    return enrich(db.list_documents())


def search_documents(query: str = "", doc_type: str | None = None, status: str | None = None) -> list[dict]:
    q = query.strip().lower()
    out = []
    for d in _active():
        hay = " ".join(str(d.get(k) or "") for k in
                       ("owner_name", "owner_identifier", "holder_name", "doc_number")).lower()
        if q and q not in hay:
            continue
        if doc_type and d["doc_type"] != doc_type:
            continue
        if status and d["status"] != status:
            continue
        out.append(_brief(d))
    return out[:50]


def list_expiring(within_days: int = 30, include_expired: bool = True) -> list[dict]:
    out = []
    for d in _active():
        left = d["days_left"]
        if left is None or d["status"] == "PENDING_REVIEW":
            continue
        if left <= within_days and (include_expired or left >= 0):
            out.append(_brief(d))
    return sorted(out, key=lambda x: x["days_left"])


def get_owner_summary(identifier: str) -> dict:
    ident = identifier.strip().lower()
    docs = [d for d in _active()
            if ident in (d.get("owner_identifier") or "").lower() or ident in (d.get("owner_name") or "").lower()]
    if not docs:
        return {"found": False, "message": f"ไม่พบรถหรือคนขับ '{identifier}'"}
    owner_id = docs[0]["owner_id"]
    docs = [d for d in docs if d["owner_id"] == owner_id]
    result = {"found": True, "owner": docs[0]["owner_name"],
              "owner_type": OWNER_TYPES.get(docs[0]["owner_type"], ""),
              "documents": [_brief(d) for d in docs]}
    owner = db.get_owner(owner_id) or {}
    if owner.get("owner_type") == "VEHICLE":
        driver = db.get_owner(owner["driver_id"]) if owner.get("driver_id") else None
        result["driver"] = driver["name"] if driver else "ไม่มีคนขับประจำ"
        if driver:
            result["driver_license"] = [_brief(d) for d in _active() if d["owner_id"] == driver["id"]]
    elif owner.get("owner_type") == "DRIVER":
        result["vehicles"] = [v["name"] for v in db.vehicles_of_driver(owner_id)]
    return result


def get_stats() -> dict:
    docs = _active()
    by_status = Counter(STATUS_LABEL[d["status"]] for d in docs)
    by_type = Counter(doc_label(d["doc_type"]) for d in docs)
    return {"total": len(docs), "by_status": dict(by_status), "by_type": dict(by_type)}


def draft_reminder(document_id: int, tone: str = "สุภาพ") -> dict:
    d = db.get_document(document_id)
    if not d:
        return {"error": f"ไม่พบเอกสาร id={document_id}"}
    d = enrich([d])[0]
    return {"document": _brief(d), "tone": tone,
            "instruction": "ใช้ข้อมูลนี้ร่างข้อความแจ้งเตือนภาษาไทยถึงผู้รับผิดชอบรถคันนี้"}


TOOLS = {
    "search_documents": search_documents,
    "list_expiring": list_expiring,
    "get_owner_summary": get_owner_summary,
    "get_stats": get_stats,
    "draft_reminder": draft_reminder,
}

TOOL_SCHEMAS = [
    {
        "name": "search_documents",
        "description": "ค้นหาเอกสารตามทะเบียนรถ ชื่อคนขับ หรือเลขที่เอกสาร กรองตามประเภท/สถานะได้",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "ข้อความค้นหา (เว้นว่างได้)"},
                "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
                "status": {"type": "string", "enum": ["EXPIRED", "EXPIRING", "VALID", "UNKNOWN"]},
            },
            "required": [],
        },
    },
    {
        "name": "list_expiring",
        "description": "รายการเอกสารที่จะหมดอายุภายใน N วัน (รวมที่หมดแล้วด้วยเป็นค่าเริ่มต้น) เรียงจากใกล้หมดที่สุด",
        "input_schema": {
            "type": "object",
            "properties": {
                "within_days": {"type": "integer", "description": "จำนวนวันนับจากวันนี้"},
                "include_expired": {"type": "boolean"},
            },
            "required": ["within_days"],
        },
    },
    {
        "name": "get_owner_summary",
        "description": "สรุปเอกสารของรถหนึ่งคัน (ภาษี/พ.ร.บ./ประกัน + คนขับประจำและใบขับขี่) ค้นด้วยทะเบียน เช่น 70-1234 หรือสรุปของคนขับหนึ่งคน ค้นด้วยชื่อ",
        "input_schema": {
            "type": "object",
            "properties": {"identifier": {"type": "string"}},
            "required": ["identifier"],
        },
    },
    {
        "name": "get_stats",
        "description": "สถิติภาพรวม: จำนวนเอกสารทั้งหมด แยกตามสถานะและประเภท",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "draft_reminder",
        "description": "ดึงข้อมูลเอกสารหนึ่งฉบับเพื่อใช้ร่างข้อความแจ้งเตือน (ไม่ได้ส่งจริง)",
        "input_schema": {
            "type": "object",
            "properties": {"document_id": {"type": "integer"}, "tone": {"type": "string"}},
            "required": ["document_id"],
        },
    },
]
