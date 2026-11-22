"""Stockage local SQLite. Aucune donnée ne quitte le serveur du cabinet."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("KAPSI_DB", Path(__file__).parent.parent / "data" / "kapsi_q.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sector TEXT,
  size TEXT, activities TEXT, contact TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS projects (client_id INTEGER, standard TEXT, progress TEXT DEFAULT '{}',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (client_id, standard));
CREATE TABLE IF NOT EXISTS gap (client_id INTEGER, standard TEXT, clause TEXT, status TEXT, note TEXT,
  PRIMARY KEY (client_id, standard, clause));
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, kind TEXT,
  standard TEXT, title TEXT, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audits (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, type TEXT,
  standards TEXT, date TEXT, lead_auditor TEXT, findings TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def _rows(sql, args=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args)]


def _one(sql, args=()):
    r = _rows(sql, args)
    return r[0] if r else None


def _exec(sql, args=()):
    with conn() as c:
        return c.execute(sql, args).lastrowid


# clients
def list_clients():
    return _rows("SELECT * FROM clients ORDER BY id DESC")


def get_client(cid):
    return _one("SELECT * FROM clients WHERE id=?", (cid,))


def create_client(d):
    cid = _exec("INSERT INTO clients(name,sector,size,activities,contact) VALUES (?,?,?,?,?)",
                (d["name"], d.get("sector"), d.get("size"), d.get("activities"), d.get("contact")))
    return get_client(cid)


def update_client(cid, d):
    _exec("UPDATE clients SET name=?,sector=?,size=?,activities=?,contact=? WHERE id=?",
          (d["name"], d.get("sector"), d.get("size"), d.get("activities"), d.get("contact"), cid))
    return get_client(cid)


def delete_client(cid):
    with conn() as c:
        for t in ("projects", "gap", "documents", "audits"):
            c.execute(f"DELETE FROM {t} WHERE client_id=?", (cid,))
        c.execute("DELETE FROM clients WHERE id=?", (cid,))


# projets de mise en place
def list_projects(cid=None):
    q = "SELECT * FROM projects" + (" WHERE client_id=?" if cid else "") + " ORDER BY rowid"
    rows = _rows(q, (cid,) if cid else ())
    for r in rows:
        r["progress"] = json.loads(r["progress"] or "{}")
    return rows


def add_project(cid, std):
    _exec("INSERT OR IGNORE INTO projects(client_id,standard) VALUES (?,?)", (cid, std))


def remove_project(cid, std):
    with conn() as c:
        c.execute("DELETE FROM projects WHERE client_id=? AND standard=?", (cid, std))
        c.execute("DELETE FROM gap WHERE client_id=? AND standard=?", (cid, std))


def set_progress(cid, std, progress):
    _exec("UPDATE projects SET progress=? WHERE client_id=? AND standard=?", (json.dumps(progress, ensure_ascii=False), cid, std))


# analyse d'écarts
def save_gap(cid, std, answers):
    with conn() as c:
        for clause, a in answers.items():
            c.execute("INSERT OR REPLACE INTO gap VALUES (?,?,?,?,?)", (cid, std, clause, a.get("status"), a.get("note", "")))


def get_gap(cid, std):
    return {r["clause"]: {"status": r["status"], "note": r["note"]}
            for r in _rows("SELECT * FROM gap WHERE client_id=? AND standard=?", (cid, std))}


# documents
def save_document(cid, doc):
    return _exec("INSERT INTO documents(client_id,kind,standard,title,body) VALUES (?,?,?,?,?)",
                 (cid, doc["kind"], doc.get("standard", ""), doc["title"], json.dumps(doc, ensure_ascii=False)))


def list_documents(cid=None):
    q = "SELECT id,client_id,kind,standard,title,created_at FROM documents" + (" WHERE client_id=?" if cid else "") + " ORDER BY id DESC"
    return _rows(q, (cid,) if cid else ())


def get_document(did):
    r = _one("SELECT body FROM documents WHERE id=?", (did,))
    return json.loads(r["body"]) if r else None


def delete_document(did):
    _exec("DELETE FROM documents WHERE id=?", (did,))


# audits tierce partie
def _audit(r):
    if r:
        r["standards"] = json.loads(r["standards"]); r["findings"] = json.loads(r["findings"] or "{}")
    return r


def create_audit(cid, d):
    aid = _exec("INSERT INTO audits(client_id,type,standards,date,lead_auditor) VALUES (?,?,?,?,?)",
                (cid, d["type"], json.dumps(d["standards"]), d.get("date", ""), d.get("lead_auditor", "")))
    return get_audit(aid)


def get_audit(aid):
    return _audit(_one("SELECT * FROM audits WHERE id=?", (aid,)))


def list_audits(cid=None):
    q = "SELECT * FROM audits" + (" WHERE client_id=?" if cid else "") + " ORDER BY id DESC"
    return [_audit(r) for r in _rows(q, (cid,) if cid else ())]


def save_findings(aid, findings):
    a = get_audit(aid)
    merged = {**a["findings"], **findings}
    merged = {k: v for k, v in merged.items() if v.get("grade")}
    _exec("UPDATE audits SET findings=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), aid))
    return get_audit(aid)


def delete_audit(aid):
    _exec("DELETE FROM audits WHERE id=?", (aid,))


# réglages
def get_settings(prefix="llm."):
    return {r["key"][len(prefix):]: r["value"] for r in _rows("SELECT * FROM settings WHERE key LIKE ?", (prefix + "%",))}


def set_settings(d, prefix="llm."):
    with conn() as c:
        for k, v in d.items():
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (prefix + k, v))
