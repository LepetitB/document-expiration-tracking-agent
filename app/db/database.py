"""SQLite storage for owners, documents and notification log."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS owners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type TEXT NOT NULL,
    name TEXT NOT NULL,
    identifier TEXT,
    contact_email TEXT,
    responsible_person TEXT,
    UNIQUE(owner_type, identifier)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER REFERENCES owners(id),
    doc_type TEXT NOT NULL,
    doc_number TEXT,
    holder_name TEXT,
    issue_date TEXT,
    expiry_date TEXT,
    issuing_authority TEXT,
    file_path TEXT,
    raw_extraction TEXT,
    confidence REAL DEFAULT 1.0,
    review_status TEXT DEFAULT 'CONFIRMED',
    renewed INTEGER DEFAULT 0,
    replaced_by INTEGER,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id),
    threshold_days INTEGER,
    channel TEXT,
    message TEXT,
    sent_at TEXT,
    UNIQUE(document_id, threshold_days)
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(owners)")}
        for col, typ in (("phone", "TEXT"), ("line_user_id", "TEXT"), ("driver_id", "INTEGER")):
            if col not in cols:  # migrate databases created before drivers existed
                c.execute(f"ALTER TABLE owners ADD COLUMN {col} {typ}")


def set_driver_contact(driver_id: int, phone: str | None = None, line_user_id: str | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE owners SET phone=COALESCE(?, phone), line_user_id=COALESCE(?, line_user_id) WHERE id=?",
                  (phone or None, line_user_id or None, driver_id))


def assign_driver(vehicle_id: int, driver_id: int | None) -> None:
    with connect() as c:
        c.execute("UPDATE owners SET driver_id=? WHERE id=?", (driver_id, vehicle_id))


def get_owner(owner_id: int) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()
        return dict(r) if r else None


def vehicles_of_driver(driver_id: int) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM owners WHERE driver_id=?", (driver_id,))]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _iso(d: date | str | None) -> str | None:
    if d is None or d == "":
        return None
    return d.isoformat() if isinstance(d, date) else str(d)


# --- owners ----------------------------------------------------------------
def upsert_owner(owner_type: str, name: str, identifier: str | None = None,
                 contact_email: str | None = None, responsible_person: str | None = None) -> int:
    identifier = (identifier or name).strip()
    with connect() as c:
        row = c.execute(
            "SELECT id FROM owners WHERE owner_type=? AND identifier=?", (owner_type, identifier)
        ).fetchone()
        if not row:  # same person/vehicle already registered under another identifier (e.g. EMP003)
            row = c.execute(
                "SELECT id FROM owners WHERE owner_type=? AND (name=? OR ? LIKE identifier || '%')",
                (owner_type, name.strip(), identifier),
            ).fetchone()
            if row:
                c.execute("UPDATE owners SET contact_email=COALESCE(?, contact_email) WHERE id=?",
                          (contact_email, row["id"]))
                return row["id"]
        if row:
            c.execute(
                "UPDATE owners SET name=?, contact_email=COALESCE(?, contact_email), "
                "responsible_person=COALESCE(?, responsible_person) WHERE id=?",
                (name, contact_email, responsible_person, row["id"]),
            )
            return row["id"]
        cur = c.execute(
            "INSERT INTO owners(owner_type, name, identifier, contact_email, responsible_person) "
            "VALUES (?,?,?,?,?)",
            (owner_type, name, identifier, contact_email, responsible_person),
        )
        return cur.lastrowid


def list_owners() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM owners ORDER BY owner_type, name")]


# --- documents -------------------------------------------------------------
def add_document(*, owner_id: int, doc_type: str, doc_number: str | None, holder_name: str | None,
                 issue_date: Any, expiry_date: Any, issuing_authority: str | None = None,
                 file_path: str | None = None, raw_extraction: dict | None = None,
                 confidence: float = 1.0, review_status: str = "CONFIRMED",
                 notes: str | None = None) -> int:
    now = _now()
    with connect() as c:
        cur = c.execute(
            """INSERT INTO documents(owner_id, doc_type, doc_number, holder_name, issue_date,
               expiry_date, issuing_authority, file_path, raw_extraction, confidence,
               review_status, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (owner_id, doc_type, doc_number, holder_name, _iso(issue_date), _iso(expiry_date),
             issuing_authority, file_path,
             json.dumps(raw_extraction, ensure_ascii=False) if raw_extraction else None,
             confidence, review_status, notes, now, now),
        )
        new_id = cur.lastrowid
        if review_status == "CONFIRMED":
            _mark_previous_renewed(c, new_id)
        return new_id


