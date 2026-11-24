"""Données de démonstration (entreprises fictives) pour présenter et former à Kapsi-Q.
Usage : python -m app.demo (28 entreprises, dont 14 avec le travail des agents déjà fait)      (les entreprises déjà présentes ne sont pas recréées)

Toutes les entreprises sont fictives et marquées « (démo) ». Elles se suppriment depuis leur fiche.
"""
import random

from . import engine, store

# level : niveau de maturité (part des exigences conformes au diagnostic, et avancement de la feuille de route)
# audits : (type, normes, date, qualité) — qualité = probabilité qu'une exigence soit conforme en audit
DEMO = [
    {"name": "Métal Plus SARL (démo)", "sector": "Fabrication de pièces métalliques", "size": "85",
     "activities": "Découpe laser, Soudure, Peinture, Contrôle final", "contact": "Directeur qualité",
     "standards": ["ISO 9001", "ISO 45001"], "level": 0.75,
     "audits": [("stage2", ["ISO 9001"], "2026-11-15", 0.80)]},
    {"name": "AgroDélice (démo)", "sector": "Agroalimentaire — biscuiterie", "size": "140",
     "activities": "Réception matières, Pétrissage, Cuisson, Conditionnement", "contact": "Responsable QHSE",
     "standards": ["ISO 22000", "ISO 14001"], "level": 0.55,
     "audits": [("blanc", ["ISO 22000"], "2026-11-15", 0.65)]},
    {"name": "Institut Horizon Formation (démo)", "sector": "Centre de formation professionnelle", "size": "30",
     "activities": "Conception des programmes, Admission, Formation, Évaluation", "contact": "Directrice",
     "standards": ["ISO 21001"], "level": 0.45,
     "audits": [("blanc", ["ISO 21001"], "2026-11-15", 0.60)]},
    {"name": "DataSoft Services (démo)", "sector": "Services informatiques", "size": "60",
     "activities": "Développement logiciel, Hébergement, Support client", "contact": "RSSI",
     "standards": ["ISO 27001", "ISO 9001"], "level": 0.6,
     "audits": [("blanc", ["ISO 27001"], "2026-11-15", 0.70)]},
    {"name": "Câbles du Cap Bon (démo)", "sector": "Câblage automobile", "size": "320",
     "activities": "Coupe des fils, Sertissage, Assemblage des faisceaux, Test électrique, Expédition", "contact": "Responsable QSE",
     "standards": ["ISO 9001", "ISO 14001", "ISO 45001"], "level": 0.85,
     "audits": [("surveillance", ["ISO 9001", "ISO 14001", "ISO 45001"], "2026-10-21", 0.90)]},
    {"name": "Clinique Azur Médical (démo)", "sector": "Santé — clinique pluridisciplinaire", "size": "180",
     "activities": "Admission des patients, Hospitalisation, Bloc opératoire, Laboratoire, Stérilisation", "contact": "Directeur des soins",
     "standards": ["ISO 9001", "ISO 45001"], "level": 0.5,
     "audits": [("stage1", ["ISO 9001"], "2026-12-08", 0.70)]},
    {"name": "Huilerie Oliveraie du Sahel (démo)", "sector": "Agroalimentaire — huile d'olive", "size": "60",
     "activities": "Réception des olives, Trituration, Stockage, Mise en bouteille", "contact": "Gérant",
     "standards": ["ISO 22000", "ISO 14001"], "level": 0.7,
     "audits": [("stage2", ["ISO 22000"], "2026-09-30", 0.82)]},
    {"name": "Confection Sahel Mode (démo)", "sector": "Textile — confection pour l'export", "size": "450",
     "activities": "Coupe, Piquage, Finition, Repassage, Emballage", "contact": "Responsable qualité",
     "standards": ["ISO 9001", "ISO 45001", "ISO 14001"], "level": 0.65,
     "audits": [("recertification", ["ISO 9001"], "2026-10-05", 0.78), ("blanc", ["ISO 45001"], "2026-11-18", 0.62)]},
    {"name": "Hôtel Les Dunes Bleues (démo)", "sector": "Hôtellerie — resort 4 étoiles", "size": "210",
     "activities": "Hébergement, Restauration, Blanchisserie, Maintenance, Piscines et spa", "contact": "Directeur général",
     "standards": ["ISO 14001", "ISO 50001", "ISO 22000"], "level": 0.4,
     "audits": []},
    {"name": "PayNova Tunisie (démo)", "sector": "Fintech — paiement en ligne", "size": "90",
     "activities": "Développement de la plateforme, Exploitation des serveurs, Service client, Gestion des fraudes", "contact": "RSSI",
     "standards": ["ISO 27001", "ISO 9001"], "level": 0.8,
     "audits": [("stage2", ["ISO 27001"], "2026-11-03", 0.86)]},
    {"name": "École Les Petits Savants (démo)", "sector": "Enseignement privé primaire", "size": "70",
     "activities": "Inscriptions, Enseignement, Activités périscolaires, Évaluation des élèves", "contact": "Directrice",
     "standards": ["ISO 21001"], "level": 0.35,
     "audits": []},
    {"name": "Polymères du Nord (démo)", "sector": "Plasturgie — emballages", "size": "260",
     "activities": "Extrusion, Injection, Impression, Recyclage des chutes", "contact": "Responsable énergie",
     "standards": ["ISO 50001", "ISO 14001", "ISO 9001"], "level": 0.6,
     "audits": [("stage1", ["ISO 50001"], "2026-12-02", 0.75)]},
    {"name": "Carthago Fret Logistique (démo)", "sector": "Transport et logistique", "size": "130",
     "activities": "Entreposage, Préparation des commandes, Transport routier, Dédouanement", "contact": "Responsable QHSE",
     "standards": ["ISO 9001", "ISO 45001"], "level": 0.7,
     "audits": [("stage2", ["ISO 9001", "ISO 45001"], "2026-11-20", 0.76)]},
    {"name": "NeuroDev Labs (démo)", "sector": "Start-up — intelligence artificielle", "size": "25",
     "activities": "Collecte de données, Entraînement des modèles, Déploiement, Support client", "contact": "CTO",
     "standards": ["ISO 42001", "ISO 27001"], "level": 0.3,
     "audits": [("blanc", ["ISO 42001"], "2026-11-25", 0.55)]},
    # --- Lot 2 (v2.0) : entreprises avec le travail des agents déjà effectué
    # agents : liste d'agents lancés sur la première norme ; validate : nb de documents validés ; close : part des actions clôturées
    {"name": "Laboratoires Médina Pharma (démo)", "sector": "Industrie pharmaceutique — formes sèches", "size": "240",
     "activities": "Réception des matières premières, Granulation, Compression, Conditionnement, Contrôle qualité, Libération des lots", "contact": "Pharmacien responsable",
     "standards": ["ISO 9001", "ISO 14001", "ISO 45001"], "level": 0.7,
     "audits": [("surveillance", ["ISO 9001"], "2026-10-14", 0.84)], "agents": ["mission"], "validate": 12, "close": 0.5, "trained": 3},
    {"name": "Ciments du Haut Tell (démo)", "sector": "Cimenterie", "size": "520",
     "activities": "Carrière, Concassage, Cuisson du clinker, Broyage, Ensachage, Expédition", "contact": "Directeur HSE",
     "standards": ["ISO 14001", "ISO 45001", "ISO 50001"], "level": 0.6,
     "audits": [("stage2", ["ISO 14001", "ISO 45001"], "2026-11-10", 0.74)], "agents": ["mission"], "validate": 6, "close": 0.25, "trained": 2},
    {"name": "Laiterie Vergers du Nord (démo)", "sector": "Agroalimentaire — produits laitiers", "size": "190",
     "activities": "Collecte du lait, Pasteurisation, Fermentation, Conditionnement, Chaîne du froid", "contact": "Responsable sécurité des aliments",
     "standards": ["ISO 22000", "ISO 9001"], "level": 0.55,
     "audits": [("blanc", ["ISO 22000"], "2026-11-19", 0.66)], "agents": ["mission"], "validate": 4, "close": 0.0, "trained": 1},
    {"name": "AéroComposants Tunisie (démo)", "sector": "Aéronautique — pièces usinées", "size": "150",
     "activities": "Usinage 5 axes, Traitement de surface, Contrôle dimensionnel, Traçabilité, Expédition", "contact": "Responsable qualité",
     "standards": ["ISO 9001", "ISO 45001", "ISO 27001"], "level": 0.8,
     "audits": [("recertification", ["ISO 9001"], "2026-09-22", 0.88)], "agents": ["mission"], "validate": 20, "close": 0.8, "trained": 5},
    {"name": "Bâtisseurs de Carthage BTP (démo)", "sector": "Bâtiment et travaux publics", "size": "380",
     "activities": "Études, Préparation de chantier, Gros œuvre, Second œuvre, Réception des ouvrages", "contact": "Directeur technique",
     "standards": ["ISO 9001", "ISO 45001", "ISO 14001"], "level": 0.45,
     "audits": [], "agents": ["preuves", "qualite", "formateur"], "validate": 3, "close": 0.0, "trained": 1},
    {"name": "Source Bleue Zaghouan (démo)", "sector": "Embouteillage d'eau minérale", "size": "110",
     "activities": "Captage, Filtration, Soufflage des bouteilles, Embouteillage, Stockage", "contact": "Responsable QHSE",
     "standards": ["ISO 22000", "ISO 14001", "ISO 50001"], "level": 0.65,
     "audits": [("stage1", ["ISO 22000"], "2026-12-03", 0.76)], "agents": ["mission"], "validate": 8, "close": 0.3, "trained": 2},
    {"name": "Méditerranée Port Services (démo)", "sector": "Manutention portuaire et logistique", "size": "300",
     "activities": "Déchargement des navires, Stockage des conteneurs, Livraison, Maintenance des engins", "contact": "Responsable QHSE",
     "standards": ["ISO 45001", "ISO 9001"], "level": 0.5,
     "audits": [("blanc", ["ISO 45001"], "2026-11-12", 0.6)], "agents": ["auditeur", "capa"], "validate": 0, "close": 0.0, "trained": 0},
    {"name": "Université Privée NovaTech (démo)", "sector": "Enseignement supérieur privé", "size": "160",
     "activities": "Admissions, Enseignement, Stages et projets, Recherche, Diplomation", "contact": "Vice-président qualité",
     "standards": ["ISO 21001", "ISO 27001"], "level": 0.4,
     "audits": [], "agents": ["mission"], "validate": 2, "close": 0.0, "trained": 0},
    {"name": "Cartonnerie du Golfe (démo)", "sector": "Emballage carton ondulé", "size": "175",
     "activities": "Ondulation, Impression, Découpe, Collage, Palettisation", "contact": "Responsable énergie et qualité",
     "standards": ["ISO 9001", "ISO 50001"], "level": 0.7,
     "audits": [("stage2", ["ISO 50001"], "2026-10-28", 0.8)], "agents": ["pilote", "certification"], "validate": 0, "close": 0.0, "trained": 0},
    {"name": "Contact Center Médina (démo)", "sector": "Centre d'appels offshore", "size": "600",
     "activities": "Recrutement des téléconseillers, Production des appels, Contrôle qualité des appels, Support informatique", "contact": "RSSI",
     "standards": ["ISO 27001", "ISO 9001"], "level": 0.6,
     "audits": [("stage1", ["ISO 27001"], "2026-12-10", 0.72)], "agents": ["mission"], "validate": 5, "close": 0.2, "trained": 2},
    {"name": "SolarTech Énergies (démo)", "sector": "Installation photovoltaïque", "size": "45",
     "activities": "Étude de site, Dimensionnement, Installation, Mise en service, Maintenance", "contact": "Gérant",
     "standards": ["ISO 9001", "ISO 45001", "ISO 14001"], "level": 0.35,
     "audits": [], "agents": ["qualite"], "validate": 0, "close": 0.0, "trained": 0},
    {"name": "Tannerie Cuirs de Sfax (démo)", "sector": "Tannerie et finissage du cuir", "size": "120",
     "activities": "Reverdissage, Tannage, Teinture, Finissage, Traitement des effluents", "contact": "Responsable environnement",
     "standards": ["ISO 14001", "ISO 45001"], "level": 0.5,
     "audits": [("blanc", ["ISO 14001"], "2026-11-21", 0.58)], "agents": ["mission"], "validate": 3, "close": 0.1, "trained": 1},
    {"name": "Minoterie Blé d'Or Béja (démo)", "sector": "Meunerie — farines et semoules", "size": "95",
     "activities": "Réception des blés, Nettoyage, Mouture, Ensachage, Livraison", "contact": "Responsable qualité",
     "standards": ["ISO 22000", "ISO 9001"], "level": 0.75,
     "audits": [("surveillance", ["ISO 22000"], "2026-10-07", 0.85)], "agents": ["mission"], "validate": 15, "close": 0.6, "trained": 4},
    {"name": "Atlas Assurances Digital (démo)", "sector": "Assurance en ligne", "size": "140",
     "activities": "Souscription en ligne, Gestion des sinistres, Scoring par IA, Relation client", "contact": "Directeur des risques",
     "standards": ["ISO 27001", "ISO 42001"], "level": 0.55,
     "audits": [("blanc", ["ISO 42001"], "2026-11-26", 0.6)], "agents": ["preuves", "auditeur", "capa"], "validate": 0, "close": 0.0, "trained": 0},
]


