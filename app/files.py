"""Accès des agents aux fichiers du cabinet : dossiers locaux et Google Drive (dossier synchronisé).

Principe de sécurité :
  - les agents ne voient que les dossiers déclarés par l'administrateur (Réglages → Documents et Drive) ;
  - chaque dossier est en lecture seule, sauf s'il est explicitement autorisé en écriture ;
  - les agents n'écrivent que dans le sous-dossier « Kapsi-Q » d'un dossier autorisé en écriture
    (ou dans data/sorties par défaut), jamais ailleurs, et ne suppriment ni ne modifient aucun fichier existant.

Google Drive : installer « Google Drive pour ordinateur » ; le Drive apparaît comme un dossier
(par ex. G:\\Mon Drive) qu'il suffit d'ajouter ici.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from . import store

TEXT_EXT = {".txt", ".md", ".csv"}
OOXML_EXT = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/slides/"}
SUPPORTED = TEXT_EXT | set(OOXML_EXT) | {".pdf"}
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "appdata",
             "system volume information", "node_modules", ".git", ".venv", "__pycache__", "kapsi-q"}
MAX_BYTES = 25 * 1024 * 1024
MAX_TEXT = 40_000
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "sorties"

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, root TEXT, name TEXT, ext TEXT, size INTEGER,
  mtime REAL, text TEXT, indexed_at TEXT);
"""


def init() -> None:
    with store.conn() as c:
        c.executescript(SCHEMA)
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(path UNINDEXED, name, text, tokenize='unicode61 remove_diacritics 2')")
        except sqlite3.OperationalError:
            pass  # FTS5 indisponible : recherche par LIKE


def _fts(c) -> bool:
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE name='files_fts'").fetchone())


# ------------------------------------------------------------------ dossiers
def roots() -> list[dict]:
    raw = store.get_settings("files.").get("roots", "[]")
    out = []
    for r in json.loads(raw):
        p = Path(r["path"])
        out.append({**r, "exists": p.is_dir()})
    return out


def _save_roots(rs: list[dict]) -> None:
    store.set_settings({"roots": json.dumps([{k: r[k] for k in ("path", "label", "write")} for r in rs], ensure_ascii=False)}, "files.")


def add_root(path: str, label: str = "", write: bool = False) -> list[dict]:
    p = Path(path).expanduser()
    if not p.is_dir():
        raise ValueError(f"Dossier introuvable sur le poste Kapsi-Q : {path}")
    p = p.resolve()
    rs = [r for r in roots() if Path(r["path"]).resolve() != p]
    rs.append({"path": str(p), "label": label or p.name or str(p), "write": bool(write)})
    _save_roots(rs)
    return roots()


def remove_root(path: str) -> list[dict]:
    p = Path(path).resolve()
    _save_roots([r for r in roots() if Path(r["path"]).resolve() != p])
    with store.conn() as c:
        c.execute("DELETE FROM files WHERE root=?", (str(p),))
        if _fts(c):
            c.execute("DELETE FROM files_fts WHERE path LIKE ?", (str(p) + "%",))
    return roots()


def _inside_roots(path: Path) -> dict | None:
    rp = path.resolve()
    for r in roots():
        base = Path(r["path"]).resolve()
        if rp == base or base in rp.parents:
            return r
    return None


# ---------------------------------------------------------- extraction texte
def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return path.read_text(encoding="utf-8", errors="ignore")[:MAX_TEXT]
        if ext in OOXML_EXT:
            parts = []
            with zipfile.ZipFile(path) as z:
                prefix = OOXML_EXT[ext]
                names = [n for n in z.namelist() if n.startswith(prefix) and n.endswith(".xml")]
                if ext == ".xlsx":
                    names = [n for n in z.namelist() if n in ("xl/sharedStrings.xml",) or n.startswith("xl/worksheets/sheet")]
                for n in sorted(names):
                    xml = z.read(n).decode("utf-8", errors="ignore")
                    xml = re.sub(r"</w:p>|</a:p>|</row>", "\n", xml)
                    parts.append(re.sub(r"<[^>]+>", " ", xml))
                    if sum(map(len, parts)) > MAX_TEXT:
                        break
            txt = re.sub(r"[ \t\r\f\v]+", " ", " ".join(parts))
            return re.sub(r"\s*\n\s*", "\n", txt).strip()[:MAX_TEXT]
        if ext == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(str(path))
            out = []
            for page in r.pages[:40]:
                out.append(page.extract_text() or "")
                if sum(map(len, out)) > MAX_TEXT:
                    break
            return "\n".join(out)[:MAX_TEXT]
    except Exception:
        return ""
    return ""


