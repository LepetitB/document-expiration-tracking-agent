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
        "file": "01_tax_70-1234",
        "truth": {"doc_type": "VEHICLE_TAX", "doc_number": "6900123", "expiry_date": "2026-11-26",
                  "plate": "70-1234"},
        "text": """เครื่องหมายแสดงการเสียภาษีรถ (ป้ายวงกลม)
กรมการขนส่งทางบก
ทะเบียน 70-1234 ชลบุรี
เลขที่ 6900123
ประเภท รถบรรทุกส่วนบุคคล
วันจดทะเบียน 14 มีนาคม 2560
วันครบกำหนดเสียภาษี / หมดอายุ 26/11/69""",
    },
    {
        "file": "02_tax_72-4410",
        "truth": {"doc_type": "VEHICLE_TAX", "doc_number": "6904410", "expiry_date": "2027-07-22",
                  "plate": "72-4410"},
        "text": """เครื่องหมายแสดงการเสียภาษีรถ
ทะเบียน 72-4410 ชลบุรี
เลขที่ 6904410
ชำระภาษีวันที่ 22 กรกฎาคม 2569
วันสิ้นอายุ 22 กรกฎาคม 2570""",
    },
    {
        "file": "03_prb_71-0099",
        "truth": {"doc_type": "COMPULSORY_INSURANCE", "doc_number": "CMI-25681201-55",
                  "expiry_date": "2026-12-01", "plate": "71-0099"},
        "text": """กรมธรรม์ประกันภัยคุ้มครองผู้ประสบภัยจากรถ (พ.ร.บ.)
บริษัท ไทยประกันภัยตัวอย่าง จำกัด (มหาชน)
กรมธรรม์เลขที่ CMI-25681201-55
ชื่อผู้เอาประกัน บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 71-0099 ระยอง
ระยะเวลาประกันภัย เริ่มต้น ๑ ธ.ค. ๒๕๖๘ สิ้นสุด ๑ ธ.ค. ๒๕๖๙""",
    },
    {
        "file": "04_prb_70-5678",
        "truth": {"doc_type": "COMPULSORY_INSURANCE", "doc_number": "CMI-25691217-08",
                  "expiry_date": "2026-12-17", "plate": "70-5678"},
        "text": """ใบรับรองการประกันภัยตาม พ.ร.บ. คุ้มครองผู้ประสบภัยจากรถ
กรมธรรม์เลขที่ CMI-25691217-08
ผู้เอาประกันภัย บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 70-5678 ชลบุรี
ตั้งแต่วันที่ 17/12/2568 ถึงวันที่ 17/12/2569""",
    },
    {
        "file": "05_insurance_70-1234",
        "truth": {"doc_type": "VEHICLE_INSURANCE", "doc_number": "POL-V1-554021", "expiry_date": "2027-02-18",
                  "plate": "70-1234"},
        "text": """ตารางกรมธรรม์ประกันภัยรถยนต์ ประเภท 1
กรมธรรม์เลขที่ POL-V1-554021
ชื่อผู้เอาประกันภัย บริษัท สยามฟลีท ทรานสปอร์ต จำกัด
ทะเบียนรถ 70-1234 ชลบุรี
ระยะเวลาประกันภัย ตั้งแต่วันที่ 18 กุมภาพันธ์ 2569 ถึงวันที่ 18 กุมภาพันธ์ 2570""",
    },
    {
        "file": "06_insurance_72-9045_english",
        "truth": {"doc_type": "VEHICLE_INSURANCE", "doc_number": "MTR-2026-009045", "expiry_date": "2026-12-04",
                  "plate": "72-9045"},
        "text": """MOTOR INSURANCE POLICY SCHEDULE (Class 2+)
Policy No. MTR-2026-009045
Insured: Siam Fleet Transport Co., Ltd.
Registration No. 72-9045 Chachoengsao
Period of insurance: from 4 Dec 2025 to 4 Dec 2026""",
    },
    {
        "file": "07_insurance_71-3307",
        "truth": {"doc_type": "VEHICLE_INSURANCE", "doc_number": "POL-V3-713307", "expiry_date": "2026-12-29",
                  "plate": "71-3307"},
        "text": """กรมธรรม์ประกันภัยรถยนต์ ประเภท 3
เลขที่ POL-V3-713307
ทะเบียนรถ 71-3307 ระยอง
วันที่ออกกรมธรรม์ 20 ธ.ค. 2568
คุ้มครอง 29 ธ.ค. 2568 - 29 ธ.ค. 2569 (เวลา 16.30 น.)""",
    },
    {
        "file": "08_driver_license_surachai",
        "truth": {"doc_type": "DRIVER_LICENSE", "doc_number": "64012345", "expiry_date": "2026-12-02",
                  "holder": "สุรชัย พึ่งบุญ"},
        "text": """ใบอนุญาตขับรถยนต์ส่วนบุคคล ชนิดที่ 2 (ท.2)
กรมการขนส่งทางบก
ฉบับที่ 64012345
ชื่อ นายสุรชัย พึ่งบุญ
เกิดวันที่ 3 มีนาคม 2525
วันอนุญาต 2 ธันวาคม 2564
วันสิ้นอายุ 2 ธันวาคม 2569""",
    },
    {
        "file": "09_driver_license_boonlert",
        "truth": {"doc_type": "DRIVER_LICENSE", "doc_number": "63098712", "expiry_date": "2027-07-09",
                  "holder": "บุญเลิศ ใจงาม"},
        "text": """DRIVING LICENCE / ใบอนุญาตขับรถ ท.3
No. 63098712
Name: Mr. Boonlert Jaingam / นายบุญเลิศ ใจงาม
Date of Birth 12 Aug 1985
Issue Date 9 Jul 2022
Expiry Date 9 Jul 2027""",
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
