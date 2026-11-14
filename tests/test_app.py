"""End-to-end tests of the web app with a temporary database (offline / rules engine)."""
import io
import os
import tempfile
from pathlib import Path

import pytest

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ.pop("ANTHROPIC_API_KEY", None)
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
    data = (SAMPLES / "01_driver_license_somchai.txt").read_bytes()
    r = client.post("/upload", data={"engine": "rules", "files": (io.BytesIO(data), "license.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert "2027-01-15" in r.get_data(as_text=True)
    pending = db.list_documents(review_status="PENDING_REVIEW")
    assert pending and pending[0]["expiry_date"] == "2027-01-15"

    # confirm via the review form
    doc = pending[0]
    r = client.post(f"/documents/{doc['id']}", data={
        "doc_type": "DRIVER_LICENSE", "holder_name": "นายสมชาย ใจดี", "doc_number": "64012345",
        "issue_date": "2022-01-15", "expiry_date": "2027-01-15"})
    assert r.status_code == 302
    assert db.get_document(doc["id"])["review_status"] == "CONFIRMED"


def test_renewal_supersedes_old_document(client):
    old = [d for d in db.list_documents() if d["doc_type"] == "DRIVER_LICENSE" and d["owner_identifier"] == "EMP003"][0]
    client.post("/documents/new", data={"doc_type": "DRIVER_LICENSE", "holder_name": old["owner_name"],
                                        "doc_number": "NEW-1", "issue_date": "2026-11-01", "expiry_date": "2031-11-01"})
    assert db.get_document(old["id"])["renewed"] == 1


def test_alerts_sent_once(client):
    first = run_expiry_check()
    assert first, "seed data contains expiring documents"
    assert run_expiry_check() == []


def test_chat_api_offline(client):
    r = client.post("/api/chat", json={"message": "30 วันข้างหน้ามีอะไรหมดบ้าง"})
    body = r.get_json()
    assert r.status_code == 200 and body["tools"] == ["list_expiring"]
    answer, _ = chat_offline("รถ 70-1234")
    assert "70-1234" in answer
