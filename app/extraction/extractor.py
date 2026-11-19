"""Document classification + key-information extraction.

Two engines:
* ``claude``  – Claude vision reads the image/PDF and returns JSON (structured outputs).
* ``rules``   – offline fallback: pypdf text layer / .txt + keyword & regex rules.
               Used when no API key is configured and as a baseline for evaluation.

Both return the same dict shape, which is then normalised (dates parsed in code)
and scored by ``app.core.validator``.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from pathlib import Path

from app import config
from app.core import validator
from app.extraction.thai_date import find_dates, parse_date

DOC_TYPE_ENUM = list(config.DOC_TYPES.keys())

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": DOC_TYPE_ENUM},
        "doc_number": {"type": ["string", "null"]},
        "holder_name": {"type": ["string", "null"]},
        "vehicle_plate": {"type": ["string", "null"]},
        "issuing_authority": {"type": ["string", "null"]},
        "issue_date_raw": {"type": ["string", "null"]},
        "expiry_date_raw": {"type": ["string", "null"]},
        "year_system": {"type": "string", "enum": ["BUDDHIST", "GREGORIAN", "UNKNOWN"]},
        "field_confidence": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in (*validator.KEY_FIELDS, "holder_name")},
            "required": [*validator.KEY_FIELDS, "holder_name"],
            "additionalProperties": False,
        },
        "notes": {"type": "string"},
    },
    "required": ["doc_type", "doc_number", "holder_name", "vehicle_plate", "issuing_authority",
                 "issue_date_raw", "expiry_date_raw", "year_system", "field_confidence", "notes"],
    "additionalProperties": False,
}

DOC_TYPE_GUIDE = "\n".join(f"- {k}: {v[0]}" for k, v in config.DOC_TYPES.items())

EXTRACTION_PROMPT = f"""คุณคือระบบอ่านเอกสารรถและใบขับขี่ของฝ่ายธุรการบริษัทขนส่ง อ่านเอกสารที่แนบมาแล้วดึงข้อมูลตาม schema

ประเภทเอกสาร (doc_type):
{DOC_TYPE_GUIDE}

กติกา:
1. expiry_date_raw = วันหมดอายุ / วันครบกำหนดเสียภาษี / วันสิ้นสุดความคุ้มครอง — คัดลอกข้อความวันที่ตามที่ปรากฏในเอกสารทุกตัวอักษร (เช่น "28 ก.พ. 2570" หรือ "28/02/2027") ห้ามแปลงปีหรือคำนวณเอง
2. issue_date_raw = วันออกเอกสาร / วันเริ่มคุ้มครอง (คัดลอกตามจริงเช่นกัน) — อย่าสับสนกับวันจดทะเบียนรถหรือวันเกิด
3. year_system = BUDDHIST ถ้าปีในเอกสารเป็น พ.ศ., GREGORIAN ถ้าเป็น ค.ศ.
4. เอกสารรถ: vehicle_plate = ทะเบียนรถพร้อมจังหวัด (เช่น "70-1234 ชลบุรี"), holder_name = ชื่อผู้เอาประกัน/เจ้าของรถ
   ใบขับขี่ (DRIVER_LICENSE): holder_name = ชื่อ-สกุลคนขับ, vehicle_plate = null
