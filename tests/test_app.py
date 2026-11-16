"""End-to-end tests of the web app with a temporary database (offline / rules engine)."""
import io
import os
import tempfile
from pathlib import Path

import pytest

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["ANTHROPIC_API_KEY"] = ""  # empty (not unset) so load_dotenv() cannot fill it from .env
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

from app.agent.agent import chat_offline  # noqa: E402
from app.core.notifier import run_expiry_check  # noqa: E402
from app.db import database as db  # noqa: E402
from app.seed import seed  # noqa: E402
from app.web.server import create_app  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


@pytest.fixture()
def client():
    seed(reset=True)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_pages_render(client):
    for url in ["/", "/vehicles", "/drivers", "/review", "/documents/new", "/chat", "/alerts", "/?status=EXPIRED"]:
        r = client.get(url)
        assert r.status_code == 200, url


def test_upload_text_document(client):
    data = (SAMPLES / "05_insurance_70-1234.txt").read_bytes()
    r = client.post("/upload", data={"engine": "rules", "files": (io.BytesIO(data), "policy.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert "18 ก.พ. 2570" in r.get_data(as_text=True)
    pending = db.list_documents(review_status="PENDING_REVIEW")
    assert pending and pending[0]["expiry_date"] == "2027-02-18"
    assert pending[0]["owner_identifier"] == "70-1234"  # linked to the existing vehicle

    # confirm via the review form
    doc = pending[0]
    r = client.post(f"/documents/{doc['id']}", data={
        "doc_type": "VEHICLE_INSURANCE", "vehicle_plate": "70-1234 ชลบุรี", "doc_number": "POL-V1-554021",
        "issue_date": "2026-02-18", "expiry_date": "2027-02-18"})
    assert r.status_code == 302
    assert db.get_document(doc["id"])["review_status"] == "CONFIRMED"


def test_renewal_supersedes_old_document(client):
    old = [d for d in db.list_documents()
           if d["doc_type"] == "COMPULSORY_INSURANCE" and d["owner_identifier"] == "71-0099"][0]
    client.post("/documents/new", data={"doc_type": "COMPULSORY_INSURANCE", "vehicle_plate": "71-0099 ระยอง",
                                        "doc_number": "NEW-1", "issue_date": "2026-11-14", "expiry_date": "2027-11-14"})
    assert db.get_document(old["id"])["renewed"] == 1


def test_vehicle_matrix_readiness(client):
    from app.core.status import enrich
    from app.web.server import vehicle_matrix

    rows = {v["plate"]: v["readiness"] for v in vehicle_matrix(enrich(db.list_documents()))}
    assert rows["71-0099 ระยอง"] == "NO_DRIVE"   # พ.ร.บ. expired
    assert rows["70-8821 ชลบุรี"] == "NO_DRIVE"   # tax expired
    assert rows["72-0157 ฉะเชิงเทรา"] == "RISK"   # insurance expired
    assert rows["72-4410 ชลบุรี"] == "NO_DRIVE"   # assigned driver's licence expired
    assert rows["71-5530 ระยอง"] == "READY"


def test_driver_licence_upload_links_to_driver(client):
    data = (SAMPLES / "08_driver_license_surachai.txt").read_bytes()
    client.post("/upload", data={"engine": "rules", "files": (io.BytesIO(data), "licence.txt")},
                content_type="multipart/form-data")
    doc = db.list_documents(review_status="PENDING_REVIEW")[0]
    assert doc["doc_type"] == "DRIVER_LICENSE"
    assert doc["owner_type"] == "DRIVER" and doc["owner_name"] == "นายสุรชัย พึ่งบุญ"  # existing driver


def test_alerts_sent_once(client):
    first = run_expiry_check()
    assert first, "seed data contains expiring documents"
    assert run_expiry_check() == []


def test_line_alerts_reach_the_right_drivers(client):
    sent = run_expiry_check()
    to_driver = {c for s in sent for c in s["channels"] if c.startswith("LINE")}
    assert "LINE(จำลอง)→นายมานพ ศรีสุข" in to_driver        # own licence expired
    assert "LINE(จำลอง)→นายประสิทธิ์ แก้วกล้า" in to_driver  # drives 71-0099 whose พ.ร.บ. expired
    # 72-0157: only its insurance expired -> admin only, its driver is not messaged about the vehicle
    assert not any("72-0157" in s["message"] and "ถึงคนขับ" in s["message"] for s in sent)


def test_chat_api_offline(client):
    r = client.post("/api/chat", json={"message": "30 วันข้างหน้ามีอะไรหมดบ้าง"})
    body = r.get_json()
    assert r.status_code == 200 and body["tools"] == ["list_expiring"]
    answer, _ = chat_offline("รถ 70-1234")
    assert "70-1234" in answer
    answer, _ = chat_offline("รถคันไหนห้ามออกวิ่งบ้าง")
    assert "71-0099" in answer and "70-8821" in answer and "72-0157" not in answer
    assert "มานพ" in answer  # expired driver's licence also blocks a vehicle


def test_master_data_cross_check(client):
    from app.core import validator

    typo = validator.cross_check({"doc_type": "DRIVER_LICENSE", "holder_name": "นายสุรชัย พึงบุญ"})
    assert typo and "นายสุรชัย พึ่งบุญ" in typo[0]  # suggests the registered spelling
    assert validator.cross_check({"doc_type": "DRIVER_LICENSE",
                                  "holder_name": "Mr. Boonlert Jaingam / นายบุญเลิศ ใจงาม"}) == []
    assert validator.cross_check({"doc_type": "VEHICLE_TAX", "vehicle_plate": "70-1234 ชลบุรี"}) == []
    assert validator.cross_check({"doc_type": "VEHICLE_TAX", "vehicle_plate": "99-9999 ตาก"})


def test_fleet_add_vehicle_driver_and_assign(client):
    from app.core.status import enrich
    from app.web.server import vehicle_matrix

    assert client.get("/fleet").status_code == 302 and client.get("/upload").status_code == 302
    client.post("/vehicles", data={"action": "add_vehicle", "plate": "73-5555", "province": "ชลบุรี"})
    client.post("/drivers", data={"action": "add_driver", "name": "นายสมศักดิ์ ขยันดี",
                                  "phone": "081-000-0199", "line_user_id": "U-demo-somsak"})
    owners = {o["name"]: o for o in db.list_owners()}
    vid, did = owners["73-5555 ชลบุรี"]["id"], owners["นายสมศักดิ์ ขยันดี"]["id"]
    assert owners["นายสมศักดิ์ ขยันดี"]["phone"] == "081-000-0199"
    client.post("/vehicles", data={"action": "assign", "vehicle_id": vid, "driver_id": did})
    assert db.get_owner(vid)["driver_id"] == did

    # a new vehicle without documents is listed and cannot go out yet
    rows = {v["plate"]: v for v in vehicle_matrix(enrich(db.list_documents()))}
    assert rows["73-5555 ชลบุรี"]["readiness"] == "NO_DRIVE"
    # its documents attach to it by plate
    client.post("/documents/new", data={"doc_type": "VEHICLE_TAX", "vehicle_plate": "73-5555 ชลบุรี",
                                        "doc_number": "T1", "expiry_date": "2027-11-14"})
    assert any(d["owner_id"] == vid for d in db.list_documents())
    assert client.get(f"/owners/{vid}").status_code == 200
    assert client.get(f"/owners/{did}").status_code == 200

    bad = client.post("/vehicles", data={"action": "add_vehicle", "plate": "ABC", "province": ""}, follow_redirects=True)
    assert "รูปแบบทะเบียนไม่ถูกต้อง" in bad.get_data(as_text=True)


def test_new_vehicle_intake_creates_vehicle_and_summary(client):
    tax = ("เครื่องหมายแสดงการเสียภาษีรถ\nทะเบียน 73-5555 ชลบุรี\nเลขที่ 7355550\n"
           "วันครบกำหนดเสียภาษี / หมดอายุ 10/03/2570").encode("utf-8")
    prb = ("กรมธรรม์ประกันภัยคุ้มครองผู้ประสบภัยจากรถ (พ.ร.บ.)\nกรมธรรม์เลขที่ CMI-735555\n"
           "ทะเบียนรถ 73-5555 ชลบุรี\nระยะเวลาประกันภัย เริ่มต้น 10 มี.ค. 2569 สิ้นสุด 10 มี.ค. 2570").encode("utf-8")
    licence = (SAMPLES / "08_driver_license_surachai.txt").read_bytes()
    r = client.post("/upload", data={"engine": "rules", "new_vehicle": "1",
                                     "files": [(io.BytesIO(tax), "tax.txt"), (io.BytesIO(prb), "prb.txt"),
                                               (io.BytesIO(licence), "licence.txt")]},
                    content_type="multipart/form-data")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "73-5555 ชลบุรี" in html and "รถใหม่" in html
    assert "ยังไม่มีประกันภัยรถ" in html          # checklist shows the missing insurance
    assert "ควรเริ่มต่อ" in html
    vehicle = next(o for o in db.list_owners() if o["name"] == "73-5555 ชลบุรี")
    driver = next(o for o in db.list_owners() if o["name"] == "นายสุรชัย พึ่งบุญ")
    assert vehicle["driver_id"] == driver["id"]     # licence in the batch -> regular driver
    docs = [d for d in db.list_documents() if d["owner_id"] == vehicle["id"]]
    assert {d["doc_type"] for d in docs} == {"VEHICLE_TAX", "COMPULSORY_INSURANCE"}
    # "new vehicle" was ticked, so the unknown plate is not reported as a problem
    import json
    assert not any("ยังไม่มีในระบบ" in p for d in docs for p in json.loads(d["raw_extraction"])["problems"])



def test_add_driver_with_licence_photo(client):
    """New driver: no name typed -> the AI (rules engine here) reads it from the licence."""
    licence = ("ใบอนุญาตขับรถยนต์ ท.2\nฉบับที่ 65055501\nชื่อ นายสมศักดิ์ ขยันดี\n"
               "วันอนุญาต 1 มกราคม 2566\nวันสิ้นอายุ 1 มกราคม 2571").encode("utf-8")
    r = client.post("/drivers", data={"action": "add_driver", "engine": "rules", "phone": "081-000-0199",
                                      "files": (io.BytesIO(licence), "licence.txt")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    driver = next(o for o in db.list_owners() if o["name"] == "นายสมศักดิ์ ขยันดี")
    assert driver["owner_type"] == "DRIVER" and driver["phone"] == "081-000-0199"
    lic = [d for d in db.list_documents() if d["owner_id"] == driver["id"]]
    assert lic and lic[0]["doc_type"] == "DRIVER_LICENSE" and lic[0]["expiry_date"] == "2028-01-01"
    import json
    assert not any("ในระบบ" in p for p in json.loads(lic[0]["raw_extraction"])["problems"])


def test_attach_renewal_on_vehicle_page(client):
    vehicle = next(o for o in db.list_owners() if o["identifier"] == "71-0099")
    old = next(d for d in db.list_documents() if d["owner_id"] == vehicle["id"] and d["doc_type"] == "COMPULSORY_INSURANCE")
    prb = ("กรมธรรม์ประกันภัยคุ้มครองผู้ประสบภัยจากรถ (พ.ร.บ.)\nกรมธรรม์เลขที่ CMI-NEW-0099\n"
           "ทะเบียนรถ 71-0099 ระยอง\nระยะเวลาประกันภัย เริ่มต้น 14 พ.ย. 2569 สิ้นสุด 14 พ.ย. 2570").encode("utf-8")
    client.post("/upload", data={"engine": "rules", "vehicle_id": vehicle["id"],
                                 "files": (io.BytesIO(prb), "prb.txt")}, content_type="multipart/form-data")
    new = next(d for d in db.list_documents(include_renewed=True) if d.get("doc_number") == "CMI-NEW-0099")
    assert new["owner_id"] == vehicle["id"]
    # rules engine is never confident enough to auto-confirm; confirming it supersedes the old พ.ร.บ.
    client.post(f"/documents/{new['id']}", data={"doc_type": "COMPULSORY_INSURANCE", "vehicle_plate": "71-0099 ระยอง",
                                                 "doc_number": "CMI-NEW-0099", "expiry_date": "2027-11-14"})
    assert db.get_document(old["id"])["renewed"] == 1
