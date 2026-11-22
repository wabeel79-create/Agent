import io
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["KAPSI_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KAPSI_BACKEND"] = "none"

import pytest  # noqa: E402
from docx import Document  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import engine  # noqa: E402
from app.llm import llm  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
STDS = list(engine.STANDARDS)
CLIENT = {"name": "Métal Plus SARL", "sector": "Fabrication métallique", "size": "50",
          "activities": "Découpe laser, Soudure, Peinture", "standards": ["ISO 9001", "ISO 14001"]}


def _new(**kw):
    return c.post("/api/clients", json={**CLIENT, **kw}).json()["id"]


@pytest.fixture(autouse=True)
def offline():
    llm.configure({"provider": "none"})
    yield
    llm.configure({"provider": "none"})


def test_health_and_catalog():
    assert c.get("/api/health").json()["ai"]["provider"] == "none"
    cat = c.get("/api/catalog").json()
    assert {s["code"] for s in cat["standards"]} >= {"ISO 9001", "ISO 14001", "ISO 45001", "ISO 21001", "ISO 27001"}


@pytest.mark.parametrize("std", STDS)
def test_clauses_sorted_and_specific(std):
    cl = engine.clauses(std)
    ids = [x["id"] for x in cl]
    assert ids == sorted(ids, key=engine._ckey) and len(set(ids)) == len(ids)
    for s in engine.STANDARDS[std]["specific"]:
        assert s["id"] in ids


def test_client_with_projects():
    cid = _new()
    d = c.get(f"/api/clients/{cid}").json()
    assert [p["standard"] for p in d["projects"]] == ["ISO 9001", "ISO 14001"]


@pytest.mark.parametrize("std", STDS)
def test_all_generators_every_standard_and_docx(std):
    cid = _new(standards=[std])
    for g in c.get("/api/catalog").json()["generators"]:
        r = c.post(f"/api/clients/{cid}/generate", json={"kind": g["kind"], "standard": std})
        assert r.status_code == 200, (std, g["kind"], r.text)
        doc = r.json()
        assert doc["sections"]
    docs = c.get(f"/api/clients/{cid}").json()["documents"]
    x = c.get(f"/api/documents/{docs[0]['id']}/docx")
    Document(io.BytesIO(x.content))


def test_soa_has_93_controls():
    cid = _new()
    d = c.post(f"/api/clients/{cid}/generate", json={"kind": "soa", "standard": "ISO 27001"}).json()
    assert len(d["sections"][1]["table"]["rows"]) == 93


def test_gap_flow_and_radar():
    cid = _new()
    cls = engine.clauses("ISO 14001")
    ans = {x["id"]: {"status": "C"} for x in cls}
    ans["6.1.2"] = {"status": "NC", "note": "Pas d'analyse environnementale"}
    s = c.put(f"/api/clients/{cid}/gap/ISO 14001", json={"answers": ans}).json()
    assert s["answered"] == len(cls) and s["score"] == round(100 * (len(cls) - 1) / len(cls))
    assert s["by_chapter"]["6"] < 100
    rep = c.post(f"/api/clients/{cid}/gap/ISO 14001/report").json()
    assert rep["sections"][2]["table"]["rows"][0][0] == "6.1.2"
    assert c.put(f"/api/clients/{cid}/gap/ISO 14001", json={"answers": {"4.1": {"status": "X"}}}).status_code == 400


def test_roadmap_progress():
    cid = _new()
    k = f"{engine.ROADMAP[0]['phase']}|{engine.ROADMAP[0]['tasks'][0]}"
    assert c.put(f"/api/clients/{cid}/projects/ISO 9001/progress", json={"progress": {k: True}}).status_code == 200
    d = c.post(f"/api/clients/{cid}/generate", json={"kind": "roadmap", "standard": "ISO 9001"}).json()
    assert d["sections"][1]["table"]["rows"][0][2] == "Fait"
    dash = c.get("/api/dashboard").json()
    assert any(p["roadmap"] > 0 for p in dash["projects"])


