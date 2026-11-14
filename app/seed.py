"""Synthetic demo fleet: vehicles, their drivers and documents (all fictional), dated relative to today."""
from __future__ import annotations

from datetime import date, timedelta

from app.config import COMPANY_NAME
from app.db import database as db

# plate, province, days until expiry for (tax, พ.ร.บ., insurance), assigned driver index (None = no regular driver)
FLEET = [
    ("70-1234", "ชลบุรี", 12, 12, 95, 0),
    ("70-5678", "ชลบุรี", 33, 33, 140, 1),
    ("71-0099", "ระยอง", 200, -3, 3, 2),
    ("72-4410", "ชลบุรี", 250, 250, 250, 3),
    ("70-8821", "ชลบุรี", -20, 340, 340, 4),
    ("71-3307", "ระยอง", 45, 45, 45, 5),
    ("70-2299", "ชลบุรี", 25, 25, 180, 6),
    ("72-0157", "ฉะเชิงเทรา", 60, 60, -15, 7),
    ("71-5530", "ระยอง", 300, 300, 300, 8),
    ("70-6612", "ชลบุรี", 7, 7, 7, 9),
    ("72-9045", "ฉะเชิงเทรา", 150, 150, 20, 10),
    ("70-3388", "ชลบุรี", 90, 90, 210, None),
]
# name, fake phone, fake LINE userId, days until licence expiry
DRIVERS = [
    ("นายสมชาย ใจดี", "081-000-0101", "U-demo-somchai", 400),
    ("นายวีระ ทองมาก", "081-000-0102", "U-demo-weera", 900),
    ("นายประสิทธิ์ แก้วกล้า", "081-000-0103", "U-demo-prasit", 600),
    ("นายมานพ ศรีสุข", "081-000-0104", "U-demo-manop", -5),      # licence expired -> 72-4410 cannot go out
    ("นายเกรียงไกร บุญมา", "081-000-0105", "U-demo-kriangkrai", 700),
    ("นายสุรชัย พึ่งบุญ", "081-000-0106", "U-demo-surachai", 18),  # licence expiring soon
    ("นายอนุชา คงดี", "081-000-0107", "U-demo-anucha", 1200),
    ("นายธนพล มีสุข", "081-000-0108", "U-demo-thanaphon", 85),
    ("นายวิชัย รุ่งเรือง", "081-000-0109", "U-demo-wichai", 1500),
    ("นายบุญเลิศ ใจงาม", "081-000-0110", "U-demo-boonlert", 6),     # licence expiring this week
    ("นายพงศกร แสงทอง", "081-000-0111", "U-demo-pongsakorn", 320),
]
INSURERS = ["บริษัท ไทยประกันภัยตัวอย่าง จำกัด", "บริษัท สยามประกันภัยสมมติ จำกัด"]


def seed(reset: bool = False) -> int:
    if reset:
        db.reset_all()
    else:
        db.init_db()
    today = date.today()
    n = 0
    driver_ids = []
    for i, (name, phone, line_id, days) in enumerate(DRIVERS):
        did = db.upsert_owner("DRIVER", name, name, responsible_person="ฝ่ายธุรการ")
        db.set_driver_contact(did, phone, line_id)
        driver_ids.append(did)
        expiry = today + timedelta(days=days)
        db.add_document(owner_id=did, doc_type="DRIVER_LICENSE", doc_number=f"6{4000000 + i * 1371}",
                        holder_name=name, issue_date=expiry - timedelta(days=365 * 5), expiry_date=expiry,
                        issuing_authority="กรมการขนส่งทางบก", raw_extraction={"engine": "seed"},
                        notes="ข้อมูลตัวอย่าง (สมมติ) ใบขับขี่ประเภท 2 (ท.2)")
        n += 1
    for i, (plate, province, tax, prb, ins, driver) in enumerate(FLEET):
        owner_id = db.upsert_owner("VEHICLE", f"{plate} {province}", plate, responsible_person="ฝ่ายธุรการ")
        db.assign_driver(owner_id, driver_ids[driver] if driver is not None else None)
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