def _grade(rnd: random.Random, q: float) -> tuple[str, str]:
    r = rnd.random()
    if r < q * 0.85:
        return "C", ""
    if r < q:
        return "PF", "Pratique solide, bien documentée"
    if r < q + (1 - q) * 0.55:
        return "OA", "Constat de démonstration : pratique à formaliser"
    if r < q + (1 - q) * 0.93:
        return "NCm", "Constat de démonstration : enregistrements incomplets"
    return "NCM", "Constat de démonstration : exigence non mise en œuvre"


def _agents_work(cid: int, d: dict, rnd: random.Random) -> None:
    """Lance les agents prévus, puis simule le travail du consultant : validation, actions clôturées, formations réalisées."""
    from . import agents
    std = d["standards"][0]
    for key in d["agents"]:
        rid = agents.run_sync(cid, key, std)
        r = store.get_run(rid)
        if r["status"] == "Terminé" and r["outputs"].get("gap_proposals"):
            agents.apply_proposals(cid, std, r["outputs"]["gap_proposals"])
    docs = sorted((x for x in store.list_documents(cid) if x.get("agent")), key=lambda x: x["id"])
    for x in docs[: d.get("validate", 0)]:
        store.validate_document(x["id"], f"{d['contact']} (démo)")
    acts = store.list_actions(cid, None)
    for a in acts[: int(len(acts) * d.get("close", 0))]:
        store.update_action(a["id"], {"status": "Clôturée"})
    for t in store.list_trainings(cid)[: d.get("trained", 0)]:
        store.update_training(t["id"], "Réalisée")


