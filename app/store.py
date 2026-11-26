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
CREATE TABLE IF NOT EXISTS agent_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, agent TEXT, standard TEXT,
  status TEXT, log TEXT DEFAULT '[]', outputs TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT);
CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, standard TEXT, source TEXT,
  clause TEXT, finding TEXT, cause TEXT, action TEXT, owner TEXT, due TEXT, status TEXT DEFAULT 'Ouverte',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS trainings (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, standard TEXT, module TEXT,
  audience TEXT, duration TEXT, planned TEXT, status TEXT DEFAULT 'Planifiée', document_id INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

MIGRATIONS = [("documents", "status", "TEXT DEFAULT 'À valider'"), ("documents", "validated_by", "TEXT"),
              ("documents", "validated_at", "TEXT"), ("documents", "path", "TEXT"), ("documents", "agent", "TEXT")]


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
        for table, col, decl in MIGRATIONS:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


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
        for t in ("projects", "gap", "documents", "audits", "agent_runs", "actions", "trainings"):
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
def save_document(cid, doc, agent=None, path=None):
    return _exec("INSERT INTO documents(client_id,kind,standard,title,body,agent,path) VALUES (?,?,?,?,?,?,?)",
                 (cid, doc["kind"], doc.get("standard", ""), doc["title"], json.dumps(doc, ensure_ascii=False), agent, path))


def validate_document(did, by):
    _exec("UPDATE documents SET status='Validé', validated_by=?, validated_at=datetime('now','localtime') WHERE id=?", (by, did))


def list_documents(cid=None):
    q = "SELECT id,client_id,kind,standard,title,created_at,status,validated_by,validated_at,path,agent FROM documents" + (" WHERE client_id=?" if cid else "") + " ORDER BY id DESC"
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


# exécutions d'agents
def create_run(cid, agent, standard):
    return _exec("INSERT INTO agent_runs(client_id,agent,standard,status,created_at) VALUES (?,?,?,'En cours',datetime('now','localtime'))", (cid, agent, standard))


def update_run(rid, log=None, outputs=None, status=None):
    with conn() as c:
        if log is not None:
            c.execute("UPDATE agent_runs SET log=? WHERE id=?", (json.dumps(log, ensure_ascii=False), rid))
        if outputs is not None:
            c.execute("UPDATE agent_runs SET outputs=? WHERE id=?", (json.dumps(outputs, ensure_ascii=False), rid))
        if status is not None:
            c.execute("UPDATE agent_runs SET status=?, finished_at=CASE WHEN ? IN ('Terminé','Échec') THEN datetime('now','localtime') ELSE finished_at END WHERE id=?", (status, status, rid))


def get_run(rid):
    r = _one("SELECT * FROM agent_runs WHERE id=?", (rid,))
    if r:
        r["log"] = json.loads(r["log"] or "[]"); r["outputs"] = json.loads(r["outputs"] or "{}")
    return r


def list_runs(cid=None, limit=50):
    q = "SELECT id,client_id,agent,standard,status,created_at,finished_at FROM agent_runs" + (" WHERE client_id=?" if cid else "") + " ORDER BY id DESC LIMIT ?"
    return _rows(q, ((cid, limit) if cid else (limit,)))


# actions correctives (CAPA)
ACTION_FIELDS = ("standard", "source", "clause", "finding", "cause", "action", "owner", "due", "status")


def add_action(cid, d):
    return _exec("INSERT INTO actions(client_id,standard,source,clause,finding,cause,action,owner,due,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (cid, *[d.get(k, "Ouverte" if k == "status" else "") for k in ACTION_FIELDS]))


def update_action(aid, d):
    sets = [k for k in ACTION_FIELDS if k in d]
    if sets:
        _exec(f"UPDATE actions SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*[d[k] for k in sets], aid))
    return _one("SELECT * FROM actions WHERE id=?", (aid,))


def list_actions(cid=None, standard=None):
    q, a = "SELECT * FROM actions WHERE 1=1", []
    if cid:
        q += " AND client_id=?"; a.append(cid)
    if standard:
        q += " AND standard=?"; a.append(standard)
    return _rows(q + " ORDER BY CASE status WHEN 'Ouverte' THEN 0 WHEN 'En cours' THEN 1 ELSE 2 END, due", a)


# formations
def add_training(cid, d):
    return _exec("INSERT INTO trainings(client_id,standard,module,audience,duration,planned,status,document_id) VALUES (?,?,?,?,?,?,?,?)",
                 (cid, d.get("standard"), d.get("module"), d.get("audience"), d.get("duration"), d.get("planned"), d.get("status", "Planifiée"), d.get("document_id")))


def update_training(tid, status):
    _exec("UPDATE trainings SET status=? WHERE id=?", (status, tid))


def list_trainings(cid=None):
    q = "SELECT * FROM trainings" + (" WHERE client_id=?" if cid else "") + " ORDER BY planned"
    return _rows(q, (cid,) if cid else ())


def get_setting(key):
    r = _one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else None


def set_setting(key, value):
    _exec("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