def test_third_party_audit_full_cycle():
    cid = _new(size="120")
    a = c.post(f"/api/clients/{cid}/audits", json={"type": "stage2", "standards": ["ISO 9001", "ISO 45001"], "date": "2026-12-01", "lead_auditor": "N. Selmi"}).json()
    plan = c.post(f"/api/audits/{a['id']}/plan").json()
    info = dict(plan["sections"][0]["table"]["rows"])
    assert "jour" in info["Durée indicative"] and plan["sections"][1]["table"]["rows"][-1][2].startswith("Réunion de clôture")
    f = {f"ISO 9001|{x['id']}": {"grade": "C"} for x in engine.clauses("ISO 9001")}
    f["ISO 9001|7.5"] = {"grade": "NCm", "note": "Liste des documents non à jour", "evidence": "LDV rév. 3"}
    f["ISO 45001|6.1.2"] = {"grade": "NCM", "note": "DUER absent pour l'atelier soudure"}
    f["ISO 45001|5.4"] = {"grade": "PF", "note": "Comité SST actif"}
    s = c.put(f"/api/audits/{a['id']}/findings", json={"findings": f}).json()
    assert s["counts"]["NCM"] == 1 and s["counts"]["NCm"] == 1 and s["verdict"] == "Certification non recommandée en l'état"
    s = c.put(f"/api/audits/{a['id']}/findings", json={"findings": {"ISO 45001|6.1.2": {"grade": "OA"}}}).json()
    assert s["verdict"] == "Certification recommandée sous réserve"
    rep = c.post(f"/api/audits/{a['id']}/report").json()
    ncs = next(x for x in rep["sections"] if x["heading"] == "Fiches de non-conformité")["table"]["rows"]
    assert len(ncs) == 1 and ncs[0][2] == "ISO 9001"
    assert c.put(f"/api/audits/{a['id']}/findings", json={"findings": {"ISO 9001|4.1": {"grade": "ZZ"}}}).status_code == 400


def test_audit_duration_scales():
    small = engine.audit_duration(10, ["ISO 9001"], "stage2")["days"]
    big = engine.audit_duration(500, ["ISO 9001"], "stage2")["days"]
    assert big > small >= 0.5


def test_writer_fallback_without_ai():
    cid = _new()
    d = c.post(f"/api/clients/{cid}/write", json={"standard": "ISO 9001", "doc_type": "Procédure", "subject": "Évaluation des fournisseurs"}).json()
    assert not d["ai"] and any("8.4" in b for s in d["sections"] for b in s.get("bullets", []))


class _FakeLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = {"choices": [{"message": {"content": "<think>raisonnement</think>## Objet\nTexte IA.\n- point 1"}}]}
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_writer_with_openai_compatible_api():
    srv = HTTPServer(("127.0.0.1", 0), _FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = c.put("/api/settings/llm", json={"provider": "custom", "url": f"http://127.0.0.1:{srv.server_port}", "model": "x", "api_key": "k"}).json()
        assert r["has_key"] and "api_key" not in r
        assert c.post("/api/settings/llm/test").json()["ok"]
        cid = _new()
        d = c.post(f"/api/clients/{cid}/write", json={"standard": "ISO 27001", "doc_type": "Procédure", "subject": "Sauvegardes"}).json()
        assert d["ai"] and d["sections"][0]["heading"] == "Objet" and "think" not in json.dumps(d)
    finally:
        srv.shutdown()
        c.put("/api/settings/llm", json={"provider": "none"})


def test_ask_multi_standard():
    r = c.post("/api/ask", json={"question": "Que demande ISO 14001 6.1.2 sur les aspects ?"}).json()
    assert r["sources"][0].startswith("ISO 14001 §6.1.2")


def test_delete_client_cascade():
    cid = _new()
    c.post(f"/api/clients/{cid}/audits", json={"type": "stage1", "standards": ["ISO 9001"]})
    assert c.delete(f"/api/clients/{cid}").status_code == 200
    assert c.get(f"/api/clients/{cid}").status_code == 404


def test_pwa_assets():
    for p in ("/", "/manifest.webmanifest", "/sw.js", "/static/chart.umd.js", "/static/app.js"):
        assert c.get(p).status_code == 200, p
