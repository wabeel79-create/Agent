"""API Kapsi-Q — SmartCell Technologies.
Lancement : python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agents, campus, engine, export, files, pilots, smoe, store
from .llm import PRESETS, llm

VERSION = "2.3.0"
STATIC = Path(__file__).parent / "static"
TOKEN = os.getenv("KAPSI_TOKEN", "")

app = FastAPI(title="Kapsi-Q", version=VERSION, docs_url="/api/docs")
store.init()
files.init()
campus.init()
smoe.init()
pilots.init()
if os.environ.get("KAPSI_NO_SCHEDULER") != "1":
    pilots.start_scheduler()
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


class RunIn(BaseModel):
    standard: str


class RootIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    label: str = ""
    write: bool = False


class ActionIn(BaseModel):
    standard: str | None = None
    source: str | None = None
    clause: str | None = None
    finding: str | None = None
    cause: str | None = None
    action: str | None = None
    owner: str | None = None
    due: str | None = None
    status: str | None = None


class StatusIn(BaseModel):
    status: str


class ValidateIn(BaseModel):
    by: str = Field(min_length=2, max_length=120)


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


def _lan_ips() -> list[str]:
    """Adresses IPv4 du poste sur le réseau local (pour connecter les téléphones)."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # aucun paquet envoyé : sert à choisir l'interface
        ips.add(s.getsockname()[0]); s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


@app.get("/api/network", dependencies=A)
def network(request: Request):
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    host = request.url.hostname or ""
    urls = [f"http://{ip}:{port}" for ip in _lan_ips()]
    if host not in ("localhost", "127.0.0.1") and f"{request.url.scheme}://{host}:{port}" not in urls:
        urls.insert(0, f"{request.url.scheme}://{host}:{port}")
    return {"urls": urls, "port": port, "hostname": socket.gethostname()}


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
    acts = store.list_actions()
    return {"clients": len(clients), "projects": proj, "audits": len(audits), "documents": len(store.list_documents()),
            "actions_open": sum(1 for a in acts if a["status"] != "Clôturée"), "runs": len(store.list_runs(limit=10000)),
            "to_validate": sum(1 for d in store.list_documents() if d.get("status") != "Validé"),
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


# ------------------------------------------------------------------ agents
def _host_only(request: Request) -> None:
    """Les dossiers autorisés ne se modifient que depuis le poste hôte (ou avec le jeton)."""
    host = request.client.host if request.client else ""
    if not TOKEN and host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "Pour des raisons de sécurité, les dossiers autorisés se modifient depuis le poste qui héberge Kapsi-Q.")


@app.get("/api/agents", dependencies=A)
def agent_list(campus_only: bool = False):
    return [{"key": k, "name": v[0], "desc": v[1]} for k, v in agents.AGENTS.items() if k.startswith(("campus_", "smoe_", "pia_")) == campus_only]


@app.post("/api/clients/{cid}/agents/{key}", dependencies=A)
def agent_start(cid: int, key: str, r: RunIn):
    _client(cid)
    if key not in agents.AGENTS:
        raise HTTPException(400, "Agent inconnu")
    std = _std(r.standard)
    store.add_project(cid, std)
    return {"run_id": agents.start(cid, key, std)}


@app.get("/api/runs", dependencies=A)
def runs_all():
    names = {c["id"]: c["name"] for c in store.list_clients()}
    return [{**r, "client": names.get(r["client_id"], "?"), "agent_name": agents.AGENTS.get(r["agent"], (r["agent"],))[0]} for r in store.list_runs(limit=30)]


@app.get("/api/clients/{cid}/runs", dependencies=A)
def runs_client(cid: int):
    return [{**r, "agent_name": agents.AGENTS.get(r["agent"], (r["agent"],))[0]} for r in store.list_runs(cid)]


@app.get("/api/runs/{rid}", dependencies=A)
def run_get(rid: int):
    r = store.get_run(rid)
    if not r:
        raise HTTPException(404, "Exécution introuvable")
    docs = {d["id"]: d for d in store.list_documents(r["client_id"])}
    for d in r["outputs"].get("documents", []):
        d["status"] = docs.get(d["id"], {}).get("status")
    r["client"] = (store.get_client(r["client_id"]) or {}).get("name")
    r["agent_name"] = agents.AGENTS.get(r["agent"], (r["agent"],))[0]
    r["n_proposals"] = len(r["outputs"].get("gap_proposals") or {})
    if r["status"] == "Terminé" and r["outputs"].get("readiness"):
        r["outputs"]["readiness"] = agents.readiness(r["client_id"], r["standard"])  # valeur à jour
    return r


