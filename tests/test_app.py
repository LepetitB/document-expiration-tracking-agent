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
    for url in ["/", "/upload", "/review", "/documents/new", "/chat", "/alerts", "/?status=EXPIRED"]:
        r = client.get(url)
        assert r.status_code == 200, url


def test_upload_text_document(client):
    data = (SAMPLES / "05_insurance_70-1234.txt").read_bytes()
    r = client.post("/upload", data={"engine": "rules", "files": (io.BytesIO(data), "policy.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert "2027-02-18" in r.get_data(as_text=True)
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