def _mark_previous_renewed(c: sqlite3.Connection, new_id: int) -> None:
    """A newer confirmed document of the same type for the same owner supersedes older ones."""
    new = c.execute("SELECT * FROM documents WHERE id=?", (new_id,)).fetchone()
    if not new or not new["expiry_date"]:
        return
    c.execute(
        """UPDATE documents SET renewed=1, replaced_by=?, updated_at=?
           WHERE owner_id=? AND doc_type=? AND id<>? AND renewed=0
             AND review_status='CONFIRMED' AND expiry_date < ?""",
        (new_id, _now(), new["owner_id"], new["doc_type"], new_id, new["expiry_date"]),
    )


def update_document(doc_id: int, **fields: Any) -> None:
    allowed = {"owner_id", "doc_type", "doc_number", "holder_name", "issue_date", "expiry_date",
               "issuing_authority", "confidence", "review_status", "notes"}
    sets = {k: (_iso(v) if k.endswith("_date") else v) for k, v in fields.items() if k in allowed}
    if not sets:
        return
    sets["updated_at"] = _now()
    with connect() as c:
        c.execute(
            f"UPDATE documents SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?",
            (*sets.values(), doc_id),
        )
        if sets.get("review_status") == "CONFIRMED":
            _mark_previous_renewed(c, doc_id)


def delete_document(doc_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM notifications WHERE document_id=?", (doc_id,))
        c.execute("UPDATE documents SET replaced_by=NULL WHERE replaced_by=?", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))


def get_document(doc_id: int) -> dict | None:
    with connect() as c:
        r = c.execute(_DOC_SELECT + " WHERE d.id=?", (doc_id,)).fetchone()
        return dict(r) if r else None


_DOC_SELECT = """
SELECT d.*, o.name AS owner_name, o.owner_type, o.identifier AS owner_identifier,
       o.contact_email AS owner_email, o.responsible_person, o.phone AS owner_phone,
       o.line_user_id AS owner_line, o.driver_id
FROM documents d LEFT JOIN owners o ON o.id = d.owner_id
"""


def list_documents(include_renewed: bool = False, review_status: str | None = None) -> list[dict]:
    q, args = _DOC_SELECT + " WHERE 1=1", []
    if not include_renewed:
        q += " AND d.renewed=0"
    if review_status:
        q += " AND d.review_status=?"
        args.append(review_status)
    q += " ORDER BY d.expiry_date IS NULL, d.expiry_date"
    with connect() as c:
        return [dict(r) for r in c.execute(q, args)]


# --- notifications ---------------------------------------------------------
def notification_sent(doc_id: int, threshold: int) -> bool:
    with connect() as c:
        return c.execute(
            "SELECT 1 FROM notifications WHERE document_id=? AND threshold_days=?", (doc_id, threshold)
        ).fetchone() is not None


def log_notification(doc_id: int, threshold: int, channel: str, message: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO notifications(document_id, threshold_days, channel, message, sent_at) "
            "VALUES (?,?,?,?,?)",
            (doc_id, threshold, channel, message, _now()),
        )


def list_notifications(limit: int = 100) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT n.*, d.doc_type, d.holder_name, d.expiry_date, o.name AS owner_name
               FROM notifications n JOIN documents d ON d.id=n.document_id
               LEFT JOIN owners o ON o.id=d.owner_id
               ORDER BY n.sent_at DESC, n.id DESC LIMIT ?""", (limit,))]


def reset_all() -> None:
    with connect() as c:
        c.executescript("DROP TABLE IF EXISTS notifications; DROP TABLE IF EXISTS documents; "
                        "DROP TABLE IF EXISTS owners;")
    init_db()