@app.post("/api/runs/{rid}/apply", dependencies=A)
def run_apply(rid: int):
    r = store.get_run(rid)
    if not r or not r["outputs"].get("gap_proposals"):
        raise HTTPException(400, "Aucune proposition à appliquer")
    n = agents.apply_proposals(r["client_id"], r["standard"], r["outputs"]["gap_proposals"])
    return {"applied": n}


@app.get("/api/clients/{cid}/tree/{std}", dependencies=A)
def agent_tree(cid: int, std: str):
    if not store.get_client(cid):
        raise HTTPException(404, "Client introuvable")
    return agents.tree(cid, std)


@app.get("/api/clients/{cid}/readiness/{std}", dependencies=A)
def readiness(cid: int, std: str):
    _client(cid)
    return agents.readiness(cid, _std(std))


# ------------------------------------------------------- fichiers et Drive
@app.get("/api/files/roots", dependencies=A)
def roots_get():
    return {"roots": files.roots(), "stats": files.stats()}


@app.post("/api/files/roots", dependencies=A)
def roots_add(r: RootIn, request: Request):
    _host_only(request)
    try:
        return {"roots": files.add_root(r.path, r.label, r.write)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/files/roots", dependencies=A)
def roots_del(path: str, request: Request):
    _host_only(request)
    return {"roots": files.remove_root(path)}


@app.post("/api/files/index", dependencies=A)
def files_index():
    return {**files.index_all(), **files.stats()}


@app.get("/api/files/search", dependencies=A)
def files_search(q: str):
    return files.search(q, limit=15)


# --------------------------------------------------------- actions et formations
@app.get("/api/clients/{cid}/actions", dependencies=A)
def actions_get(cid: int):
    _client(cid)
    return store.list_actions(cid)


@app.post("/api/clients/{cid}/actions", dependencies=A)
def actions_add(cid: int, a: ActionIn):
    _client(cid)
    return {"id": store.add_action(cid, {k: v for k, v in a.model_dump().items() if v is not None})}


@app.put("/api/actions/{aid}", dependencies=A)
def actions_upd(aid: int, a: ActionIn):
    if a.status and a.status not in ("Ouverte", "En cours", "Clôturée"):
        raise HTTPException(400, "Statut invalide")
    r = store.update_action(aid, {k: v for k, v in a.model_dump().items() if v is not None})
    if not r:
        raise HTTPException(404, "Action introuvable")
    return r


@app.get("/api/clients/{cid}/trainings", dependencies=A)
def trainings_get(cid: int):
    _client(cid)
    return store.list_trainings(cid)


@app.put("/api/trainings/{tid}", dependencies=A)
def trainings_upd(tid: int, s: StatusIn):
    if s.status not in ("Planifiée", "Réalisée", "Annulée"):
        raise HTTPException(400, "Statut invalide")
    store.update_training(tid, s.status)
    return {"ok": True}


@app.post("/api/documents/{did}/validate", dependencies=A)
def doc_validate(did: int, v: ValidateIn):
    if not store.get_document(did):
        raise HTTPException(404, "Document introuvable")
    store.validate_document(did, v.by)
    return {"ok": True}


# --------------------------------------------------------------- documents
@app.get("/api/documents/{did}", dependencies=A)
def get_document(did: int):
    d = store.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    meta = store._one("SELECT status, validated_by, validated_at, path, agent FROM documents WHERE id=?", (did,)) or {}
    return {**d, "meta": meta}


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



# --------------------------------------------------------------------- Kapsi Campus (ISO 21001)
def _client_or_404(cid: int) -> dict:
    c = store.get_client(cid)
    if not c:
        raise HTTPException(404, "Établissement introuvable")
    return c


def _bad(e: Exception):
    raise HTTPException(400, str(e))


@app.get("/api/campus/meta", dependencies=A)
def campus_meta():
    return {"types": {k: {"label": v[0], "form": v[1], "service": v[2], "delay": v[3]} for k, v in campus.TYPES.items()},
            "statuses": campus.STATUSES, "plans": {k: {"label": v[0], "form": v[1]} for k, v in campus.PLANS.items()},
            "categories": {k: {"label": v[0], "form": v[1]} for k, v in campus.CATEGORIES.items()},
            "processes": [dict(zip(("code", "kind", "name", "pilot", "clauses", "mode"), p)) for p in campus.PROCESSES]}


@app.get("/api/clients/{cid}/campus", dependencies=A)
def campus_summary(cid: int):
    _client_or_404(cid)
    return campus.summary(cid)


@app.get("/api/clients/{cid}/campus/requests", dependencies=A)
def campus_requests(cid: int, status: str | None = None, type: str | None = None):
    return campus.list_requests(cid, status, type)


@app.post("/api/clients/{cid}/campus/requests", dependencies=A)
def campus_add_request(cid: int, d: dict):
    _client_or_404(cid)
    try:
        return campus.add_request(cid, d)
    except ValueError as e:
        _bad(e)


@app.put("/api/campus/requests/{rid}", dependencies=A)
def campus_update_request(rid: int, d: dict):
    try:
        return campus.update_request(rid, d)
    except KeyError:
        raise HTTPException(404, "Demande introuvable")
    except ValueError as e:
        _bad(e)


@app.get("/api/clients/{cid}/campus/assets", dependencies=A)
def campus_assets(cid: int):
    return campus.list_assets(cid)


@app.post("/api/clients/{cid}/campus/assets", dependencies=A)
def campus_add_asset(cid: int, d: dict):
    _client_or_404(cid)
    try:
        return {"id": campus.add_asset(cid, d)}
    except ValueError as e:
        _bad(e)


@app.get("/api/campus/assets/{aid}", dependencies=A)
def campus_asset(aid: int):
    a = campus.asset_life(aid)
    if not a:
        raise HTTPException(404, "Équipement introuvable")
    return a


@app.post("/api/campus/assets/{aid}/interventions", dependencies=A)
def campus_add_intervention(aid: int, d: dict):
    a = campus.asset_life(aid)
    if not a:
        raise HTTPException(404, "Équipement introuvable")
    return {"id": campus.add_intervention(a["client_id"], {**d, "asset_id": aid})}


@app.get("/api/clients/{cid}/campus/tasks", dependencies=A)
def campus_tasks(cid: int, plan: str | None = None, start: str | None = None, end: str | None = None):
    return campus.list_tasks(cid, plan, start, end)


@app.post("/api/clients/{cid}/campus/tasks", dependencies=A)
def campus_add_task(cid: int, d: dict):
    _client_or_404(cid)
    try:
        return {"id": campus.add_task(cid, d)}
    except (ValueError, KeyError) as e:
        _bad(e)


@app.put("/api/campus/tasks/{tid}", dependencies=A)
def campus_set_task(tid: int, d: dict):
    campus.set_task(tid, bool(d.get("done")), d.get("note"))
    return {"ok": True}


@app.get("/api/clients/{cid}/campus/mail", dependencies=A)
def campus_mail(cid: int):
    return campus.list_mail(cid)


@app.post("/api/clients/{cid}/campus/mail", dependencies=A)
def campus_add_mail(cid: int, d: dict):
    _client_or_404(cid)
    return {"id": campus.add_mail(cid, d)}


@app.put("/api/campus/mail/{mid}", dependencies=A)
def campus_update_mail(mid: int, d: dict):
    if d.get("status") not in ("Enregistré", "Diffusé", "Traité"):
        raise HTTPException(400, "Statut inconnu")
    campus.update_mail(mid, d["status"])
    return {"ok": True}


@app.get("/api/clients/{cid}/campus/calls", dependencies=A)
def campus_calls(cid: int):
    return campus.list_calls(cid)


@app.post("/api/clients/{cid}/campus/calls", dependencies=A)
def campus_add_call(cid: int, d: dict):
    _client_or_404(cid)
    return {"id": campus.add_call(cid, d)}


@app.get("/api/clients/{cid}/campus/complaints", dependencies=A)
def campus_complaints(cid: int):
    return campus.list_complaints(cid)


@app.post("/api/clients/{cid}/campus/complaints", dependencies=A)
def campus_add_complaint(cid: int, d: dict):
    _client_or_404(cid)
    return campus.add_complaint(cid, d)


@app.put("/api/campus/complaints/{kid}", dependencies=A)
def campus_update_complaint(kid: int, d: dict):
    try:
        campus.update_complaint(kid, d)
    except ValueError as e:
        _bad(e)
    return {"ok": True}


@app.post("/api/clients/{cid}/campus/archive", dependencies=A)
def campus_add_archive(cid: int, d: dict):
    _client_or_404(cid)
    return {"id": campus.add_archive(cid, d)}


@app.get("/api/clients/{cid}/campus/indicators", dependencies=A)
def campus_indicators(cid: int, period: str | None = None):
    _client_or_404(cid)
    try:
        return campus.compute(cid, period)
    except ValueError as e:
        _bad(e)


@app.put("/api/clients/{cid}/campus/indicators/{code}", dependencies=A)
def campus_set_indicator(cid: int, code: str, d: dict):
    try:
        if "target" in d:
            tg = json.loads(store.get_setting(f"campus.targets.{cid}") or "{}")
            tg[code] = float(d["target"])
            store.set_setting(f"campus.targets.{cid}", json.dumps(tg))
        if "value" in d:
            campus.set_measure(cid, code, d.get("period") or "courante", float(d["value"]), d.get("note", ""))
    except (ValueError, TypeError) as e:
        _bad(e)
    return {"ok": True}


@app.get("/api/clients/{cid}/campus/processes", dependencies=A)
def campus_processes(cid: int):
    return campus.processes(cid)


@app.get("/api/clients/{cid}/campus/guichet", dependencies=A)
def campus_guichet_admin(cid: int, request: Request, renew: bool = False):
    _client_or_404(cid)
    if renew:
        _host_only(request)
    return {"code": campus.guichet_code(cid, renew)}


@app.post("/api/clients/{cid}/campus/demo", dependencies=A)
def campus_demo(cid: int, request: Request):
    _host_only(request)
    _client_or_404(cid)
    if campus.list_requests(cid, limit=1):
        raise HTTPException(409, "Cet établissement a déjà des données")
    campus.seed_demo(cid)
    return campus.summary(cid)



# --------------------------------------------------------------------- SMOE : tous les processus ISO 21001
@app.get("/api/smoe/meta", dependencies=A)
def smoe_meta():
    return smoe.meta()


@app.get("/api/clients/{cid}/smoe", dependencies=A)
def smoe_overview(cid: int):
    _client_or_404(cid)
    return smoe.overview(cid)


@app.get("/api/clients/{cid}/smoe/{process}/{register}", dependencies=A)
def smoe_records(cid: int, process: str, register: str):
    try:
        smoe.reg(process, register)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return smoe.records(cid, process, register)


@app.post("/api/clients/{cid}/smoe/{process}/{register}", dependencies=A)
def smoe_add(cid: int, process: str, register: str, d: dict):
    _client_or_404(cid)
    try:
        return smoe.add(cid, process, register, d.get("data") or {}, d.get("status"))
    except ValueError as e:
        _bad(e)


@app.put("/api/smoe/records/{rid}", dependencies=A)
def smoe_update(rid: int, d: dict):
    try:
        return smoe.update(rid, d)
    except KeyError:
        raise HTTPException(404, "Enregistrement introuvable")
    except ValueError as e:
        _bad(e)


@app.post("/api/clients/{cid}/smoe/demo", dependencies=A)
def smoe_demo(cid: int, request: Request):
    _host_only(request)
    _client_or_404(cid)
    if store._rows("SELECT id FROM s_records WHERE client_id=? LIMIT 1", (cid,)):
        raise HTTPException(409, "Cet établissement a déjà des enregistrements SMOE")
    smoe.seed_demo(cid)
    return {"ok": True}



# --------------------------------------------------------------------- Pilotes IA
@app.get("/api/clients/{cid}/pilots", dependencies=A)
def pilots_status(cid: int):
    _client_or_404(cid)
    return {"auto": pilots.auto(cid), "rights": pilots.RIGHTS, "forbidden": pilots.FORBIDDEN, "pilots": pilots.status(cid)}


@app.put("/api/clients/{cid}/pilots", dependencies=A)
def pilots_settings(cid: int, d: dict):
    _client_or_404(cid)
    try:
        if "auto" in d:
            pilots.set_auto(cid, d["auto"])
        for code, name in (d.get("humans") or {}).items():
            if not str(name).strip():
                raise ValueError("Nom du pilote humain vide")
            pilots.set_human(cid, code, str(name))
    except ValueError as e:
        _bad(e)
    return pilots_status(cid)


@app.post("/api/pilots/alerts/{aid}/ack", dependencies=A)
def pilots_ack(aid: int):
    pilots.ack(aid)
    return {"ok": True}


# Guichet numérique : ouvert aux demandeurs avec le code de l'établissement (pas de jeton administrateur)
class GuichetIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    kind: str = "demande"
    type: str | None = None
    requester: str = Field(default="", max_length=120)
    dept: str = Field(default="", max_length=120)
    title: str = Field(default="", max_length=200)
    details: dict = {}
    qty: int = Field(default=1, ge=1, le=5000)
    needed_by: str | None = None
    subject: str = Field(default="", max_length=1000)
    source: str = "Apprenant"


@app.get("/api/guichet/{cid}")
def guichet_info(cid: int, code: str):
    c = _client_or_404(cid)
    if not campus.check_code(cid, code):
        raise HTTPException(403, "Code d'accès invalide")
    types = {k: {"label": v[0], "form": v[1], "delay": v[3]} for k, v in campus.TYPES.items()}
    for k, (label, p, rg) in smoe.GUICHET.items():
        types[k] = {"label": label, "form": rg["form"], "delay": rg["delay"], "process": p,
                    "fields": [[f, l, t] for f, l, t in rg["fields"] if f not in ("etudiant", "niveau") and (t != "date" or f == "date")]}
    return {"name": c["name"], "types": types}


@app.post("/api/guichet/{cid}")
def guichet_submit(cid: int, d: GuichetIn):
    _client_or_404(cid)
    if not campus.check_code(cid, d.code):
        raise HTTPException(403, "Code d'accès invalide")
    if d.kind == "reclamation":
        if len(d.subject.strip()) < 5:
            raise HTTPException(400, "Décrivez la réclamation")
        c = campus.add_complaint(cid, {"subject": d.subject, "source": d.source, "channel": "Guichet numérique"})
        return {"ticket": c["ticket"], "service": c["service"], "due": c["due"]}
    if d.type and d.type.startswith("smoe:"):
        if d.type not in smoe.GUICHET:
            raise HTTPException(400, "Type de demande inconnu")
        _, p, rg = smoe.GUICHET[d.type]
        data = {**{k: v for k, v in (d.details or {}).items()}, "etudiant": d.requester}
        if any(f == "niveau" for f, _, _ in rg["fields"]) and not data.get("niveau") and d.dept:
            data["niveau"] = d.dept
        if rg["title"] not in data and d.title:
            data[rg["title"]] = d.title
        try:
            r = smoe.add(cid, p, rg["key"], data, requester=d.requester, ticket=campus._ticket("S"))
        except ValueError as e:
            _bad(e)
        return {"ticket": r["ticket"], "service": smoe.PROCESSES[p]["name"], "needed_by": r["due"], "form": rg["form"]}
    try:
        r = campus.add_request(cid, {"type": d.type, "requester": d.requester, "dept": d.dept, "title": d.title, "details": d.details,
                                     "qty": d.qty, "needed_by": d.needed_by})
    except ValueError as e:
        _bad(e)
    return {"ticket": r["ticket"], "service": r["service"], "needed_by": r["needed_by"], "form": r["form"]}


@app.get("/api/guichet/{cid}/ticket/{ticket}")
def guichet_ticket(cid: int, ticket: str, code: str):
    if not campus.check_code(cid, code):
        raise HTTPException(403, "Code d'accès invalide")
    r = campus.find_ticket(cid, ticket)
    if not r:
        s = smoe.find_ticket(cid, ticket)
        if not s:
            raise HTTPException(404, "Ticket introuvable")
        rg = smoe.reg(s["process"], s["register"])
        return {"ticket": s["ticket"], "type_label": rg["guichet"] or rg["label"], "title": s["title"], "status": s["status"], "statuses": rg["statuses"],
                "needed_by": s["due"], "done_at": s["done_at"], "received_at": None, "satisfied": s["satisfied"], "service": smoe.PROCESSES[s["process"]]["name"]}
    return {k: r[k] for k in ("ticket", "type_label", "title", "status", "needed_by", "done_at", "received_at", "satisfied", "service")}


@app.post("/api/guichet/{cid}/ticket/{ticket}/receive")
def guichet_receive(cid: int, ticket: str, d: dict):
    if not campus.check_code(cid, str(d.get("code", ""))):
        raise HTTPException(403, "Code d'accès invalide")
    r = campus.find_ticket(cid, ticket)
    if not r:
        raise HTTPException(404, "Ticket introuvable")
    if r["status"] != "Réalisée":
        raise HTTPException(409, "La demande n'est pas encore réalisée")
    r = campus.update_request(r["id"], {"status": "Réceptionnée", "satisfied": bool(d.get("satisfied", True)), "remark": (d.get("remark") or "")[:300] or None})
    return {"status": r["status"]}


@app.get("/guichet")
def guichet_page():
    return FileResponse(STATIC / "guichet.html")


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
