"""API Kapsi-Q — SmartCell Technologies.
Lancement : python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
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
from .llm import PRESETS, llm

VERSION = "0.2.0"
STATIC = Path(__file__).parent / "static"
TOKEN = os.getenv("KAPSI_TOKEN", "")

app = FastAPI(title="Kapsi-Q", version=VERSION, docs_url="/api/docs")
store.init()
llm.configure(store.get_settings())


def auth(request: Request) -> None:
    if TOKEN and not secrets.compare_digest(request.headers.get("X-Kapsi-Token", ""), TOKEN):
        raise HTTPException(401, "Jeton d'accès invalide")


A = [Depends(auth)]


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str = ""
    size: str = ""
    activities: str = ""
    contact: str = ""
    standards: list[str] = []


class GenerateIn(BaseModel):
    kind: str
    standard: str | None = None


class GapIn(BaseModel):
    answers: dict[str, dict]


class ProgressIn(BaseModel):
    progress: dict[str, bool]


class AuditIn(BaseModel):
    type: str
    standards: list[str] = Field(min_length=1)
    date: str = ""
    lead_auditor: str = ""


class FindingsIn(BaseModel):
    findings: dict[str, dict]


class WriteIn(BaseModel):
    standard: str
    doc_type: str
    subject: str = Field(min_length=2, max_length=300)
    instructions: str = ""


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    standard: str | None = None


class LLMIn(BaseModel):
    provider: str
    url: str = ""
    model: str = ""
    api_key: str | None = None
    module: str = ""


def _client(cid: int) -> dict:
    c = store.get_client(cid)
    if not c:
        raise HTTPException(404, "Client introuvable")
    return c


def _std(s: str | None) -> str:
    if s and s not in engine.STANDARDS:
        raise HTTPException(400, f"Norme inconnue : {s}")
    return s or "ISO 9001"


def _save(cid: int, doc: dict) -> dict:
    doc["id"] = store.save_document(cid, doc)
    return doc


# ---------------------------------------------------------------- système
@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "ai": llm.public(), "auth": bool(TOKEN)}


@app.get("/api/catalog", dependencies=A)
def catalog():
    return {"standards": engine.catalog_standards(),
            "generators": [{"kind": k, "label": v[0], "only": v[2]} for k, v in engine.GENERATORS.items()],
            "gap_status": engine.GAP_STATUS, "audit_grades": engine.AUDIT_GRADES, "audit_types": engine.AUDIT_TYPES,
            "roadmap": engine.ROADMAP, "doc_types": engine.DOC_TYPES,
            "providers": {k: {kk: vv for kk, vv in v.items()} for k, v in PRESETS.items()}}


@app.get("/api/standards/{std}/clauses", dependencies=A)
def std_clauses(std: str):
    return engine.clauses(_std(std))


@app.get("/api/dashboard", dependencies=A)
def dashboard():
    clients = store.list_clients(); projects = store.list_projects(); audits = store.list_audits()
    names = {c["id"]: c["name"] for c in clients}
    proj = []
    for p in projects:
        g = engine.gap_score(p["standard"], store.get_gap(p["client_id"], p["standard"]))
        ntask = sum(len(ph["tasks"]) for ph in engine.ROADMAP)
        proj.append({"client_id": p["client_id"], "client": names.get(p["client_id"], "?"), "standard": p["standard"],
                     "gap": g["score"], "roadmap": round(100 * sum(1 for v in p["progress"].values() if v) / ntask)})
    findings = {k: 0 for k in engine.AUDIT_GRADES}
    for a in audits:
        for k, v in engine.audit_stats(a)["counts"].items():
            findings[k] += v
    by_std = {}
    for p in proj:
        by_std[p["standard"]] = by_std.get(p["standard"], 0) + 1
    return {"clients": len(clients), "projects": proj, "audits": len(audits), "documents": len(store.list_documents()),
            "findings": findings, "by_standard": by_std,
            "recent_audits": [{"id": a["id"], "client": names.get(a["client_id"], "?"), "client_id": a["client_id"],
                               "type": engine.AUDIT_TYPES.get(a["type"], a["type"]), "standards": a["standards"],
                               **{k: v for k, v in engine.audit_stats(a).items() if k in ("conformity", "verdict", "progress")}} for a in audits[:6]]}


# ---------------------------------------------------------------- clients
@app.get("/api/clients", dependencies=A)
def clients():
    projects = store.list_projects()
    out = store.list_clients()
    for c in out:
        c["standards"] = [p["standard"] for p in projects if p["client_id"] == c["id"]]
    return out


@app.post("/api/clients", dependencies=A)
def create_client(c: ClientIn):
    for s in c.standards:
        _std(s)
    cl = store.create_client(c.model_dump())
    for s in c.standards:
        store.add_project(cl["id"], s)
    return cl


@app.get("/api/clients/{cid}", dependencies=A)
def get_client(cid: int):
    c = _client(cid)
    c["projects"] = []
    for p in store.list_projects(cid):
        g = engine.gap_score(p["standard"], store.get_gap(cid, p["standard"]))
        c["projects"].append({**p, "gap": g})
    c["audits"] = [{**a, "stats": engine.audit_stats(a)} for a in store.list_audits(cid)]
    c["documents"] = store.list_documents(cid)
    return c


@app.put("/api/clients/{cid}", dependencies=A)
def update_client(cid: int, c: ClientIn):
    _client(cid)
    return store.update_client(cid, c.model_dump())


@app.delete("/api/clients/{cid}", dependencies=A)
def delete_client(cid: int):
    _client(cid); store.delete_client(cid)
    return {"deleted": cid}


@app.post("/api/clients/{cid}/projects/{std}", dependencies=A)
def add_project(cid: int, std: str):
    _client(cid); store.add_project(cid, _std(std))
    return {"ok": True}


@app.delete("/api/clients/{cid}/projects/{std}", dependencies=A)
def remove_project(cid: int, std: str):
    _client(cid); store.remove_project(cid, _std(std))
    return {"ok": True}


@app.put("/api/clients/{cid}/projects/{std}/progress", dependencies=A)
def progress(cid: int, std: str, p: ProgressIn):
    _client(cid); store.set_progress(cid, _std(std), p.progress)
    return {"ok": True}


# ----------------------------------------------------------- mise en place
@app.post("/api/clients/{cid}/generate", dependencies=A)
def generate(cid: int, g: GenerateIn):
    c = _client(cid)
    if g.kind not in engine.GENERATORS:
        raise HTTPException(400, "Type de document inconnu")
    std = _std(g.standard)
    label, fn, only = engine.GENERATORS[g.kind]
    if g.kind == "roadmap":
        prog = next((p["progress"] for p in store.list_projects(cid) if p["standard"] == std), {})
        return _save(cid, fn(c, std, prog))
    return _save(cid, fn(c, (only or [std])[0] if only and std not in only else std))


@app.get("/api/clients/{cid}/gap/{std}", dependencies=A)
def get_gap(cid: int, std: str):
    _client(cid); std = _std(std)
    ans = store.get_gap(cid, std)
    return {"answers": ans, "score": engine.gap_score(std, ans), "clauses": engine.clauses(std)}


@app.put("/api/clients/{cid}/gap/{std}", dependencies=A)
def save_gap(cid: int, std: str, g: GapIn):
    _client(cid); std = _std(std)
    bad = [k for k, v in g.answers.items() if v.get("status") not in engine.GAP_STATUS]
    if bad:
        raise HTTPException(400, f"Statut invalide : {', '.join(bad)}")
    store.save_gap(cid, std, g.answers)
    return engine.gap_score(std, store.get_gap(cid, std))


@app.post("/api/clients/{cid}/gap/{std}/report", dependencies=A)
def gap_report(cid: int, std: str):
    c = _client(cid); std = _std(std)
    return _save(cid, engine.gap_analysis(c, std, store.get_gap(cid, std)))


# ------------------------------------------------------------------ audits
@app.post("/api/clients/{cid}/audits", dependencies=A)
def create_audit(cid: int, a: AuditIn):
    _client(cid)
    if a.type not in engine.AUDIT_TYPES:
        raise HTTPException(400, "Type d'audit inconnu")
    for s in a.standards:
        _std(s)
    return store.create_audit(cid, a.model_dump())


def _audit(aid: int) -> dict:
    a = store.get_audit(aid)
    if not a:
        raise HTTPException(404, "Audit introuvable")
    return a


@app.get("/api/audits/{aid}", dependencies=A)
def get_audit(aid: int):
    a = _audit(aid)
    return {**a, "stats": engine.audit_stats(a), "client": store.get_client(a["client_id"]),
            "clauses": {s: engine.clauses(s) for s in a["standards"]}}


@app.put("/api/audits/{aid}/findings", dependencies=A)
def findings(aid: int, f: FindingsIn):
    _audit(aid)
    bad = [k for k, v in f.findings.items() if v.get("grade") and v["grade"] not in engine.AUDIT_GRADES]
    if bad:
        raise HTTPException(400, f"Cotation invalide : {', '.join(bad)}")
    a = store.save_findings(aid, f.findings)
    return engine.audit_stats(a)


@app.post("/api/audits/{aid}/plan", dependencies=A)
def audit_plan(aid: int):
    a = _audit(aid); c = store.get_client(a["client_id"])
    return _save(a["client_id"], engine.audit_plan(c, a))


@app.post("/api/audits/{aid}/report", dependencies=A)
def audit_report(aid: int):
    a = _audit(aid); c = store.get_client(a["client_id"])
    return _save(a["client_id"], engine.audit_report(c, a))


@app.delete("/api/audits/{aid}", dependencies=A)
def delete_audit(aid: int):
    _audit(aid); store.delete_audit(aid)
    return {"ok": True}


# --------------------------------------------------------------- documents
@app.get("/api/documents/{did}", dependencies=A)
def get_document(did: int):
    d = store.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    return d


@app.delete("/api/documents/{did}", dependencies=A)
def delete_document(did: int):
    store.delete_document(did)
    return {"ok": True}


@app.get("/api/documents/{did}/docx", dependencies=A)
def docx(did: int):
    d = get_document(did)
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", d["title"])[:80] + ".docx"
    return Response(export.to_docx(d), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ------------------------------------------------------------------- IA
@app.post("/api/clients/{cid}/write", dependencies=A)
def write(cid: int, w: WriteIn):
    c = _client(cid)
    return _save(cid, engine.write_document(c, _std(w.standard), w.doc_type, w.subject, w.instructions))


@app.post("/api/ask", dependencies=A)
def ask(a: AskIn):
    return engine.ask(a.question, a.standard)


@app.get("/api/settings/llm", dependencies=A)
def get_llm():
    return llm.public()


@app.put("/api/settings/llm", dependencies=A)
def set_llm(s: LLMIn):
    if s.provider not in PRESETS:
        raise HTTPException(400, "Fournisseur inconnu")
    d = {"provider": s.provider, "url": s.url, "model": s.model, "module": s.module}
    if s.api_key is not None:
        d["api_key"] = s.api_key
    store.set_settings(d)
    llm.configure(store.get_settings())
    return llm.public()


@app.post("/api/settings/llm/test", dependencies=A)
def test_llm():
    if not llm.available:
        return {"ok": False, "message": "Aucun modèle configuré : Kapsi-Q fonctionne avec ses générateurs."}
    out = llm.generate("Réponds uniquement : « Kapsi-Q connecté. »", max_tokens=30, timeout=60)
    return {"ok": bool(out), "message": out or f"Échec : {llm.last_error}"}


# --------------------------------------------------------------------- PWA
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
