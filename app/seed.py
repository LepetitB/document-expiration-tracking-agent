"""Synthetic demo data (fictional people, plates and numbers) relative to today's date."""
from __future__ import annotations

from datetime import date, timedelta

from app.db import database as db

# (doc_type, owner_type, owner_name, identifier, doc_number, days_until_expiry, validity_years)
DEMO = [
    ("DRIVER_LICENSE", "EMPLOYEE", "นายสมชาย ใจดี", "EMP001", "ท.2-64012345", 18, 3),
    ("DRIVER_LICENSE", "EMPLOYEE", "นายวีระ ทองมาก", "EMP002", "ท.2-63098712", 240, 5),
    ("DRIVER_LICENSE", "EMPLOYEE", "นายประสิทธิ์ แก้วกล้า", "EMP003", "ท.3-62055501", -6, 5),
    ("WORK_PERMIT", "EMPLOYEE", "Mr. Aung Ko Ko", "EMP014", "WP-0067-889201", 45, 2),
    ("WORK_PERMIT", "EMPLOYEE", "Mr. Sok Dara", "EMP015", "WP-0067-889377", 150, 2),
    ("VISA", "EMPLOYEE", "Mr. Aung Ko Ko", "EMP014", "NON-LA-772031", 52, 1),
    ("VEHICLE_TAX", "VEHICLE", "70-1234 ชลบุรี", "70-1234", "TAX-2569-001234", 12, 1),
    ("COMPULSORY_INSURANCE", "VEHICLE", "70-1234 ชลบุรี", "70-1234", "CMI-25690331-77", 12, 1),
    ("VEHICLE_INSURANCE", "VEHICLE", "70-1234 ชลบุรี", "70-1234", "POL-V1-554021", 95, 1),
    ("VEHICLE_TAX", "VEHICLE", "70-5678 ชลบุรี", "70-5678", "TAX-2569-005678", 33, 1),
    ("COMPULSORY_INSURANCE", "VEHICLE", "70-5678 ชลบุรี", "70-5678", "CMI-25690412-03", 33, 1),
    ("COMPULSORY_INSURANCE", "VEHICLE", "71-0099 ระยอง", "71-0099", "CMI-25681201-55", -3, 1),
    ("VEHICLE_TAX", "VEHICLE", "71-0099 ระยอง", "71-0099", "TAX-2569-710099", 200, 1),
    ("VEHICLE_INSURANCE", "VEHICLE", "71-0099 ระยอง", "71-0099", "POL-V1-554388", 3, 1),
    ("TRANSPORT_LICENSE", "COMPANY", "บริษัท สยามฟลีท ทรานสปอร์ต จำกัด", "0105556001234", "ขส.บ.(ม) 20-0451", 80, 7),
    ("CONTRACT", "CUSTOMER", "บริษัท ไทยรีเทล ซัพพลาย จำกัด", "CUST-01", "CT-2025-0107", 58, 2),
    ("CONTRACT", "CUSTOMER", "บริษัท อีสเทิร์น ฟู้ดส์ จำกัด", "CUST-02", "CT-2025-0213", 310, 2),
]


def seed(reset: bool = False) -> int:
    if reset:
        db.reset_all()
    else:
        db.init_db()
    today = date.today()
    n = 0
    for doc_type, otype, name, ident, number, days, years in DEMO:
        owner_id = db.upsert_owner(otype, name, ident, responsible_person="ฝ่ายธุรการ")
        expiry = today + timedelta(days=days)
        issue = expiry - timedelta(days=365 * years)
        db.add_document(owner_id=owner_id, doc_type=doc_type, doc_number=number,
                        holder_name=name if otype != "VEHICLE" else "บริษัท สยามฟลีท ทรานสปอร์ต จำกัด",
                        issue_date=issue, expiry_date=expiry, raw_extraction={"engine": "seed"},
                        notes="ข้อมูลตัวอย่าง (สมมติ)")
        n += 1
    return n


if __name__ == "__main__":
    print(f"seeded {seed(reset=True)} documents")
