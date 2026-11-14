"""Generate synthetic sample documents (fictional data) + ground truth for evaluation.

    python scripts/make_samples.py

Writes data/samples/*.txt (text documents) and *.png (rendered "photos" for Claude Vision),
plus data/samples/ground_truth.json.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    {
        "file": "01_driver_license_somchai",
        "truth": {"doc_type": "DRIVER_LICENSE", "doc_number": "64012345", "expiry_date": "2027-01-15",
                  "holder": "นายสมชาย ใจดี"},
        "text": """ใบอนุญาตขับรถ ชนิดที่ 2 (ท.2)
กรมการขนส่งทางบก
เลขที่ 64012345
ชื่อ นายสมชาย ใจดี
วันเกิด 3 มีนาคม 2525
วันออกใบอนุญาต 15 มกราคม 2565
วันหมดอายุ 15 มกราคม 2570""",
    },
    {
        "file": "02_vehicle_tax_70-1234",
        "truth": {"doc_type": "VEHICLE_TAX", "doc_number": "6900123", "expiry_date": "2026-11-26",
                  "holder": "70-1234"},
        "text": """เครื่องหมายแสดงการเสียภาษีรถ (ป้ายวงกลม)
ทะเบียน 70-1234 ชลบุรี
เลขที่ 6900123
ประเภท รถบรรทุกส่วนบุคคล
ชื่อ บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
วันครบกำหนดเสียภาษี / หมดอายุ 26/11/69""",
    },
    {
        "file": "03_compulsory_insurance_71-0099",
        "truth": {"doc_type": "COMPULSORY_INSURANCE", "doc_number": "CMI-25681201-55",
                  "expiry_date": "2026-12-01", "holder": "71-0099"},
        "text": """กรมธรรม์ประกันภัยคุ้มครองผู้ประสบภัยจากรถ (พ.ร.บ.)
บริษัท ไทยประกันภัยตัวอย่าง จำกัด (มหาชน)
กรมธรรม์เลขที่ CMI-25681201-55
ชื่อผู้เอาประกัน บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 71-0099 ระยอง
ระยะเวลาประกันภัย เริ่มต้น ๑ ธ.ค. ๒๕๖๘ สิ้นสุด ๑ ธ.ค. ๒๕๖๙""",
    },
    {
        "file": "04_work_permit_aung",
        "truth": {"doc_type": "WORK_PERMIT", "doc_number": "WP-0067-889201", "expiry_date": "2027-03-31",
                  "holder": "Mr. Aung Ko Ko"},
        "text": """WORK PERMIT / ใบอนุญาตทำงาน
Department of Employment, Ministry of Labour
No. WP-0067-889201
Name: Mr. Aung Ko Ko
Nationality: Myanmar
Employer: Siam Fleet Transport Co., Ltd.
Date of issue: 1 Apr 2025
Valid until: 31 Mar 2027""",
    },
    {
        "file": "05_vehicle_insurance_70-1234",
        "truth": {"doc_type": "VEHICLE_INSURANCE", "doc_number": "POL-V1-554021", "expiry_date": "2027-02-18",
                  "holder": "70-1234"},
        "text": """ตารางกรมธรรม์ประกันภัยรถยนต์ ประเภท 1
กรมธรรม์เลขที่ POL-V1-554021
ชื่อผู้เอาประกันภัย บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 70-1234 ชลบุรี
ระยะเวลาประกันภัย ตั้งแต่วันที่ 18 กุมภาพันธ์ 2569 ถึงวันที่ 18 กุมภาพันธ์ 2570""",
    },
    {
        "file": "06_transport_license_company",
        "truth": {"doc_type": "TRANSPORT_LICENSE", "doc_number": "20-0451", "expiry_date": "2027-02-02",
                  "holder": "บริษัท สยามฟลีท ทรานสปอร์ต จำกัด"},
        "text": """ใบอนุญาตประกอบการขนส่งส่วนบุคคล
กรมการขนส่งทางบก
ใบอนุญาตเลขที่ 20-0451
ผู้รับใบอนุญาต บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ออกให้ ณ วันที่ 2 ก.พ. 2563
ใช้ได้ถึงวันที่ 2 ก.พ. 2570""",
    },
    {
        "file": "07_contract_thai_retail",
        "truth": {"doc_type": "CONTRACT", "doc_number": "CT-2025-0107", "expiry_date": "2027-01-10",
                  "holder": "บริษัท ไทยรีเทล ซัพพลาย จำกัด"},
        "text": """สัญญาจ้างขนส่งสินค้า
สัญญาเลขที่ CT-2025-0107
คู่สัญญา บริษัท ไทยรีเทล ซัพพลาย จำกัด
ทำ ณ วันที่ 10 มกราคม 2568
สัญญานี้มีผลตั้งแต่วันที่ 10 มกราคม 2568 และสิ้นสุดวันที่ 10 มกราคม 2570""",
    },
]


def write_text() -> None:
    for s in SAMPLES:
        (OUT / f"{s['file']}.txt").write_text(s["text"] + "\n", encoding="utf-8")


def write_png() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        print("Pillow not installed — skipping PNG samples")
        return
    font_path = Path("C:/Windows/Fonts/tahoma.ttf")
    if not font_path.exists():
        print("Tahoma font not found — skipping PNG samples")
        return
    font = ImageFont.truetype(str(font_path), 26)
    head = ImageFont.truetype(str(Path("C:/Windows/Fonts/tahomabd.ttf")), 30)
    rnd = random.Random(7)
    for s in SAMPLES:
        lines = s["text"].splitlines()
        img = Image.new("RGB", (1000, 120 + 52 * len(lines)), (250, 248, 240))
        d = ImageDraw.Draw(img)
        d.rectangle([12, 12, img.width - 12, img.height - 12], outline=(40, 70, 140), width=4)
        y = 40
        for i, line in enumerate(lines):
            d.text((50, y), line, fill=(25, 25, 35), font=head if i == 0 else font)
            y += 52
        d.text((img.width - 260, img.height - 50), "ตัวอย่าง / SAMPLE", fill=(200, 60, 60), font=font)
        # make it look like a phone photo: slight rotation + blur
        img = img.rotate(rnd.uniform(-2.5, 2.5), expand=True, fillcolor=(120, 120, 120))
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        img.save(OUT / f"{s['file']}.png")


def main() -> None:
    write_text()
    write_png()
    truth = {s["file"]: s["truth"] for s in SAMPLES}
    (OUT / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(SAMPLES)} samples to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
