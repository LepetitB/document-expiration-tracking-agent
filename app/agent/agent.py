"""Chat agent: Claude with tool use over the document registry.

When no API key is configured, a small keyword router answers using the same tools
so the demo still works offline.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date

from app import config
from app.agent import tools as T
import time

from app.extraction.extractor import call_claude, usage_of
from app.extraction.thai_date import to_thai

MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """คุณคือ "ผู้ช่วยติดตามเอกสารรถ" ของฝ่ายธุรการบริษัทขนส่ง ดูแลเอกสาร 3 อย่างของรถทุกคัน: ภาษีรถประจำปี, พ.ร.บ. (ประกันภาคบังคับ), ประกันภัยรถ (ภาคสมัครใจ) และใบขับขี่ของคนขับประจำรถ ตอบเป็นภาษาไทย กระชับ ชัดเจน
- ข้อมูลเอกสารทุกอย่างต้องมาจาก tool เท่านั้น ห้ามเดาหรือแต่งข้อมูลเอง
- ถ้าผู้ใช้ถามช่วงเวลา (เช่น "เดือนหน้า") ให้คำนวณจำนวนวันจากวันนี้แล้วเรียก list_expiring
- เมื่อแสดงรายการให้ใช้ bullet ระบุ ทะเบียนรถหรือชื่อคนขับ / ประเภทเอกสาร / วันหมดอายุ / เหลือกี่วัน
- ภาษีรถ, พ.ร.บ. หรือใบขับขี่ของคนขับประจำรถ หมดอายุ = ห้ามนำรถออกวิ่ง (ผิดกฎหมาย); ต้องต่อ พ.ร.บ. ก่อนจึงจะชำระภาษีรถได้; ประกันภัยหมด = ถ้าเกิดอุบัติเหตุบริษัทต้องรับผิดชอบค่าเสียหายเอง
- get_owner_summary ของรถจะบอกคนขับประจำรถและใบขับขี่ด้วย
- จัดลำดับความสำคัญ: หมดอายุแล้ว > ใกล้หมด; ภาษี/พ.ร.บ./ใบขับขี่ ก่อนประกันภัย
- คุณส่งข้อความแจ้งเตือนเองไม่ได้ ถ้าผู้ใช้ต้องการส่ง ให้บอกว่ากดปุ่ม "ตรวจและส่งแจ้งเตือน" ในหน้าแจ้งเตือน (ระบบจะส่ง LINE ถึงคนขับที่เกี่ยวข้องให้เอง)"""

# conversation id -> list of message dicts (kept server-side so thinking blocks are replayed unchanged)
_CONVERSATIONS: dict[str, list[dict]] = {}


def new_conversation() -> str:
    cid = uuid.uuid4().hex
    _CONVERSATIONS[cid] = []
    return cid


def _run_tool(name: str, args: dict) -> str:
    fn = T.TOOLS.get(name)
    if not fn:
        raise ValueError(f"unknown tool {name}")
    return json.dumps(fn(**args), ensure_ascii=False)


def chat_claude(cid: str, user_text: str) -> tuple[str, list[str], dict]:
    messages = _CONVERSATIONS.setdefault(cid, [])
    messages.append({"role": "user", "content": user_text})
    system = SYSTEM_PROMPT + f"\n\nวันนี้คือ {date.today().isoformat()} ({to_thai(date.today())})"
    used: list[str] = []
    total = {"calls": 0, "seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_thb": 0.0}
    for _ in range(MAX_TOOL_ROUNDS):
        t0 = time.perf_counter()
        resp = call_claude(model=config.CLAUDE_MODEL, max_tokens=16000, system=system,
                           tools=T.TOOL_SCHEMAS, messages=messages,
                           output_config={"effort": "low"})
        u = usage_of(resp, time.perf_counter() - t0)
        total["calls"] += 1
        for k in ("seconds", "input_tokens", "output_tokens"):
            total[k] += u[k]
        total["cost_thb"] += u["cost_thb"] or 0.0
        messages.append({"role": "assistant",
                         "content": [b.model_dump(mode="json", exclude_none=True) for b in resp.content]})
        if resp.stop_reason == "refusal":
            return "ขออภัย ไม่สามารถตอบคำถามนี้ได้", used, total
        if resp.stop_reason != "tool_use":
            text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
            return text or "(ไม่มีคำตอบ)", used, total
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            used.append(b.name)
            try:
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": _run_tool(b.name, dict(b.input or {}))})
            except Exception as e:
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": f"error: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})
    return "ขออภัย ใช้เวลาค้นข้อมูลนานเกินไป ลองถามให้เฉพาะเจาะจงขึ้น", used, total


# --------------------------------------------------------------------------- offline fallback
def _fmt(items: list[dict]) -> str:
    if not items:
        return "ไม่พบเอกสารที่ตรงเงื่อนไข"
    lines = []
    for x in items:
        left = x["days_left"]
        when = "ไม่ทราบ" if left is None else (f"เลยมา {-left} วัน" if left < 0 else f"เหลือ {left} วัน")
        icon = "👷" if x.get("owner_type") == config.OWNER_TYPES["DRIVER"] else "🚛"
        lines.append(f"- {icon} **{x['owner']}** — {x['doc_type']} · หมดอายุ {x['expiry_date']} ({when})")
    return "\n".join(lines)


def chat_offline(user_text: str) -> tuple[str, list[str]]:
    t = user_text.strip()
    if re.search(r"ห้าม.*วิ่ง|วิ่งไม่ได้", t):
        insurance = config.doc_label("VEHICLE_INSURANCE")
        bad = [x for x in T.list_expiring(0) if x["days_left"] < 0 and x["doc_type"] != insurance]
        if not bad:
            return "ไม่มีรถที่ห้ามออกวิ่ง ✅", ["list_expiring"]
        return "เอกสารที่ทำให้รถห้ามออกวิ่ง (ภาษี / พ.ร.บ. / ใบขับขี่ หมดอายุ):\n" + _fmt(bad), ["list_expiring"]
    if re.search(r"สถิติ|ภาพรวม|ทั้งหมดกี่|กี่ฉบับ|สรุป", t):
        s = T.get_stats()
        parts = [f"เอกสารทั้งหมด **{s['total']}** ฉบับ"] + [f"- {k}: {v}" for k, v in s["by_status"].items()]
        return "\n".join(parts), ["get_stats"]
    days = None
    m = re.search(r"(\d+)\s*วัน", t)
    if m:
        days = int(m.group(1))
    elif "สัปดาห์" in t:
        days = 7
    elif "เดือนหน้า" in t or "เดือน" in t:
        days = 60 if "เดือนหน้า" in t else 30
    elif "ปี" in t:
        days = 365
    m = re.search(r"(\d{1,2}\s*[ก-ฮ]{0,2}\s*-\s*\d{3,4}|[ก-ฮ]{1,3}\s*-?\s*\d{3,4})", t)
    if m:
        r = T.get_owner_summary(m.group(1).replace(" ", ""))
        if r["found"]:
            text = f"เอกสารของรถ **{r['owner']}**\n" + _fmt(r["documents"])
            if r.get("driver"):
                text += f"\n\nคนขับประจำรถ: **{r['driver']}**"
                if r.get("driver_license"):
                    text += "\n" + _fmt(r["driver_license"])
            return text, ["get_owner_summary"]
    if re.search(r"หมดอายุแล้ว|เลยกำหนด", t):
        return _fmt([x for x in T.list_expiring(0) if x["days_left"] < 0]), ["list_expiring"]
    for key, dt in (("ใบขับขี่", "DRIVER_LICENSE"), ("คนขับ", "DRIVER_LICENSE"), ("พ.ร.บ", "COMPULSORY_INSURANCE"),
                    ("ภาษี", "VEHICLE_TAX"), ("ประกัน", "VEHICLE_INSURANCE")):
        if key in t:
            label = config.doc_label(dt)
            return _fmt([x for x in T.list_expiring(days or 60) if x["doc_type"] == label]), ["list_expiring"]
    if days is not None or re.search(r"ใกล้หมด|ต้องต่อ|หมดอายุ", t):
        return _fmt(T.list_expiring(days or 30)), ["list_expiring"]
    found = T.search_documents(t)
    if found:
        return _fmt(found), ["search_documents"]
    return ("โหมดออฟไลน์ (ไม่มี API key) รองรับคำถามแบบง่าย เช่น\n"
            "- \"รถคันไหนห้ามออกวิ่งบ้าง\"\n- \"30 วันข้างหน้ามีอะไรต้องต่อบ้าง\"\n"
            "- \"รถ 70-1234\"\n- \"ใบขับขี่คนขับคนไหนใกล้หมด\""), []


def chat(cid: str, user_text: str) -> dict:
    if config.has_claude_credentials():
        try:
            answer, used, usage = chat_claude(cid, user_text)
            usage["seconds"] = round(usage["seconds"], 1)
            usage["cost_thb"] = round(usage["cost_thb"], 3)
            return {"answer": answer, "tools": used, "engine": "claude", "usage": usage}
        except Exception as e:
            _CONVERSATIONS.pop(cid, None)
            answer, used = chat_offline(user_text)
            return {"answer": f"_(เรียก Claude ไม่สำเร็จ: {e} — ตอบด้วยโหมดออฟไลน์)_\n\n{answer}",
                    "tools": used, "engine": "offline"}
    answer, used = chat_offline(user_text)
    return {"answer": answer, "tools": used, "engine": "offline"}