def index_all(progress=None) -> dict:
    """(Ré)indexe tous les dossiers déclarés. Ne lit que les fichiers modifiés depuis le dernier passage."""
    init()
    seen = new = skipped = 0
    with store.conn() as c:
        fts = _fts(c)
        known = {r["path"]: r["mtime"] for r in c.execute("SELECT path, mtime FROM files")}
        alive = set()
        for r in roots():
            base = Path(r["path"])
            if not base.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
                for fn in filenames:
                    p = Path(dirpath) / fn
                    if p.suffix.lower() not in SUPPORTED or fn.startswith("~$"):
                        continue
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    sp = str(p)
                    alive.add(sp)
                    seen += 1
                    if st.st_size > MAX_BYTES:
                        skipped += 1
                        continue
                    if known.get(sp) == st.st_mtime:
                        continue
                    text = extract_text(p)
                    c.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?)",
                              (sp, str(base.resolve()), fn, p.suffix.lower(), st.st_size, st.st_mtime, text, datetime.now().isoformat(timespec="seconds")))
                    if fts:
                        c.execute("DELETE FROM files_fts WHERE path=?", (sp,))
                        c.execute("INSERT INTO files_fts(path,name,text) VALUES (?,?,?)", (sp, fn, text))
                    new += 1
                    if progress and new % 25 == 0:
                        progress(f"{new} fichiers lus…")
        gone = [p for p in known if p not in alive]
        for p in gone:
            c.execute("DELETE FROM files WHERE path=?", (p,))
            if fts:
                c.execute("DELETE FROM files_fts WHERE path=?", (p,))
    return {"fichiers": seen, "lus": new, "ignores_trop_gros": skipped, "retires": len(gone)}


def stats() -> dict:
    init()
    with store.conn() as c:
        n = c.execute("SELECT count(*), coalesce(sum(size),0), max(indexed_at) FROM files").fetchone()
        by = {r[0]: r[1] for r in c.execute("SELECT ext, count(*) FROM files GROUP BY ext")}
    return {"fichiers": n[0], "octets": n[1], "dernier_index": n[2], "par_type": by}


def _fts_query(q: str) -> str:
    words = [w for w in re.findall(r"\w{3,}", q.lower())][:8]
    return " OR ".join(f'"{w}"' for w in words)


def search(q: str, limit: int = 10, root: str | None = None) -> list[dict]:
    init()
    with store.conn() as c:
        if _fts(c) and _fts_query(q):
            sql = ("SELECT f.path, f.name, f.ext, f.mtime, snippet(files_fts, 2, '[', ']', '…', 14) AS extrait, bm25(files_fts) AS score "
                   "FROM files_fts JOIN files f ON f.path = files_fts.path WHERE files_fts MATCH ?" + (" AND f.root=?" if root else "") +
                   " ORDER BY score LIMIT ?")
            args = [_fts_query(q)] + ([root] if root else []) + [limit]
            try:
                return [dict(r) for r in c.execute(sql, args)]
            except sqlite3.OperationalError:
                pass
        like = f"%{q.lower()}%"
        return [dict(r) for r in c.execute("SELECT path, name, ext, mtime, substr(text,1,160) AS extrait, 0 AS score FROM files "
                                           "WHERE lower(name) LIKE ? OR lower(text) LIKE ? LIMIT ?", (like, like, limit))]


def read_file(path: str) -> str:
    """Lecture d'un fichier par un agent : uniquement à l'intérieur des dossiers autorisés."""
    p = Path(path)
    if not _inside_roots(p):
        raise PermissionError("Fichier hors des dossiers autorisés")
    return extract_text(p)


# ------------------------------------------------------------------- sorties
def _safe(name: str) -> str:
    return re.sub(r"[^\w\-. ]+", "_", name).strip()[:90] or "document"


def output_dir(client: str, standard: str = "") -> Path:
    w = next((r for r in roots() if r["write"] and r["exists"]), None)
    base = (Path(w["path"]) / "Kapsi-Q") if w else DEFAULT_OUT
    d = base / _safe(client) / _safe(standard or "General")
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_output(client: str, standard: str, filename: str, data: bytes) -> str:
    """Écrit un nouveau fichier (jamais d'écrasement) dans le dossier de sortie autorisé."""
    d = output_dir(client, standard)
    stem, ext = os.path.splitext(_safe(filename))
    p = d / f"{stem}{ext}"
    i = 2
    while p.exists():
        p = d / f"{stem} ({i}){ext}"
        i += 1
    p.write_bytes(data)
    return str(p)


def search_and(words: list[str], limit: int = 3) -> list[dict]:
    """Fichiers contenant TOUS les mots (nom ou contenu) — utilisé par les agents pour trouver des preuves."""
    init()
    words = [w for w in words if w][:5]
    if not words:
        return []
    with store.conn() as c:
        if _fts(c):
            try:
                q = " AND ".join(f'"{w}"' for w in words)
                return [dict(r) for r in c.execute("SELECT f.path, f.name FROM files_fts JOIN files f ON f.path = files_fts.path "
                                                   "WHERE files_fts MATCH ? ORDER BY bm25(files_fts) LIMIT ?", (q, limit))]
            except sqlite3.OperationalError:
                pass
        cond = " AND ".join("(lower(name) LIKE ? OR lower(text) LIKE ?)" for _ in words)
        args = [a for w in words for a in (f"%{w}%", f"%{w}%")]
        return [dict(r) for r in c.execute(f"SELECT path, name FROM files WHERE {cond} LIMIT ?", (*args, limit))]
