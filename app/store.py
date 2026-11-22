"""Stockage local SQLite : clients du cabinet et documents générés. Aucune donnée ne quitte le serveur."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("KAPSI_DB", Path(__file__).parent.parent / "data" / "kapsi_iso.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, sector TEXT, size TEXT, activities TEXT, contact TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
  kind TEXT, title TEXT, body TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS gap_answers (
  client_id INTEGER, clause TEXT, status TEXT, note TEXT,
  PRIMARY KEY (client_id, clause));
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def list_clients() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clients ORDER BY id DESC")]


def get_client(cid: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None


def create_client(d: dict) -> dict:
    with conn() as c:
        cur = c.execute("INSERT INTO clients(name,sector,size,activities,contact) VALUES (?,?,?,?,?)",
                        (d["name"], d.get("sector"), d.get("size"), d.get("activities"), d.get("contact")))
        cid = cur.lastrowid
    return get_client(cid)


def delete_client(cid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM gap_answers WHERE client_id=?", (cid,))
        c.execute("DELETE FROM clients WHERE id=?", (cid,))


def save_document(cid: int, doc: dict) -> int:
    with conn() as c:
        return c.execute("INSERT INTO documents(client_id,kind,title,body) VALUES (?,?,?,?)",
                         (cid, doc["kind"], doc["title"], json.dumps(doc, ensure_ascii=False))).lastrowid


def list_documents(cid: int) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,kind,title,created_at FROM documents WHERE client_id=? ORDER BY id DESC", (cid,))]


def get_document(did: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT body FROM documents WHERE id=?", (did,)).fetchone()
        return json.loads(r["body"]) if r else None


def save_gap(cid: int, answers: dict) -> None:
    with conn() as c:
        for clause, a in answers.items():
            c.execute("INSERT OR REPLACE INTO gap_answers VALUES (?,?,?,?)",
                      (cid, clause, a.get("status", "NC"), a.get("note", "")))


def get_gap(cid: int) -> dict:
    with conn() as c:
        return {r["clause"]: {"status": r["status"], "note": r["note"]}
                for r in c.execute("SELECT * FROM gap_answers WHERE client_id=?", (cid,))}