5. ถ้าเอกสารไม่ใช่เอกสารรถหรือใบขับขี่ ให้ใช้ doc_type = OTHER และอธิบายใน notes
6. ถ้าไม่พบฟิลด์ใดให้ใส่ null — ห้ามเดา
7. field_confidence = ความมั่นใจ 0–1 ของแต่ละฟิลด์ (ภาพเบลอ/ตัวอักษรไม่ชัด/มีหลายวันที่ให้คะแนนต่ำ)
8. notes = ข้อสังเกตสั้น ๆ ภาษาไทย (เช่น ภาพเอียง, มีหลายวันที่)"""

SUPPORTED_IMAGE = {"image/png", "image/jpeg", "image/webp", "image/gif"}


# --------------------------------------------------------------------------- Claude engine
def _claude_client():
    import anthropic

    return anthropic.Anthropic()


def call_claude(**kwargs):
    """messages.create with server-side refusal fallbacks; plain request if the beta is rejected
    (e.g. models without server-side fallback)."""
    import anthropic

    client = _claude_client()
    try:
        return client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        )
    except anthropic.BadRequestError:
        return client.messages.create(**kwargs)


def usage_of(resp, seconds: float) -> dict:
    """Tokens, wall-clock time and cost of one API call (priced by the model that actually served it)."""
    model = getattr(resp, "model", "") or ""
    u = resp.usage
    inp = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) \
        + (getattr(u, "cache_read_input_tokens", 0) or 0)
    out = u.output_tokens or 0
    usd = config.cost_usd(model, inp, out)
    return {"model": model, "input_tokens": inp, "output_tokens": out, "seconds": round(seconds, 2),
            "cost_usd": round(usd, 6) if usd is not None else None,
            "cost_thb": round(usd * config.USD_TO_THB, 4) if usd is not None else None}


def _file_block(path: Path) -> dict:
    mime = mimetypes.guess_type(path.name)[0] or ""
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    if mime == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": data}}
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in SUPPORTED_IMAGE:
        raise ValueError(f"ไม่รองรับไฟล์ชนิด {mime or path.suffix}")
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}


def extract_with_claude(path: Path, model: str | None = None) -> dict:
    model = model or config.CLAUDE_MODEL
    if path.suffix.lower() == ".txt":
        content = [{"type": "text", "text": path.read_text(encoding="utf-8")}]
    else:
        content = [_file_block(path)]
    content.append({"type": "text", "text": EXTRACTION_PROMPT})
    t0 = time.perf_counter()
    resp = call_claude(
        model=model,
        max_tokens=16000,
        output_config={"effort": config.EXTRACTION_EFFORT,
                       "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    usage = usage_of(resp, time.perf_counter() - t0)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude ปฏิเสธการประมวลผลเอกสารนี้")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("คำตอบยาวเกิน max_tokens")
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    data["engine"] = f"claude:{usage['model'] or model}"
    data["usage"] = usage
    return data


# --------------------------------------------------------------------------- Rule-based engine
KEYWORDS = [
    ("DRIVER_LICENSE", ["ใบอนุญาตขับรถ", "ใบขับขี่", "driving licence", "driving license"]),
    ("COMPULSORY_INSURANCE", ["พ.ร.บ.", "คุ้มครองผู้ประสบภัย", "compulsory"]),
    ("VEHICLE_TAX", ["ภาษีรถ", "เครื่องหมายแสดงการเสียภาษี", "ป้ายภาษี", "ป้ายวงกลม"]),
    ("VEHICLE_INSURANCE", ["กรมธรรม์", "ประกันภัยรถ", "policy", "motor insurance"]),
]
EXPIRY_HINT = re.compile(r"(หมดอายุ|สิ้นสุด|ใช้ได้ถึง|ถึงวันที่|valid until|expir|ครบกำหนด|\bto\b)", re.I)
ISSUE_HINT = re.compile(r"(วันออก|ออกให้|วันที่ออก|เริ่ม|issue|ตั้งแต่|\bfrom\b)", re.I)
NUMBER_RE = re.compile(r"(?:เลขที่|ฉบับที่|No\.?|Number|กรมธรรม์เลขที่)\s*[:：]?\s*([A-Za-z0-9/\-]{4,})", re.I)
NAME_RE = re.compile(r"(?:ชื่อ(?:ผู้เอาประกันภัย|ผู้เอาประกัน|เจ้าของรถ|ผู้ถือ)?|Insured|Name)\s*[:：]?\s*([^\n:]{3,60})", re.I)
PLATE_TEXT_RE = re.compile(
    r"(?:ทะเบียน(?:รถ)?|Registration(?:\s*No\.?)?|Plate)\s*[:：]?\s*"
    r"([0-9]{0,2}\s*[ก-ฮ]{0,2}\s*-?\s*[0-9]{1,4}(?:\s+[ก-๙A-Za-z]+)?)", re.I)


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    return ""


def extract_with_rules(path: Path) -> dict:
    text = _read_text(path)
    lower = text.lower()
    doc_type, type_conf = "OTHER", 0.3
    for t, kws in KEYWORDS:
        if any(k.lower() in lower for k in kws):
            doc_type, type_conf = t, 0.8
            break

    expiry_raw = issue_raw = None
    for line in text.splitlines():
        found = find_dates(line)
        if not found:
            continue
        if EXPIRY_HINT.search(line) and not expiry_raw:
            expiry_raw = found[-1][0]
            if len(found) >= 2 and not issue_raw:  # "เริ่มต้น <date> สิ้นสุด <date>" on one line
                issue_raw = found[0][0]
        elif ISSUE_HINT.search(line) and not issue_raw:
            issue_raw = found[0][0]
    all_dates = find_dates(text)
    exp_conf = 0.75 if expiry_raw else 0.0
    if not expiry_raw and all_dates:  # guess: latest date in document
        expiry_raw = max(all_dates, key=lambda x: x[1])[0]
        exp_conf = 0.4

    num = NUMBER_RE.search(text)
    name = NAME_RE.search(text)
    plate = PLATE_TEXT_RE.search(text)
    return {
        "doc_type": doc_type,
        "doc_number": num.group(1).strip() if num else None,
        "holder_name": name.group(1).strip() if name else None,
        "vehicle_plate": plate.group(1).strip() if plate else None,
        "issuing_authority": None,
        "issue_date_raw": issue_raw,
        "expiry_date_raw": expiry_raw,
        "year_system": "UNKNOWN",
        "field_confidence": {
            "doc_type": type_conf, "expiry_date": exp_conf,
            "doc_number": 0.7 if num else 0.0, "vehicle_plate": 0.6 if plate else 0.0,
            "holder_name": 0.6 if name else 0.0,
        },
        "notes": "อ่านด้วยกฎ (ไม่มี API key)" if text else "ไม่มีข้อความในไฟล์ — กรุณากรอกข้อมูลเอง",
        "engine": "rules",
    }


# --------------------------------------------------------------------------- Pipeline
def normalise(raw: dict) -> dict:
    """Parse raw date strings into ``date`` objects and attach validation + confidence."""
    buddhist = {"BUDDHIST": True, "GREGORIAN": False}.get(raw.get("year_system", ""), None)
    ex = dict(raw)
    ex["issue_date"] = parse_date(raw.get("issue_date_raw"), buddhist)
    ex["expiry_date"] = parse_date(raw.get("expiry_date_raw"), buddhist)
    if raw.get("expiry_date_raw") and not ex["expiry_date"]:
        ex.setdefault("field_confidence", {})["expiry_date"] = 0.0
    ex["problems"] = validator.validate(ex) + validator.cross_check(ex)
    ex["confidence"] = validator.score(ex, ex["problems"])
    ex["needs_review"] = validator.needs_review(ex["confidence"], ex["problems"])
    return ex


def extract(path: Path, engine: str = "auto", model: str | None = None) -> dict:
    """Run extraction on a file. engine: 'auto' | 'claude' | 'rules'."""
    if engine == "auto":
        engine = "claude" if config.has_claude_credentials() else "rules"
    raw = extract_with_claude(path, model) if engine == "claude" else extract_with_rules(path)
    return normalise(raw)
