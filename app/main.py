"""API Kapsi ISO — SmartCell Technologies.

Lancement : uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine, export, store

VERSION = "0.1.0"
STATIC = Path(__file__).parent / "static"
TOKEN = os.getenv("KAPSI_TOKEN", "")  # si défini, exigé dans l'en-tête X-Kapsi-Token

app = FastAPI(title="Kapsi ISO", version=VERSION, docs_url="/api/docs")
store.init()


def auth(request: Request) -> None:
    if TOKEN and not secrets.compare_digest(request.headers.get("X-Kapsi-Token", ""), TOKEN):
        raise HTTPException(401, "Jeton d'accès invalide")


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str = ""
    size: str = ""
    activities: str = ""
    contact: str = ""


class GenerateIn(BaseModel):
    kind: str
    clauses: list[str] | None = None
    standards: list[str] | None = None


class GapIn(BaseModel):
    answers: dict[str, dict]


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


def _client(cid: int) -> dict:
    c = store.get_client(cid)
    if not c:
        raise HTTPException(404, "Client introuvable")
    return c


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "ai_backend": engine.llm.backend,
            "offline": True, "auth": bool(TOKEN)}


@app.get("/api/catalog", dependencies=[Depends(auth)])
def catalog():
    return {"generators": [{"kind": k, "label": v[0]} for k, v in engine.GENERATORS.items()],
            "clauses": [{"id": c["id"], "title": c["title"]} for c in engine.ISO9001],
            "standards": engine.INTEGRATED["standards"]}


@app.get("/api/clients", dependencies=[Depends(auth)])
def clients():
    return store.list_clients()


@app.post("/api/clients", dependencies=[Depends(auth)])
def create_client(c: ClientIn):
    return store.create_client(c.model_dump())


@app.delete("/api/clients/{cid}", dependencies=[Depends(auth)])
def delete_client(cid: int):
    _client(cid)
    store.delete_client(cid)
    return {"deleted": cid}


@app.get("/api/clients/{cid}/documents", dependencies=[Depends(auth)])
def documents(cid: int):
    _client(cid)
    return store.list_documents(cid)


@app.post("/api/clients/{cid}/generate", dependencies=[Depends(auth)])
def generate(cid: int, g: GenerateIn):
    c = _client(cid)
    if g.kind not in engine.GENERATORS:
        raise HTTPException(400, "Type de document inconnu")
    fn = engine.GENERATORS[g.kind][1]
    if g.kind == "audit_checklist":
        doc = fn(c, g.clauses)
    elif g.kind == "integrated_matrix":
        doc = fn(c, g.standards)
    else:
        doc = fn(c)
    doc["id"] = store.save_document(cid, doc)
    return doc


@app.get("/api/clients/{cid}/gap", dependencies=[Depends(auth)])
def get_gap(cid: int):
    _client(cid)
    return store.get_gap(cid)


@app.post("/api/clients/{cid}/gap", dependencies=[Depends(auth)])
def gap(cid: int, g: GapIn):
    c = _client(cid)
    bad = [k for k, v in g.answers.items() if v.get("status") not in engine.STATUS_LABEL]
    if bad:
        raise HTTPException(400, f"Statut invalide pour : {', '.join(bad)}")
    store.save_gap(cid, g.answers)
    doc = engine.gap_analysis(c, store.get_gap(cid))
    doc["id"] = store.save_document(cid, doc)
    return doc


@app.get("/api/documents/{did}", dependencies=[Depends(auth)])
def get_document(did: int):
    d = store.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    return d


@app.get("/api/documents/{did}/docx", dependencies=[Depends(auth)])
def docx(did: int):
    d = store.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", d["title"])[:80] + ".docx"
    return Response(export.to_docx(d),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.post("/api/ask", dependencies=[Depends(auth)])
def ask(a: AskIn):
    return engine.ask(a.question)


# ------------------------------------------------------------- PWA (front)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/sw.js")
def sw():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
