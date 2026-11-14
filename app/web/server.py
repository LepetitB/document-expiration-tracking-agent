"""Flask web app: dashboard, upload, review, chat, alerts."""
from __future__ import annotations

import json
import uuid
from collections import Counter, OrderedDict
from datetime import date, timedelta
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.utils import secure_filename

from app import config
from app.agent import agent
from app.config import DOC_TYPES, OWNER_TYPES, doc_label
from app.core import notifier, validator
from app.core.status import STATUS_ICON, STATUS_LABEL, enrich
from app.db import database as db
from app.extraction import extractor
from app.extraction.thai_date import parse_date, to_thai

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}

app = Flask(__name__)
app.secret_key = "local-dev-only"  # sessions only hold a chat id; app runs on localhost
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


@app.template_filter("thai")
def _thai(v):
    if not v:
        return "-"
    return to_thai(v if isinstance(v, date) else date.fromisoformat(str(v)[:10]))


@app.context_processor
def _globals():
    pending = len(db.list_documents(review_status="PENDING_REVIEW"))
    return {
        "DOC_TYPES": DOC_TYPES, "OWNER_TYPES": OWNER_TYPES, "STATUS_LABEL": STATUS_LABEL,
        "STATUS_ICON": STATUS_ICON, "doc_label": doc_label, "pending_count": pending,
        "ai_online": config.has_claude_credentials(), "model": config.CLAUDE_MODEL,
        "today": date.today(),
    }


# --------------------------------------------------------------------------- dashboard
@app.route("/")
def dashboard():
    docs = enrich(db.list_documents())
    counts = Counter(d["status"] for d in docs)
    q = request.args.get("q", "").strip().lower()
    f_status = request.args.get("status", "")
    f_type = request.args.get("type", "")
    rows = [d for d in docs
            if (not q or q in " ".join(str(d.get(k) or "") for k in
                                       ("owner_name", "owner_identifier", "holder_name", "doc_number")).lower())
            and (not f_status or d["status"] == f_status)
            and (not f_type or d["doc_type"] == f_type)]

    # 12-month outlook: how many documents expire in each month
    months: OrderedDict[str, dict] = OrderedDict()
    start = date.today().replace(day=1)
    for i in range(12):
        y, m = start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1
        months[f"{y}-{m:02d}"] = {"label": to_thai(date(y, m, 1)).split(" ", 1)[1], "n": 0}
    for d in docs:
        if d.get("expiry_date") and d["status"] != "PENDING_REVIEW":
            key = d["expiry_date"][:7]
            if key in months:
                months[key]["n"] += 1
    peak = max([m["n"] for m in months.values()] + [1])
    urgent = [d for d in docs if d["status"] in ("EXPIRED", "EXPIRING")][:6]
    vehicles = vehicle_matrix(docs)
    vcount = Counter(v["readiness"] for v in vehicles)
    return render_template("dashboard.html", docs=rows, counts=counts, total=len(docs),
                           months=list(months.values()), peak=peak, urgent=urgent,
                           vehicles=vehicles, vcount=vcount, MAIN_DOC_TYPES=config.MAIN_DOC_TYPES,
                           SHORT_LABEL=config.SHORT_LABEL, q=q, f_status=f_status, f_type=f_type)


