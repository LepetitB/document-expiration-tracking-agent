"""Synthetic demo fleet (fictional plates and document numbers), dated relative to today."""
from __future__ import annotations

from datetime import date, timedelta

from app.config import COMPANY_NAME
from app.db import database as db

# plate, province, days until expiry for (tax, พ.ร.บ., insurance)
FLEET = [
    ("70-1234", "ชลบุรี", 12, 12, 95),
    ("70-5678", "ชลบุรี", 33, 33, 140),
    ("71-0099", "ระยอง", 200, -3, 3),
    ("72-4410", "ชลบุรี", 250, 250, 250),
    ("70-8821", "ชลบุรี", -20, 340, 340),
    ("71-3307", "ระยอง", 45, 45, 45),
    ("70-2299", "ชลบุรี", 25, 25, 180),
    ("72-0157", "ฉะเชิงเทรา", 60, 60, -15),
    ("71-5530", "ระยอง", 300, 300, 300),
    ("70-6612", "ชลบุรี", 7, 7, 7),
    ("72-9045", "ฉะเชิงเทรา", 150, 150, 20),
    ("70-3388", "ชลบุรี", 90, 90, 210),
]
INSURERS = ["บริษัท ไทยประกันภัยตัวอย่าง จำกัด", "บริษัท สยามประกันภัยสมมติ จำกัด"]


def seed(reset: bool = False) -> int:
    if reset:
        db.reset_all()
    else:
        db.init_db()
    today = date.today()
    n = 0
    for i, (plate, province, tax, prb, ins) in enumerate(FLEET):
        name = f"{plate} {province}"
        owner_id = db.upsert_owner("VEHICLE", name, plate, responsible_person="ฝ่ายธุรการ")
        digits = plate.replace("-", "")
        for doc_type, days, number, issuer in (
            ("VEHICLE_TAX", tax, f"TAX-{digits}-{2569 + i % 2}", "กรมการขนส่งทางบก"),
            ("COMPULSORY_INSURANCE", prb, f"CMI-{digits}-{100 + i}", INSURERS[i % 2]),
            ("VEHICLE_INSURANCE", ins, f"POL-V1-{digits}", INSURERS[(i + 1) % 2]),
        ):
            expiry = today + timedelta(days=days)
            db.add_document(owner_id=owner_id, doc_type=doc_type, doc_number=number,
                            holder_name=COMPANY_NAME, issue_date=expiry - timedelta(days=365),
                            expiry_date=expiry, issuing_authority=issuer,
                            raw_extraction={"engine": "seed"}, notes="ข้อมูลตัวอย่าง (สมมติ)")
            n += 1
    return n


if __name__ == "__main__":
    print(f"seeded {seed(reset=True)} documents")
