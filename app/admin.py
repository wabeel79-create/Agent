"""Administration Kapsi-Q : sauvegarde, restauration, informations.

  python -m app.admin sauvegarder            -> copie datée dans le dossier sauvegardes/
  python -m app.admin restaurer <fichier>    -> remplace la base (une copie de sécurité est faite avant)
  python -m app.admin liste                  -> liste les sauvegardes
  python -m app.admin info                   -> version, base, nombre de clients/audits/documents
"""
import datetime as dt
import shutil
import sqlite3
import sys
from pathlib import Path

from . import store

ROOT = Path(__file__).resolve().parent.parent
BACKUPS = ROOT / "sauvegardes"


def backup() -> Path:
    store.init()
    BACKUPS.mkdir(exist_ok=True)
    dest = BACKUPS / f"kapsi_q_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
    src = sqlite3.connect(store.DB_PATH)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)  # copie cohérente même si l'application tourne
    src.close(); dst.close()
    return dest


def restore(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Fichier introuvable : {p}")
    sqlite3.connect(p).execute("SELECT count(*) FROM clients").fetchone()  # vérifie que c'est une base Kapsi-Q
    safety = backup()
    shutil.copy2(p, store.DB_PATH)
    return safety


def info() -> dict:
    from .main import VERSION
    store.init()
    return {"version": VERSION, "base": str(store.DB_PATH), "clients": len(store.list_clients()),
            "audits": len(store.list_audits()), "documents": len(store.list_documents())}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    if cmd == "sauvegarder":
        print("Sauvegarde créée :", backup())
    elif cmd == "restaurer" and len(sys.argv) > 2:
        print("Base restaurée. Copie de sécurité de l'ancienne base :", restore(sys.argv[2]))
    elif cmd == "liste":
        for f in sorted(BACKUPS.glob("*.db")) if BACKUPS.exists() else []:
            print(f.name, f"{f.stat().st_size // 1024} Ko")
    else:
        for k, v in info().items():
            print(f"{k:10} {v}")