def vehicle_matrix(docs: list[dict]) -> list[dict]:
    """One row per vehicle: the current tax / พ.ร.บ. / insurance document and whether it may be driven.

    * NO_DRIVE  – tax or พ.ร.บ. expired (illegal to drive) or missing
    * RISK      – insurance expired/missing, or something expires within its window
    * READY     – everything valid
    """
    by_vehicle: dict[int, dict] = {}
    for d in docs:
        if d["status"] in ("PENDING_REVIEW", "RENEWED"):
            continue
        v = by_vehicle.setdefault(d["owner_id"], {"owner_id": d["owner_id"], "plate": d["owner_name"], "docs": {}})
        cur = v["docs"].get(d["doc_type"])
        if not cur or (d.get("expiry_date") or "") > (cur.get("expiry_date") or ""):
            v["docs"][d["doc_type"]] = d
    rows = []
    for v in by_vehicle.values():
        legal = [v["docs"].get(t) for t in ("VEHICLE_TAX", "COMPULSORY_INSURANCE")]
        ins = v["docs"].get("VEHICLE_INSURANCE")
        if any(x is None or x["status"] == "EXPIRED" for x in legal):
            v["readiness"] = "NO_DRIVE"
        elif ins is None or ins["status"] == "EXPIRED" or any(
                x["status"] == "EXPIRING" for x in v["docs"].values()):
            v["readiness"] = "RISK"
        else:
            v["readiness"] = "READY"
        lefts = [x["days_left"] for x in v["docs"].values() if x.get("days_left") is not None]
        v["min_left"] = min(lefts) if lefts else 9999
        rows.append(v)
    order = {"NO_DRIVE": 0, "RISK": 1, "READY": 2}
    return sorted(rows, key=lambda v: (order[v["readiness"]], v["min_left"]))


# --------------------------------------------------------------------------- upload
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")
    engine = request.form.get("engine", "auto")
    results = []
    for f in request.files.getlist("files"):
        if not f or not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            results.append({"filename": f.filename, "error": f"ไม่รองรับไฟล์ {ext}"})
            continue
        stored = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename) or 'file' + ext}"
        path = config.UPLOAD_DIR / stored
        f.save(path)
        try:
            ex = extractor.extract(path, engine)
        except Exception as e:
            ex = extractor.normalise({"doc_type": "OTHER", "field_confidence": {},
                                      "notes": f"อ่านเอกสารไม่สำเร็จ: {e}", "engine": "error"})
        doc_id = _save_extraction(ex, stored)
        results.append({"filename": f.filename, "id": doc_id, "ex": ex})
    if not results:
        flash("กรุณาเลือกไฟล์อย่างน้อย 1 ไฟล์", "warn")
        return redirect(url_for("upload"))
    return render_template("upload_result.html", results=results)


def _owner_for(ex: dict, email: str | None = None) -> int:
    """Every document belongs to a vehicle, identified by its plate."""
    plate = (ex.get("vehicle_plate") or "").strip() or "ไม่ระบุทะเบียน"
    return db.upsert_owner("VEHICLE", plate, plate, contact_email=email or None)


def _save_extraction(ex: dict, stored_file: str) -> int:
    raw = {k: v for k, v in ex.items() if k not in ("issue_date", "expiry_date")}
    return db.add_document(
        owner_id=_owner_for(ex), doc_type=ex.get("doc_type") or "OTHER",
        doc_number=ex.get("doc_number"), holder_name=ex.get("holder_name"),
        issue_date=ex.get("issue_date"), expiry_date=ex.get("expiry_date"),
        issuing_authority=ex.get("issuing_authority"), file_path=stored_file,
        raw_extraction=raw, confidence=ex.get("confidence", 0),
        review_status="PENDING_REVIEW" if ex.get("needs_review") else "CONFIRMED",
        notes=ex.get("notes"),
    )


@app.route("/files/<path:name>")
def files(name):
    return send_from_directory(config.UPLOAD_DIR, name)


# --------------------------------------------------------------------------- review / edit
@app.route("/review")
def review_queue():
    docs = enrich(db.list_documents(review_status="PENDING_REVIEW"))
    return render_template("review_queue.html", docs=docs)


@app.route("/documents/new", methods=["GET", "POST"])
def new_document():
    if request.method == "POST":
        ex = _form_to_extraction(request.form)
        doc_id = db.add_document(
            owner_id=_owner_for(ex, request.form.get("owner_email")), doc_type=ex["doc_type"],
            doc_number=ex["doc_number"], holder_name=ex["holder_name"],
            issue_date=ex["issue_date"], expiry_date=ex["expiry_date"],
            issuing_authority=ex["issuing_authority"], raw_extraction={"engine": "manual"},
            confidence=1.0, notes=request.form.get("notes"),
        )
        flash("บันทึกเอกสารเรียบร้อย", "ok")
        return redirect(url_for("document_detail", doc_id=doc_id))
    return render_template("document_form.html", doc=None, raw={}, problems=[])


