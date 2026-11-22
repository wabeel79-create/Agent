"""Données de démonstration (entreprises fictives) pour présenter Kapsi-Q.
Usage : python -m app.demo
"""
import random

from . import engine, store

DEMO = [
    {"name": "Métal Plus SARL (démo)", "sector": "Fabrication de pièces métalliques", "size": "85",
     "activities": "Découpe laser, Soudure, Peinture, Contrôle final", "contact": "Directeur qualité",
     "standards": ["ISO 9001", "ISO 45001"], "level": 0.75},
    {"name": "AgroDélice (démo)", "sector": "Agroalimentaire — biscuiterie", "size": "140",
     "activities": "Réception matières, Pétrissage, Cuisson, Conditionnement", "contact": "Responsable QHSE",
     "standards": ["ISO 22000", "ISO 14001"], "level": 0.55},
    {"name": "Institut Horizon Formation (démo)", "sector": "Centre de formation professionnelle", "size": "30",
     "activities": "Conception des programmes, Admission, Formation, Évaluation", "contact": "Directrice",
     "standards": ["ISO 21001"], "level": 0.45},
    {"name": "DataSoft Services (démo)", "sector": "Services informatiques", "size": "60",
     "activities": "Développement logiciel, Hébergement, Support client", "contact": "RSSI",
     "standards": ["ISO 27001", "ISO 9001"], "level": 0.6},
]


def run(seed: int = 7) -> None:
    rnd = random.Random(seed)
    store.init()
    existing = {c["name"] for c in store.list_clients()}
    for d in DEMO:
        if d["name"] in existing:
            continue
        c = store.create_client(d)
        for std in d["standards"]:
            store.add_project(c["id"], std)
            ans = {}
            for cl in engine.clauses(std):
                r = rnd.random()
                st = "C" if r < d["level"] else "P" if r < d["level"] + 0.15 else "NC"
                ans[cl["id"]] = {"status": st, "note": ""}
            store.save_gap(c["id"], std, ans)
            tasks = [f"{p['phase']}|{t}" for p in engine.ROADMAP for t in p["tasks"]]
            store.set_progress(c["id"], std, {k: True for k in tasks[: int(len(tasks) * d["level"])]})
        a = store.create_audit(c["id"], {"type": "blanc" if d["level"] < 0.7 else "stage2", "standards": d["standards"][:1],
                                         "date": "2026-11-15", "lead_auditor": "Auditeur Kapsi-Q"})
        f = {}
        for cl in engine.clauses(d["standards"][0]):
            r = rnd.random()
            g = "C" if r < 0.68 else "OA" if r < 0.8 else "PF" if r < 0.88 else "NCm" if r < 0.97 else "NCM"
            f[f"{d['standards'][0]}|{cl['id']}"] = {"grade": g, "note": "Constat de démonstration" if g in ("NCm", "NCM", "OA") else ""}
        store.save_findings(a["id"], f)
        print("Créé :", d["name"])


if __name__ == "__main__":
    run()
