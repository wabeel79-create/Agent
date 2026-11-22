import io
import os
import tempfile

os.environ["KAPSI_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from docx import Document  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import engine  # noqa: E402

c = TestClient(app)
CLIENT = {"name": "Métal Plus SARL", "sector": "Fabrication métallique", "size": "50",
          "activities": "Découpe laser, Soudure, Peinture"}


def _new():
    return c.post("/api/clients", json=CLIENT).json()["id"]


def test_health_offline():
    h = c.get("/api/health").json()
    assert h["status"] == "ok" and h["ai_backend"] == "none"


def test_all_generators_and_docx():
    cid = _new()
    for kind in engine.GENERATORS:
        r = c.post(f"/api/clients/{cid}/generate", json={"kind": kind})
        assert r.status_code == 200, kind
        doc = r.json()
        assert doc["sections"] and doc["client"] == CLIENT["name"]
        x = c.get(f"/api/documents/{doc['id']}/docx")
        assert x.status_code == 200
        Document(io.BytesIO(x.content))  # fichier Word valide
    assert len(c.get(f"/api/clients/{cid}/documents").json()) == len(engine.GENERATORS)


def test_process_map_uses_activities():
    cid = _new()
    doc = c.post(f"/api/clients/{cid}/generate", json={"kind": "process_map"}).json()
    names = [r[1] for r in doc["sections"][0]["table"]["rows"]]
    assert "Soudure" in names and "Découpe laser" in names


def test_gap_score_and_actions():
    cid = _new()
    answers = {cl["id"]: {"status": "C"} for cl in engine.ISO9001}
    answers["7.5"] = {"status": "NC", "note": "Pas de liste des documents"}
    answers["6.1"] = {"status": "P"}
    answers["8.3"] = {"status": "NA"}
    doc = c.post(f"/api/clients/{cid}/gap", json={"answers": answers}).json()
    n = len(engine.ISO9001) - 1
    assert doc["sections"][0]["score"] == round(100 * (n - 1.5) / n)
    actions = doc["sections"][2]["table"]["rows"]
    assert {a[0] for a in actions} == {"7.5", "6.1"}
    assert c.get(f"/api/clients/{cid}/gap").json()["7.5"]["note"] == "Pas de liste des documents"


def test_gap_rejects_bad_status():
    cid = _new()
    r = c.post(f"/api/clients/{cid}/gap", json={"answers": {"4.1": {"status": "X"}}})
    assert r.status_code == 400


def test_ask_finds_clause():
    r = c.post("/api/ask", json={"question": "Que demande le 7.5 sur les documents ?"}).json()
    assert r["sources"][0].startswith("§7.5")


def test_unknown_kind_and_client():
    cid = _new()
    assert c.post(f"/api/clients/{cid}/generate", json={"kind": "zzz"}).status_code == 400
    assert c.get("/api/clients/99999/documents").status_code == 404


def test_delete_client():
    cid = _new()
    assert c.delete(f"/api/clients/{cid}").status_code == 200
    assert c.get(f"/api/clients/{cid}/documents").status_code == 404


def test_pwa_assets():
    assert c.get("/").status_code == 200
    assert c.get("/manifest.webmanifest").status_code == 200
    assert c.get("/sw.js").status_code == 200