def _form_to_extraction(form) -> dict:
    return {
        "doc_type": form.get("doc_type") or "OTHER",
        "doc_number": form.get("doc_number") or None,
        "holder_name": form.get("holder_name") or None,
        "vehicle_plate": form.get("vehicle_plate") or None,
        "issuing_authority": form.get("issuing_authority") or None,
        "issue_date": parse_date(form.get("issue_date")),
        "expiry_date": parse_date(form.get("expiry_date")),
    }


@app.route("/documents/<int:doc_id>", methods=["GET", "POST"])
def document_detail(doc_id):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            db.delete_document(doc_id)
            flash("ลบเอกสารแล้ว", "ok")
            return redirect(url_for("dashboard"))
        ex = _form_to_extraction(request.form)
        problems = validator.validate(ex)
        if not ex["expiry_date"]:
            flash("กรุณาระบุวันหมดอายุ", "warn")
            return redirect(url_for("document_detail", doc_id=doc_id))
        db.update_document(
            doc_id, owner_id=_owner_for(ex, request.form.get("owner_email")), doc_type=ex["doc_type"],
            doc_number=ex["doc_number"], holder_name=ex["holder_name"], issue_date=ex["issue_date"],
            expiry_date=ex["expiry_date"], issuing_authority=ex["issuing_authority"],
            review_status="CONFIRMED", confidence=1.0, notes=request.form.get("notes"),
        )
        flash("ยืนยันข้อมูลแล้ว" + (f" (ข้อสังเกต: {'; '.join(problems)})" if problems else ""), "ok")
        nxt = db.list_documents(review_status="PENDING_REVIEW")
        if request.form.get("next") == "review" and nxt:
            return redirect(url_for("document_detail", doc_id=nxt[0]["id"]))
        return redirect(url_for("dashboard"))
    doc = enrich([doc])[0]
    raw = json.loads(doc["raw_extraction"]) if doc.get("raw_extraction") else {}
    return render_template("document_form.html", doc=doc, raw=raw, problems=raw.get("problems", []))


# --------------------------------------------------------------------------- chat
@app.route("/chat")
def chat_page():
    if "cid" not in session:
        session["cid"] = agent.new_conversation()
    return render_template("chat.html")


@app.post("/api/chat")
def chat_api():
    text = (request.get_json(silent=True) or {}).get("message", "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400
    cid = session.get("cid") or agent.new_conversation()
    session["cid"] = cid
    return jsonify(agent.chat(cid, text))


@app.post("/api/chat/reset")
def chat_reset():
    session["cid"] = agent.new_conversation()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- alerts / settings
@app.route("/alerts", methods=["GET", "POST"])
def alerts():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "run":
            sent = notifier.run_expiry_check()
            flash(f"ตรวจเสร็จ — ส่งแจ้งเตือนใหม่ {len(sent)} รายการ" if sent
                  else "ตรวจเสร็จ — ไม่มีแจ้งเตือนใหม่ (ส่งครบทุกรอบแล้ว)", "ok")
        elif action == "test":
            ok = notifier.deliver("🔔 ทดสอบการแจ้งเตือนจาก Document Expiration Tracking Agent")
            flash(f"ส่งข้อความทดสอบผ่าน: {', '.join(ok) or 'ไม่สำเร็จ'}", "ok" if ok else "warn")
        elif action == "reset_demo":
            from app.seed import seed

            seed(reset=True)
            flash("รีเซ็ตข้อมูลตัวอย่างแล้ว", "ok")
        return redirect(url_for("alerts"))
    outbox = config.OUTBOX_DIR / f"{date.today().isoformat()}.log"
    return render_template(
        "alerts.html", log=db.list_notifications(), channels=notifier.active_channels(),
        thresholds=config.ALERT_THRESHOLDS,
        outbox=outbox.read_text(encoding="utf-8").splitlines()[-30:] if outbox.exists() else [],
        outbox_path=str(outbox),
    )


def create_app() -> Flask:
    db.init_db()
    if not db.list_owners():
        from app.seed import seed

        seed()
    return app
