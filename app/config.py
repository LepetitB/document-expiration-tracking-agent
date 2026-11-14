"""Central configuration: paths, document types, alert thresholds."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "app.db"))
OUTBOX_DIR = DATA_DIR / "outbox"  # notifications are written here when no channel is configured

for _d in (DATA_DIR, UPLOAD_DIR, OUTBOX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- LLM -------------------------------------------------------------------
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
EXTRACTION_EFFORT = os.getenv("EXTRACTION_EFFORT", "medium")


def has_claude_credentials() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


# --- Notification channels (all optional) ----------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN", "")
LINE_TO = os.getenv("LINE_TO", "")

# --- Domain ----------------------------------------------------------------
OWNER_TYPES = {
    "EMPLOYEE": "พนักงาน",
    "VEHICLE": "รถ",
    "COMPANY": "บริษัท",
    "CUSTOMER": "ลูกค้า",
}

# doc_type -> (Thai label, owner type, "expiring soon" window in days)
DOC_TYPES: dict[str, tuple[str, str, int]] = {
    "DRIVER_LICENSE": ("ใบอนุญาตขับรถ", "EMPLOYEE", 30),
    "WORK_PERMIT": ("ใบอนุญาตทำงาน (Work Permit)", "EMPLOYEE", 60),
    "VISA": ("วีซ่า", "EMPLOYEE", 60),
    "VEHICLE_TAX": ("ภาษีรถประจำปี", "VEHICLE", 30),
    "COMPULSORY_INSURANCE": ("พ.ร.บ. คุ้มครองผู้ประสบภัยจากรถ", "VEHICLE", 30),
    "VEHICLE_INSURANCE": ("กรมธรรม์ประกันภัยรถยนต์", "VEHICLE", 30),
    "TRANSPORT_LICENSE": ("ใบอนุญาตประกอบการขนส่ง", "COMPANY", 90),
    "CONTRACT": ("สัญญาจ้างขนส่ง", "CUSTOMER", 60),
    "OTHER": ("เอกสารอื่น ๆ", "COMPANY", 30),
}

ALERT_THRESHOLDS = [90, 60, 30, 7, 0]  # days before expiry
AUTO_CONFIRM_CONFIDENCE = 0.85


def doc_label(doc_type: str) -> str:
    return DOC_TYPES.get(doc_type, (doc_type,))[0]
