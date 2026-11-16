"""Daily expiry check + notification delivery.

Admin team: email / Discord / LINE group / local outbox.  Drivers: LINE (real or simulated), see driver_alert().
"""
from __future__ import annotations

import json
import smtplib
import urllib.request
from datetime import date, datetime
from email.mime.text import MIMEText

from app import config
from app.config import ALERT_THRESHOLDS, doc_label
from app.core.status import enrich
from app.db import database as db
from app.extraction.thai_date import to_thai


def _when(left: int) -> str:
    return "หมดอายุแล้ว" if left < 0 else ("หมดอายุวันนี้" if left == 0 else f"จะหมดอายุในอีก {left} วัน")


def build_message(doc: dict) -> str:
    """Message for the admin team."""
    whose = (f"ของคนขับ {doc.get('owner_name')}" if doc.get("owner_type") == "DRIVER"
             else f"รถทะเบียน {doc.get('owner_name') or '-'}")
    return (f"⚠️ {doc_label(doc['doc_type'])} {whose} {_when(doc['days_left'])} "
            f"(วันหมดอายุ {to_thai(date.fromisoformat(doc['expiry_date']))}) "
            f"เลขที่ {doc.get('doc_number') or '-'} — กรุณาดำเนินการต่ออายุ"
            + (f" (ควรเริ่มต่อตั้งแต่ {to_thai(date.fromisoformat(doc['renew_by']))})"
               if doc.get("renew_by") and doc["days_left"] > 0 else ""))


def driver_alert(doc: dict) -> tuple[dict, str] | None:
    """Who else must hear about this document via LINE, and what to tell them.

    * the driver's own licence is expiring  -> tell the driver to renew it
    * the vehicle a driver uses can no longer legally go out (tax / พ.ร.บ. expired) -> tell its driver
    Insurance and early reminders for vehicle documents stay with the admin team.
    """
    exp = to_thai(date.fromisoformat(doc["expiry_date"]))
    if doc.get("owner_type") == "DRIVER":
        driver = db.get_owner(doc["owner_id"])
        if not driver:
            return None
        if doc["days_left"] < 0:
            text = (f"แจ้งคุณ{driver['name'].removeprefix('นาย').removeprefix('นาง')}: ใบขับขี่ของคุณหมดอายุแล้ว ({exp}) "
                    f"ห้ามขับรถของบริษัทจนกว่าจะต่ออายุ กรุณาติดต่อฝ่ายธุรการ")
        else:
            text = (f"แจ้งคุณ{driver['name'].removeprefix('นาย').removeprefix('นาง')}: ใบขับขี่ของคุณ{_when(doc['days_left'])} "
                    f"({exp}) กรุณาไปต่ออายุที่สำนักงานขนส่ง แล้วส่งรูปใบขับขี่ใหม่ให้ฝ่ายธุรการ")
        return driver, text
    if doc["doc_type"] in ("VEHICLE_TAX", "COMPULSORY_INSURANCE") and doc["days_left"] < 0 and doc.get("driver_id"):
        driver = db.get_owner(doc["driver_id"])
        if not driver:
            return None
        text = (f"⛔ แจ้งคุณ{driver['name'].removeprefix('นาย').removeprefix('นาง')}: รถ {doc['owner_name']} ที่คุณขับ "
                f"{doc_label(doc['doc_type'])} หมดอายุแล้ว ({exp}) ห้ามนำรถออกวิ่งจนกว่าฝ่ายธุรการจะแจ้งว่าต่อเรียบร้อย")
        return driver, text
    return None


def send_line_to_driver(driver: dict, text: str) -> str:
    """Push a LINE message to a driver. Real push needs LINE_CHANNEL_TOKEN + the driver's LINE userId
    (the driver must add the company LINE OA as a friend); otherwise the message is simulated in the outbox."""
    if config.LINE_CHANNEL_TOKEN and driver.get("line_user_id", "").startswith("U"):
        try:
            _post_json("https://api.line.me/v2/bot/message/push",
                       {"to": driver["line_user_id"], "messages": [{"type": "text", "text": text}]},
                       {"Authorization": f"Bearer {config.LINE_CHANNEL_TOKEN}"})
            return f"LINE→{driver['name']}"
        except Exception as e:
            _write_outbox(f"[ส่ง LINE ถึง {driver['name']} ไม่สำเร็จ: {e}] {text}")
            return f"LINE→{driver['name']} (ไม่สำเร็จ)"
    contact = driver.get("line_user_id") or driver.get("phone") or "ยังไม่มี LINE"
    _write_outbox(f"💬 [LINE จำลอง] ถึง {driver['name']} ({contact}): {text}")
    return f"LINE(จำลอง)→{driver['name']}"


def due_threshold(days_left: int) -> int | None:
    """Return the tightest threshold the document has crossed, e.g. 25 days left -> 30."""
    crossed = [t for t in ALERT_THRESHOLDS if days_left <= t]
    return min(crossed) if crossed else None


def _send_email(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, config.SMTP_USER, config.ALERT_EMAIL_TO
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)


def _post_json(url: str, payload: dict, headers: dict | None = None) -> None:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST",
    )
    urllib.request.urlopen(req, timeout=15).read()


def _write_outbox(text: str) -> None:
    path = config.OUTBOX_DIR / f"{date.today().isoformat()}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%H:%M:%S}] {text}\n")


def active_channels() -> list[str]:
    ch = []
    if config.SMTP_HOST and config.ALERT_EMAIL_TO:
        ch.append("email")
    if config.DISCORD_WEBHOOK_URL:
        ch.append("discord")
    if config.LINE_CHANNEL_TOKEN and config.LINE_TO:
        ch.append("line")
    return ch or ["outbox"]


def deliver(text: str) -> list[str]:
    """Send to every configured channel. Returns list of channels that succeeded."""
    ok = []
    for ch in active_channels():
        try:
            if ch == "email":
                _send_email("แจ้งเตือนเอกสารใกล้หมดอายุ", text)
            elif ch == "discord":
                _post_json(config.DISCORD_WEBHOOK_URL, {"content": text})
            elif ch == "line":
                _post_json("https://api.line.me/v2/bot/message/push",
                           {"to": config.LINE_TO, "messages": [{"type": "text", "text": text}]},
                           {"Authorization": f"Bearer {config.LINE_CHANNEL_TOKEN}"})
            else:
                _write_outbox(text)
            ok.append(ch)
        except Exception as e:  # keep going with other channels
            _write_outbox(f"[ส่งผ่าน {ch} ไม่สำเร็จ: {e}] {text}")
    return ok


def run_expiry_check(today: date | None = None) -> list[dict]:
    """Check every active document and send one alert per crossed threshold (never twice)."""
    sent = []
    docs = enrich(db.list_documents(review_status="CONFIRMED"), today)
    for d in docs:
        if d["days_left"] is None or d["status"] == "RENEWED":
            continue
        t = due_threshold(d["days_left"])
        if t is None or db.notification_sent(d["id"], t):
            continue
        msg = build_message(d)
        channels = deliver(msg)
        logged = msg
        extra = driver_alert(d)
        if extra:
            driver, text = extra
            channels.append(send_line_to_driver(driver, text))
            logged += f"\n💬 ถึงคนขับ: {text}"
        db.log_notification(d["id"], t, ", ".join(channels) or "failed", logged)
        sent.append({"document_id": d["id"], "threshold": t, "message": logged, "channels": channels})
    return sent
