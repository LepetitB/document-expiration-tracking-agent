"""Flask web app: dashboard, upload, review, chat, alerts."""
from __future__ import annotations

import json
import re
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
    nav_owner_type = None
    if request.endpoint == "owner_detail" and request.view_args:
        o = db.get_owner(request.view_args.get("owner_id"))
        nav_owner_type = o["owner_type"] if o else None
    return {
        "DOC_TYPES": DOC_TYPES, "OWNER_TYPES": OWNER_TYPES, "STATUS_LABEL": STATUS_LABEL,
        "STATUS_ICON": STATUS_ICON, "doc_label": doc_label, "pending_count": pending,
        "ai_online": config.has_claude_credentials(), "model": config.CLAUDE_MODEL,
        "today": date.today(), "nav_owner_type": nav_owner_type,
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
                           vehicles=vehicles, vcount=vcount,
                           MAIN_DOC_TYPES=[*config.MAIN_DOC_TYPES, "DRIVER_LICENSE"],
                           SHORT_LABEL=config.SHORT_LABEL, q=q, f_status=f_status, f_type=f_type)


def vehicle_matrix(docs: list[dict]) -> list[dict]:
    """One row per vehicle: current tax / พ.ร.บ. / insurance + assigned driver's licence, and whether it may go out.

    * NO_DRIVE  – tax, พ.ร.บ. or the assigned driver's licence expired / missing (illegal to drive)
    * RISK      – insurance expired/missing, or something expires within its window
    * READY     – everything valid
    """
    def latest(target: dict, d: dict) -> None:
        cur = target.get(d["doc_type"])
        if not cur or (d.get("expiry_date") or "") > (cur.get("expiry_date") or ""):
            target[d["doc_type"]] = d

    # every registered vehicle gets a row — a new vehicle with no documents yet shows as "cannot go out"
    by_vehicle: dict[int, dict] = {
        o["id"]: {"owner_id": o["id"], "plate": o["name"], "driver_id": o.get("driver_id"), "docs": {}}
        for o in db.list_owners() if o["owner_type"] == "VEHICLE"}
    licences: dict[int, dict] = {}  # driver owner_id -> latest licence
    for d in docs:
        if d["status"] in ("PENDING_REVIEW", "RENEWED"):
            continue
        if d["owner_type"] == "DRIVER":
            cur = licences.get(d["owner_id"])
            if not cur or (d.get("expiry_date") or "") > (cur.get("expiry_date") or ""):
                licences[d["owner_id"]] = d
            continue
        v = by_vehicle.setdefault(d["owner_id"], {"owner_id": d["owner_id"], "plate": d["owner_name"],
                                                  "driver_id": d.get("driver_id"), "docs": {}})
        latest(v["docs"], d)
    rows = []
    for v in by_vehicle.values():
        driver = db.get_owner(v["driver_id"]) if v.get("driver_id") else None
        v["driver"] = driver
        lic = licences.get(driver["id"]) if driver else None
        if lic:
            v["docs"]["DRIVER_LICENSE"] = lic
        legal = [v["docs"].get(t) for t in ("VEHICLE_TAX", "COMPULSORY_INSURANCE")]
        if driver:
            legal.append(lic)
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
NEW_PLATE_PROBLEM = "ยังไม่มีในระบบ"


def _read_files(files, engine: str = "auto") -> tuple[list, list]:
    """Save uploaded files and let the AI (or the rules engine) read each one."""
    read, errors = [], []
    for f in files:
        if not f or not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            errors.append({"filename": f.filename, "error": f"ไม่รองรับไฟล์ {ext}"})
            continue
        stored = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename) or 'file' + ext}"
        path = config.UPLOAD_DIR / stored
        f.save(path)
        try:
            ex = extractor.extract(path, engine)
        except Exception as e:
            ex = extractor.normalise({"doc_type": "OTHER", "field_confidence": {},
                                      "notes": f"อ่านเอกสารไม่สำเร็จ: {e}", "engine": "error"})
        read.append((f.filename, stored, ex))
    return read, errors