def run(seed: int = 7) -> None:
    rnd = random.Random(seed)
    store.init()
    existing = {c["name"] for c in store.list_clients()}
    tasks = [f"{p['phase']}|{t}" for p in engine.ROADMAP for t in p["tasks"]]
    for d in DEMO:
        if d["name"] in existing:
            continue
        c = store.create_client(d)
        for std in d["standards"]:
            store.add_project(c["id"], std)
            lvl = max(0.1, min(0.95, d["level"] + rnd.uniform(-0.08, 0.08)))
            ans = {}
            for cl in engine.clauses(std):
                r = rnd.random()
                st = "C" if r < lvl else "P" if r < lvl + 0.15 else "NC"
                ans[cl["id"]] = {"status": st, "note": ""}
            store.save_gap(c["id"], std, ans)
            store.set_progress(c["id"], std, {k: True for k in tasks[: int(len(tasks) * lvl)]})
        for atype, stds, date, q in d["audits"]:
            a = store.create_audit(c["id"], {"type": atype, "standards": stds, "date": date, "lead_auditor": "Auditeur Kapsi-Q"})
            f = {}
            for std in stds:
                for cl in engine.clauses(std):
                    g, note = _grade(rnd, q)
                    f[f"{std}|{cl['id']}"] = {"grade": g, "note": note, "evidence": "Échantillon de démonstration" if g != "C" else ""}
            store.save_findings(a["id"], f)
        if d.get("agents"):
            _agents_work(c["id"], d, rnd)
        print("Créé :", d["name"])


if __name__ == "__main__":
    run()
