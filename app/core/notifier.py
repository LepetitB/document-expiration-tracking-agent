"""Daily expiry check + notification delivery (email / Discord / LINE / local outbox)."""
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


def build_message(doc: dict) -> str:
    left = doc["days_left"]
    when = "หมดอายุแล้ว" if left < 0 else ("หมดอายุวันนี้" if left == 0 else f"จะหมดอายุในอีก {left} วัน")
    plate = doc.get("owner_name") or "-"
    return (f"⚠️ {doc_label(doc['doc_type'])} รถทะเบียน {plate} {when} "
            f"(วันหมดอายุ {to_thai(date.fromisoformat(doc['expiry_date']))}) "
            f"เลขที่ {doc.get('doc_number') or '-'} — กรุณาดำเนินการต่ออายุ")


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
        db.log_notification(d["id"], t, ",".join(channels) or "failed", msg)
        sent.append({"document_id": d["id"], "threshold": t, "message": msg, "channels": channels})
    return sent