def _drop_problem(ex: dict, marker: str) -> None:
    """Remove an expected problem (e.g. "unknown plate" for a new vehicle) and re-score."""
    if any(marker in p for p in ex["problems"]):
        ex["problems"] = [p for p in ex["problems"] if marker not in p]
        ex["confidence"] = validator.score(ex, ex["problems"])
        ex["needs_review"] = validator.needs_review(ex["confidence"], ex["problems"])


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Intake: attach a set of documents (e.g. everything that came with a new vehicle).

    The AI reads each file; documents are grouped by vehicle; a new plate becomes a new vehicle when the
    user ticked "this is a new vehicle"; a driver's licence in the same batch becomes that vehicle's driver.
    """
    if request.method == "GET":
        return redirect(url_for("vehicles"))
    engine = request.form.get("engine", "auto")
    is_new = request.form.get("new_vehicle") == "1"
    known_vehicles = {o["id"] for o in db.list_owners() if o["owner_type"] == "VEHICLE"}

    read, errors = _read_files(request.files.getlist("files"), engine)
    if not read and not errors:
        flash("กรุณาเลือกไฟล์อย่างน้อย 1 ไฟล์", "warn")
        return redirect(request.form.get("back") or url_for("vehicles"))

    # the user confirmed this batch is a new vehicle -> an unknown plate is expected, not an error
    if is_new:
        for _, _, ex in read:
            if ex.get("doc_type") != "DRIVER_LICENSE":
                _drop_problem(ex, NEW_PLATE_PROBLEM)

    # attached on a vehicle's own page -> the documents belong to that vehicle; a different plate is flagged
    target = db.get_owner(int(request.form["vehicle_id"])) if request.form.get("vehicle_id") else None
    saved = []  # (filename, doc_id, ex)
    for filename, stored, ex in read:
        owner_id = None
        if target and ex.get("doc_type") != "DRIVER_LICENSE":
            owner_id = target["id"]
            _drop_problem(ex, NEW_PLATE_PROBLEM)
            plate = re.sub(r"\s+", "", ex.get("vehicle_plate") or "")
            if plate and not plate.startswith(target["identifier"].replace(" ", "")):
                ex["problems"].append(f"ทะเบียนในเอกสาร \"{ex['vehicle_plate']}\" ไม่ตรงกับรถ {target['name']}")
                ex["confidence"] = validator.score(ex, ex["problems"])
                ex["needs_review"] = True
        saved.append((filename, _save_extraction(ex, stored, owner_id), ex))

    # group by vehicle
    batch_ids = {doc_id for _, doc_id, _ in saved}
    vehicle_ids, licence_owner_ids = [], []
    for _, doc_id, ex in saved:
        doc = db.get_document(doc_id)
        target = licence_owner_ids if doc["owner_type"] == "DRIVER" else vehicle_ids
        if doc["owner_id"] not in target:
            target.append(doc["owner_id"])
    # driver for the vehicle(s): chosen in the form, or a licence attached in the same batch
    chosen = request.form.get("driver_id")
    driver_id = int(chosen) if chosen else (licence_owner_ids[0] if len(licence_owner_ids) == 1 else None)
    if driver_id:
        for vid in vehicle_ids:
            if not db.get_owner(vid).get("driver_id") or chosen:
                db.assign_driver(vid, driver_id)

    all_docs = enrich(db.list_documents())
    matrix = {v["owner_id"]: v for v in vehicle_matrix(all_docs)}
    groups = []
    for vid in vehicle_ids:
        owner = db.get_owner(vid)
        docs = [d for d in all_docs if d["owner_id"] == vid]
        drv = db.get_owner(owner["driver_id"]) if owner.get("driver_id") else None
        if drv:
            docs += [d for d in all_docs if d["owner_id"] == drv["id"]]
        docs.sort(key=lambda d: d.get("expiry_date") or "9999")
        have = {d["doc_type"] for d in docs if d["status"] != "PENDING_REVIEW"}
        groups.append({
            "owner": owner, "is_new": vid not in known_vehicles, "driver": drv, "docs": docs,
            "readiness": matrix.get(vid, {}).get("readiness", "NO_DRIVE"),
            "missing": [t for t in [*config.MAIN_DOC_TYPES, *(["DRIVER_LICENSE"] if drv else [])] if t not in have],
            "pending_types": {d["doc_type"] for d in docs if d["status"] == "PENDING_REVIEW"},
            "pending": [d for d in docs if d["status"] == "PENDING_REVIEW"],
        })
    other = [(fn, did, ex) for fn, did, ex in saved
             if db.get_document(did)["owner_type"] == "DRIVER" and not vehicle_ids]
    return render_template("upload_result.html", groups=groups, saved=saved, errors=errors,
                           batch_ids=batch_ids, other=other)


def _owner_for(ex: dict, email: str | None = None) -> int:
    """Vehicle documents belong to a vehicle (plate); a driver's licence belongs to the driver (name)."""
    if ex.get("doc_type") == "DRIVER_LICENSE":
        name = (ex.get("holder_name") or "").strip() or "ไม่ระบุชื่อคนขับ"
        return db.upsert_owner("DRIVER", name, name, contact_email=email or None)
    plate = (ex.get("vehicle_plate") or "").strip() or "ไม่ระบุทะเบียน"
    return db.upsert_owner("VEHICLE", plate, plate, contact_email=email or None)


