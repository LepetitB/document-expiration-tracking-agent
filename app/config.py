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


# Standard Anthropic API prices, USD per 1M tokens (input, output). Haiku 5.5 price is for prompts up to 100K tokens.
MODEL_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
USD_TO_THB = float(os.getenv("USD_TO_THB", "35"))  # assumption — set the current rate in .env


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = MODEL_PRICES.get(model)
    if not price:
        return None
    return input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1]


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
# Scope: "can this vehicle legally go out today?" — the vehicle's documents + its assigned driver's licence.
COMPANY_NAME = "บริษัท สยามฟลีท ทรานสปอร์ต จำกัด (สมมติ)"
OWNER_TYPES = {"VEHICLE": "รถ", "DRIVER": "คนขับ"}

# doc_type -> (Thai label, owner type, "expiring soon" window in days)
DOC_TYPES: dict[str, tuple[str, str, int]] = {
    "VEHICLE_TAX": ("ภาษีรถประจำปี", "VEHICLE", 30),
    "COMPULSORY_INSURANCE": ("พ.ร.บ. (ประกันภาคบังคับ)", "VEHICLE", 30),
    "VEHICLE_INSURANCE": ("ประกันภัยรถ (ภาคสมัครใจ)", "VEHICLE", 30),
    "DRIVER_LICENSE": ("ใบอนุญาตขับรถ (ใบขับขี่)", "DRIVER", 30),
    "OTHER": ("เอกสารรถอื่น ๆ", "VEHICLE", 30),
}
# the three documents every vehicle must keep valid (columns of the per-vehicle view)
MAIN_DOC_TYPES = ["VEHICLE_TAX", "COMPULSORY_INSURANCE", "VEHICLE_INSURANCE"]
SHORT_LABEL = {"VEHICLE_TAX": "ภาษีรถ", "COMPULSORY_INSURANCE": "พ.ร.บ.", "VEHICLE_INSURANCE": "ประกันภัย",
               "DRIVER_LICENSE": "ใบขับขี่", "OTHER": "อื่น ๆ"}

# LINE messages to drivers: real push via LINE Messaging API when LINE_CHANNEL_TOKEN is set and the driver
# has a LINE userId (they must add the company's LINE OA as a friend); otherwise simulated in the outbox.

ALERT_THRESHOLDS = [90, 60, 30, 7, 0]  # days before expiry
AUTO_CONFIRM_CONFIDENCE = 0.85


def doc_label(doc_type: str) -> str:
    return DOC_TYPES.get(doc_type, (doc_type,))[0]
