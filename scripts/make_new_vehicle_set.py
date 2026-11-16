"""Generate a demo document set for a *new* vehicle (73-5555), for the intake demo.

    python scripts/make_new_vehicle_set.py

Writes data/samples/new_vehicle_73-5555/*.png — upload them together on "รับรถ / แนบเอกสาร".
All data is fictional.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "samples" / "new_vehicle_73-5555"
OUT.mkdir(parents=True, exist_ok=True)

THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
               "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def thai(d: date) -> str:
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


today = date.today()
tax_exp = today + timedelta(days=365)
prb_start, prb_exp = today - timedelta(days=5), today - timedelta(days=5) + timedelta(days=365)
ins_start, ins_exp = today + timedelta(days=2), today + timedelta(days=2) + timedelta(days=365)

DOCS = {
    "1_tax_73-5555": f"""เครื่องหมายแสดงการเสียภาษีรถ (ป้ายวงกลม)
กรมการขนส่งทางบก
ทะเบียน 73-5555 ชลบุรี
เลขที่ 7355550
ประเภท รถบรรทุกส่วนบุคคล
วันครบกำหนดเสียภาษี {tax_exp:%d/%m}/{tax_exp.year + 543}""",
    "2_prb_73-5555": f"""กรมธรรม์ประกันภัยคุ้มครองผู้ประสบภัยจากรถ (พ.ร.บ.)
บริษัท ไทยประกันภัยตัวอย่าง จำกัด
กรมธรรม์เลขที่ CMI-25690735-55
ผู้เอาประกัน บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 73-5555 ชลบุรี
คุ้มครอง ตั้งแต่ {thai(prb_start)} ถึง {thai(prb_exp)}""",
    "3_insurance_73-5555": f"""ตารางกรมธรรม์ประกันภัยรถยนต์ ประเภท 1
กรมธรรม์เลขที่ POL-V1-735555
ชื่อผู้เอาประกันภัย บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 73-5555 ชลบุรี
ระยะเวลาประกันภัย {thai(ins_start)} - {thai(ins_exp)}""",
}

font = ImageFont.truetype("C:/Windows/Fonts/tahoma.ttf", 26)
head = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", 30)
rnd = random.Random(55)
for name, text in DOCS.items():
    lines = text.splitlines()
    img = Image.new("RGB", (1000, 120 + 52 * len(lines)), (250, 248, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, img.width - 12, img.height - 12], outline=(40, 70, 140), width=4)
    for i, line in enumerate(lines):
        d.text((50, 40 + 52 * i), line, fill=(25, 25, 35), font=head if i == 0 else font)
    d.text((img.width - 260, img.height - 50), "ตัวอย่าง / SAMPLE", fill=(200, 60, 60), font=font)
    img = img.rotate(rnd.uniform(-2.5, 2.5), expand=True, fillcolor=(120, 120, 120)).filter(ImageFilter.GaussianBlur(0.6))
    img.save(OUT / f"{name}.png")
print(f"wrote {len(DOCS)} images to {OUT}")