def _owner_from_form(ex: dict, form) -> int:
    owner_id = _owner_for(ex, form.get("owner_email"))
    if ex.get("doc_type") == "DRIVER_LICENSE":
        db.set_driver_contact(owner_id, form.get("driver_phone"), form.get("driver_line"))
    return owner_id


def _save_extraction(ex: dict, stored_file: str, owner_id: int | None = None) -> int:
    raw = {k: v for k, v in ex.items() if k not in ("issue_date", "expiry_date")}
    return db.add_document(
        owner_id=owner_id or _owner_for(ex), doc_type=ex.get("doc_type") or "OTHER",
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
            owner_id=_owner_from_form(ex, request.form), doc_type=ex["doc_type"],
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
            doc_id, owner_id=_owner_from_form(ex, request.form), doc_type=ex["doc_type"],
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


# --------------------------------------------------------------------------- vehicles & drivers
def _fleet_data():
    docs = enrich(db.list_documents())
    status_by_vehicle = {v["owner_id"]: v for v in vehicle_matrix(docs)}
    owners = db.list_owners()
    drivers = [o for o in owners if o["owner_type"] == "DRIVER"]
    licence = {}
    for d in docs:
        if d["doc_type"] == "DRIVER_LICENSE" and d["status"] not in ("PENDING_REVIEW", "RENEWED"):
            cur = licence.get(d["owner_id"])
            if not cur or (d.get("expiry_date") or "") > (cur.get("expiry_date") or ""):
                licence[d["owner_id"]] = d
    vehicles = []
    for o in owners:
        if o["owner_type"] != "VEHICLE":
            continue
        row = dict(o)
        v = status_by_vehicle.get(o["id"], {})
        row["readiness"] = v.get("readiness", "NO_DRIVE")
        row["vdocs"] = v.get("docs", {})
        vehicles.append(row)
    order = {"NO_DRIVE": 0, "RISK": 1, "READY": 2}
    vehicles.sort(key=lambda r: (order[r["readiness"]], r["name"]))
    for d in drivers:
        d["licence"] = licence.get(d["id"])
        d["vehicles"] = [v["name"] for v in vehicles if v.get("driver_id") == d["id"]]
    drivers.sort(key=lambda d: (d["licence"] or {}).get("expiry_date") or "0000")
    return vehicles, drivers


@app.route("/fleet")
def fleet():
    return redirect(url_for("vehicles"))


@app.route("/vehicles", methods=["GET", "POST"])
def vehicles():
    """Vehicles: add a vehicle by attaching its documents (the form posts to /upload), list, assign drivers."""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_vehicle":  # fallback: type the plate when there are no documents yet
            plate = re.sub(r"\s+", " ", request.form.get("plate", "")).strip()
            province = request.form.get("province", "").strip()
            if not validator.PLATE_RE.match(plate):
                flash(f"รูปแบบทะเบียนไม่ถูกต้อง: \"{plate}\" (ตัวอย่าง 70-1234)", "warn")
            else:
                ident = plate.split(" ")[0]
                vid = db.upsert_owner("VEHICLE", f"{ident} {province}".strip(), ident, responsible_person="ฝ่ายธุรการ")
                if request.form.get("driver_id"):
                    db.assign_driver(vid, int(request.form["driver_id"]))
                flash(f"เพิ่มรถ {ident} {province} แล้ว — แนบเอกสาร ภาษี / พ.ร.บ. / ประกัน ของคันนี้ได้เลย", "ok")
                return redirect(url_for("owner_detail", owner_id=vid))
        elif action == "assign":
            vid = int(request.form["vehicle_id"])
            did = request.form.get("driver_id")
            db.assign_driver(vid, int(did) if did else None)
            v = db.get_owner(vid)
            d = db.get_owner(int(did)) if did else None
            flash(f"รถ {v['name']}: คนขับประจำ = {d['name'] if d else 'ไม่มี'}", "ok")
        return redirect(request.form.get("back") or url_for("vehicles"))
    vehicle_rows, driver_rows = _fleet_data()
    return render_template("vehicles.html", vehicles=vehicle_rows, drivers=driver_rows,
                           MAIN_DOC_TYPES=[*config.MAIN_DOC_TYPES])


@app.route("/drivers", methods=["GET", "POST"])
def drivers():
    """Drivers: add a driver together with a photo of the licence (the AI reads name, number, expiry)."""
    if request.method == "POST":
        action = request.form.get("action", "add_driver")
        if action == "update_driver":
            db.set_driver_contact(int(request.form["driver_id"]), request.form.get("phone"),
                                  request.form.get("line_user_id"))
            flash("บันทึกข้อมูลติดต่อคนขับแล้ว", "ok")
            return redirect(request.form.get("back") or url_for("drivers"))

        existing_id = int(request.form["driver_id"]) if request.form.get("driver_id") else None
        typed = request.form.get("name", "").strip()
        read, errors = _read_files(request.files.getlist("files"), request.form.get("engine", "auto"))
        for e in errors:
            flash(f"❌ {e['filename']}: {e['error']}", "warn")
        licences = [r for r in read if r[2].get("doc_type") == "DRIVER_LICENSE"]
        for filename, _, ex in read:
            if ex.get("doc_type") != "DRIVER_LICENSE":
                flash(f"⚠️ {filename} ไม่ใช่ใบขับขี่ (AI อ่านได้เป็น {doc_label(ex.get('doc_type') or 'OTHER')}) "
                      "— เอกสารรถให้แนบที่หน้า \"รถ\"", "warn")
        if existing_id:
            did = existing_id
        else:
            name = typed or next((ex.get("holder_name") for _, _, ex in licences if ex.get("holder_name")), "")
            if not name:
                flash("กรุณาใส่ชื่อคนขับ หรือแนบรูปใบขับขี่ให้ AI อ่านชื่อ", "warn")
                return redirect(url_for("drivers"))
            did = db.upsert_owner("DRIVER", name, name, responsible_person="ฝ่ายธุรการ")
        db.set_driver_contact(did, request.form.get("phone"), request.form.get("line_user_id"))
        driver = db.get_owner(did)
        for _, stored, ex in licences:
            # the licence is attached to this driver; a new driver is expected to be unknown to the system
            _drop_problem(ex, "ในระบบ")
            read_name = (ex.get("holder_name") or "").replace(" ", "")
            if read_name and driver["name"].replace(" ", "") not in read_name:
                ex["problems"].append(f"ชื่อบนใบขับขี่ \"{ex['holder_name']}\" ไม่ตรงกับ \"{driver['name']}\"")
                ex["confidence"] = validator.score(ex, ex["problems"])
                ex["needs_review"] = True
            raw = {k: v for k, v in ex.items() if k not in ("issue_date", "expiry_date")}
            db.add_document(
                owner_id=did, doc_type="DRIVER_LICENSE", doc_number=ex.get("doc_number"),
                holder_name=ex.get("holder_name"), issue_date=ex.get("issue_date"),
                expiry_date=ex.get("expiry_date"), issuing_authority=ex.get("issuing_authority"),
                file_path=stored, raw_extraction=raw, confidence=ex.get("confidence", 0),
                review_status="PENDING_REVIEW" if ex.get("needs_review") else "CONFIRMED", notes=ex.get("notes"))
            exp = to_thai(ex["expiry_date"]) if ex.get("expiry_date") else "อ่านไม่ได้"
            state = "รอตรวจทาน 🟣" if ex.get("needs_review") else "บันทึกแล้ว ✅"
            flash(f"📄 AI อ่านใบขับขี่: {ex.get('holder_name') or '-'} · เลขที่ {ex.get('doc_number') or '-'} · "
                  f"หมดอายุ {exp} — {state}", "ok")
        if not existing_id:
            flash(f"เพิ่มคนขับ {driver['name']} แล้ว" + ("" if licences else " (ยังไม่มีใบขับขี่ — แนบได้ที่หน้านี้)"), "ok")
        return redirect(url_for("owner_detail", owner_id=did))
    _, driver_rows = _fleet_data()
    return render_template("drivers.html", drivers=driver_rows)


@app.route("/owners/<int:owner_id>")
def owner_detail(owner_id):
    owner = db.get_owner(owner_id)
    if not owner:
        abort(404)
    docs = enrich([d for d in db.list_documents(include_renewed=True) if d["owner_id"] == owner_id])
    driver = db.get_owner(owner["driver_id"]) if owner.get("driver_id") else None
    vehicles = db.vehicles_of_driver(owner_id) if owner["owner_type"] == "DRIVER" else []
    all_drivers = [o for o in db.list_owners() if o["owner_type"] == "DRIVER"]
    return render_template("owner.html", owner=owner, docs=docs, driver=driver, vehicles=vehicles,
                           all_drivers=all_drivers)


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
        thresholds=config.ALERT_THRESHOLDS, line_real=bool(config.LINE_CHANNEL_TOKEN),
        outbox=outbox.read_text(encoding="utf-8").splitlines()[-30:] if outbox.exists() else [],
        outbox_path=str(outbox),
    )


def create_app() -> Flask:
    db.init_db()
    if not db.list_owners():
        from app.seed import seed

        seed()
    return app
