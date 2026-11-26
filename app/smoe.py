"""SMOE complet (ISO 21001) : les processus de l'établissement hors Services généraux.

Chaque processus est décrit par sa fiche (finalité, pilote, entrées, sorties, activités), ses registres
(champs, statuts, délai de traitement) et ses indicateurs (formule calculée sur les registres).
Un seul moteur fait tourner tous les processus. Les registres, codes et cibles sont PROPOSÉS : chaque pilote
les valide et les adapte (le dossier de l'ISI ne décrivait que le processus GSG).
"""
from __future__ import annotations

import datetime as dt
import json
import random

from . import agents, campus, store

SCHEMA = """
CREATE TABLE IF NOT EXISTS s_records (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, process TEXT, register TEXT,
  data TEXT DEFAULT '{}', status TEXT, created_at TEXT, due TEXT, done_at TEXT, satisfied INTEGER, ticket TEXT, requester TEXT);
CREATE INDEX IF NOT EXISTS s_records_k ON s_records(client_id, process, register);
"""


def R(key, label, form, fields, statuses, done, ok=None, delay=None, guichet=None, title="", date=None):
    """Registre : champs (clé, libellé, type), statuts, statuts de clôture, statuts « réussite », délai (jours)."""
    return {"key": key, "label": label, "form": form, "fields": fields, "statuses": statuses, "done": done, "ok": ok or done[:1],
            "delay": delay, "guichet": guichet, "title": title or fields[0][0], "date": date}


def I(code, name, formula, kind, reg, freq="Semestrielle", target=90, lower=False, **kw):
    return {"code": code, "name": name, "formula": formula, "kind": kind, "reg": reg, "freq": freq, "target": target, "lower": lower, **kw}


N, T, D, B = "number", "text", "date", "bool"
S = lambda *o: "select:" + "|".join(o)

PROCESSES = {
    "DIR": {"name": "Pilotage et stratégie de l'établissement", "kind": "Management", "pilot": "Directeur", "clauses": "4, 5, 6, 9.3",
            "purpose": "Définir la politique et les objectifs de l'établissement, maîtriser les risques et décider en revue de direction.",
            "inputs": ["Orientations du ministère et de l'université", "Besoins des apprenants et des parties intéressées", "Résultats des processus et des audits"],
            "outputs": ["Politique et objectifs qualité", "Plan stratégique", "Décisions de revue de direction", "Registre des risques"],
            "activities": ["Analyser le contexte et les parties intéressées", "Fixer la politique et les objectifs", "Évaluer les risques et opportunités", "Tenir la revue de direction et suivre ses décisions"],
            "registers": [
                R("objectifs", "Objectifs qualité de l'établissement", "DIR-FR-01", [("objectif", "Objectif", T), ("processus", "Processus", T), ("cible", "Cible", T), ("echeance", "Échéance", D)],
                  ["En cours", "Atteint", "Non atteint"], ["Atteint", "Non atteint"], ["Atteint"]),
                R("revues", "Revues de direction", "DIR-PV-01", [("date", "Date prévue", D), ("participants", "Participants", N), ("decisions", "Décisions prises", N)],
                  ["Planifiée", "Tenue", "Reportée"], ["Tenue", "Reportée"], ["Tenue"], title="date"),
                R("parties", "Parties intéressées", "DIR-FR-02", [("partie", "Partie intéressée", T), ("attentes", "Besoins et attentes", T), ("surveillance", "Moyen de surveillance", T)],
                  ["Identifiée", "Revue"], ["Revue"]),
                R("risques", "Risques et opportunités", "DIR-FR-03", [("risque", "Risque ou opportunité", T), ("processus", "Processus", T), ("gravite", "Gravité (1-4)", N), ("probabilite", "Probabilité (1-4)", N), ("action", "Action", T)],
                  ["Ouvert", "Maîtrisé"], ["Maîtrisé"]),
            ],
            "indicators": [I("DIR-1", "Taux d'atteinte des objectifs qualité", "Objectifs atteints / objectifs échus × 100", "status_ratio", "objectifs", "Annuelle", 80, num=["Atteint"], den=["Atteint", "Non atteint"]),
                           I("DIR-2", "Taux de tenue des revues de direction planifiées", "Revues tenues / revues prévues × 100", "status_ratio", "revues", "Annuelle", 100, num=["Tenue"], den=["Tenue", "Reportée"]),
                           I("DIR-3", "Taux de risques critiques maîtrisés", "Risques critiques maîtrisés / risques critiques × 100", "status_ratio", "risques", "Semestrielle", 80, num=["Maîtrisé"], den=None, where=("crit", 9))]},
    "PAC": {"name": "Amélioration continue", "kind": "Management", "pilot": "RSMOE", "clauses": "9.1, 9.2, 10",
            "purpose": "Mesurer la satisfaction, auditer le système et traiter les non-conformités pour améliorer en continu.",
            "inputs": ["Programme d'audit", "Réclamations et non-conformités", "Résultats des enquêtes", "Indicateurs des processus"],
            "outputs": ["Rapports d'audit", "Actions correctives", "Analyses de satisfaction", "Bilan qualité pour la revue de direction"],
            "activities": ["Planifier et réaliser les audits internes", "Enregistrer et traiter les non-conformités", "Mener les enquêtes de satisfaction", "Suivre l'efficacité des actions"],
            "registers": [
                R("audits", "Programme d'audits internes", "PAC-PG-01", [("processus", "Processus audité", T), ("date", "Date prévue", D), ("auditeur", "Auditeur", T), ("constats", "Non-conformités relevées", N)],
                  ["Planifié", "Réalisé", "Annulé"], ["Réalisé", "Annulé"], ["Réalisé"]),
                R("nc", "Non-conformités", "PAC-FR-01", [("source", "Source", S("Audit", "Réclamation", "Indicateur", "Constat interne")), ("processus", "Processus", T), ("description", "Description", T)],
                  ["Ouverte", "Traitée", "Clôturée"], ["Clôturée"], ["Clôturée"], delay=30, title="description"),
                R("enquetes", "Enquêtes de satisfaction", "PAC-FR-02", [("population", "Population", S("Apprenants", "Enseignants", "Personnel", "Employeurs", "Parents")), ("periode", "Période", T), ("repondants", "Répondants", N), ("satisfaits", "Satisfaits", N)],
                  ["Lancée", "Analysée"], ["Analysée"], title="population"),
            ],
            "indicators": [I("PAC-2", "Taux de réalisation du programme d'audit interne", "Audits réalisés / audits programmés échus × 100", "status_ratio", "audits", "Annuelle", 100, num=["Réalisé"], den=["Réalisé", "Annulé", "Planifié"], due_only=True),
                           I("PAC-3", "Taux de satisfaction des apprenants et des parties intéressées", "Satisfaits / répondants × 100", "sum_ratio", "enquetes", "Annuelle", 75, num="satisfaits", den="repondants"),
                           I("PAC-4", "Taux de non-conformités clôturées dans les délais", "NC clôturées dans le délai / NC × 100", "in_time", "nc", "Semestrielle", 80)]},
    "PED-04": {"name": "Gestion des activités pédagogiques", "kind": "Réalisation", "pilot": "Directeur des études", "clauses": "8.2, 8.3, 8.5, 7.1.6",
               "purpose": "Concevoir, organiser et délivrer les enseignements conformément aux programmes, et évaluer leur qualité.",
               "inputs": ["Programmes habilités", "Emplois du temps", "Ressources pédagogiques et enseignants", "Évaluations des apprenants"],
               "outputs": ["Enseignements réalisés", "Syllabus validés", "Évaluation des enseignements", "Plan de rattrapage"],
               "activities": ["Établir les emplois du temps", "Valider les syllabus des modules", "Suivre la réalisation des séances et les rattrapages", "Évaluer les enseignements par les apprenants"],
               "registers": [
                   R("seances", "Réalisation des séances (cahiers de textes)", "PED-FR-01", [("module", "Module", T), ("niveau", "Niveau", T), ("enseignant", "Enseignant", T), ("programmees", "Séances programmées", N), ("realisees", "Séances réalisées", N)],
                     ["En cours", "Clôturé"], ["Clôturé"]),
                   R("syllabus", "Syllabus des modules", "PED-FR-02", [("module", "Module", T), ("niveau", "Niveau", T), ("responsable", "Responsable", T)],
                     ["Brouillon", "Soumis", "Validé"], ["Validé"]),
                   R("rattrapages", "Absences et rattrapages", "PED-FR-03", [("module", "Module", T), ("date", "Date de la séance", D), ("motif", "Motif", T)],
                     ["À rattraper", "Rattrapée", "Non rattrapée"], ["Rattrapée", "Non rattrapée"], ["Rattrapée"], delay=21),
                   R("evaluations", "Évaluation des enseignements", "PED-FR-04", [("module", "Module", T), ("repondants", "Répondants", N), ("satisfaits", "Satisfaits", N)],
                     ["Lancée", "Analysée"], ["Analysée"]),
               ],
               "indicators": [I("PED-1", "Taux de réalisation des séances programmées", "Séances réalisées / séances programmées × 100", "sum_ratio", "seances", target=95, num="realisees", den="programmees"),
                              I("PED-2", "Satisfaction des apprenants sur les enseignements", "Satisfaits / répondants × 100", "sum_ratio", "evaluations", target=75, num="satisfaits", den="repondants"),
                              I("PED-3", "Taux de syllabus validés", "Syllabus validés / modules × 100", "status_ratio", "syllabus", "Annuelle", 100, num=["Validé"], den=None),
                              I("PED-4", "Taux de séances rattrapées dans les 3 semaines", "Rattrapages dans le délai / absences × 100", "in_time", "rattrapages", target=90)]},
    "GSP-05": {"name": "Stages et projets de fin d'études", "kind": "Réalisation", "pilot": "Responsable des stages", "clauses": "8.5, 8.4",
               "purpose": "Placer chaque apprenant en stage et conduire les projets de fin d'études jusqu'à la soutenance dans les délais.",
               "inputs": ["Liste des apprenants concernés", "Offres des entreprises partenaires", "Demandes de convention"],
               "outputs": ["Conventions signées", "Soutenances réalisées", "Évaluations des stagiaires par les entreprises"],
               "activities": ["Délivrer les conventions de stage", "Suivre le placement des apprenants", "Affecter encadrants et sujets de PFE", "Planifier et tenir les soutenances"],
               "registers": [
                   R("conventions", "Demandes de convention de stage", "GSP-FR-01", [("etudiant", "Étudiant", T), ("niveau", "Niveau", T), ("entreprise", "Entreprise", T), ("type", "Type de stage", S("Initiation", "Perfectionnement", "PFE"))],
                     ["Demandée", "Signée", "Refusée"], ["Signée", "Refusée"], ["Signée"], delay=5, guichet="Convention de stage", title="entreprise"),
                   R("pfe", "Projets de fin d'études", "GSP-FR-02", [("etudiant", "Étudiant", T), ("sujet", "Sujet", T), ("encadrant", "Encadrant", T), ("prevue", "Soutenance prévue", D), ("soutenance", "Date de soutenance", D)],
                     ["Affecté", "En cours", "Soutenu", "Reporté"], ["Soutenu", "Reporté"], ["Soutenu"], title="sujet"),
                   R("placement", "Placement en stage par promotion", "GSP-FR-03", [("promotion", "Promotion", T), ("concernes", "Apprenants concernés", N), ("places", "Apprenants placés", N)],
                     ["En cours", "Clôturé"], ["Clôturé"]),
               ],
               "indicators": [I("GSP-1", "Taux d'apprenants placés en stage", "Apprenants placés / apprenants concernés × 100", "sum_ratio", "placement", "Annuelle", 90, num="places", den="concernes"),
                              I("GSP-2", "Taux de soutenances de PFE dans les délais", "Soutenances à la date prévue / PFE soutenus ou reportés × 100", "date_le", "pfe", "Annuelle", 90, a="soutenance", b="prevue"),
                              I("GSP-3", "Taux de conventions délivrées sous 5 jours", "Conventions signées dans le délai / demandes × 100", "in_time", "conventions", target=90)]},
    "EXD-06": {"name": "Examens et délibérations", "kind": "Réalisation", "pilot": "Directeur des études", "clauses": "8.5.1, 8.6, 8.7",
               "purpose": "Organiser les examens, délibérer et publier les résultats dans les délais, et traiter les réclamations sur les notes.",
               "inputs": ["Calendrier des examens", "Sujets et copies", "Notes des enseignants"],
               "outputs": ["PV de délibération", "Résultats publiés", "Réponses aux réclamations sur les notes"],
               "activities": ["Planifier les sessions", "Organiser surveillance et correction", "Délibérer et publier les résultats", "Traiter les réclamations sur les notes"],
               "registers": [
                   R("sessions", "Sessions d'examens et publication des résultats", "EXD-FR-01", [("session", "Session", T), ("niveau", "Niveau", T), ("dernier_examen", "Date du dernier examen", D), ("publication", "Date de publication", D), ("inscrits", "Inscrits", N), ("admis", "Admis", N)],
                     ["Planifiée", "Délibérée", "Publiée"], ["Publiée"], title="session"),
                   R("reclamations_notes", "Réclamations sur les notes", "EXD-FR-02", [("etudiant", "Étudiant", T), ("module", "Module", T), ("motif", "Motif", T)],
                     ["Déposée", "Traitée", "Rejetée"], ["Traitée", "Rejetée"], ["Traitée", "Rejetée"], delay=7, guichet="Réclamation sur une note", title="module"),
               ],
               "indicators": [I("EXD-1", "Délai moyen de publication des résultats (jours)", "Moyenne (date de publication − date du dernier examen)", "avg_days", "sessions", target=15, lower=True, a="publication", b="dernier_examen"),
                              I("EXD-2", "Taux de réclamations sur les notes traitées dans les délais", "Réclamations traitées sous 7 jours / réclamations × 100", "in_time", "reclamations_notes", target=90),
                              I("EXD-3", "Taux de réussite", "Admis / inscrits × 100", "sum_ratio", "sessions", target=80, num="admis", den="inscrits")]},
    "GSA-07": {"name": "Scolarité", "kind": "Réalisation", "pilot": "Secrétaire général", "clauses": "8.5, 8.5.3, 7.5",
               "purpose": "Inscrire les apprenants et leur délivrer leurs documents de scolarité rapidement et sans erreur.",
               "inputs": ["Dossiers d'inscription", "Demandes de documents", "Résultats publiés"],
               "outputs": ["Apprenants inscrits", "Attestations, relevés et diplômes délivrés", "Dossiers archivés"],
               "activities": ["Inscrire et réinscrire", "Délivrer attestations et relevés", "Préparer les diplômes", "Archiver les dossiers"],
               "registers": [
                   R("documents", "Demandes de documents de scolarité", "GSA-FR-01", [("etudiant", "Étudiant", T), ("document", "Document", S("Attestation d'inscription", "Attestation de présence", "Relevé de notes", "Attestation de réussite", "Diplôme")), ("niveau", "Niveau", T)],
                     ["Demandée", "Prête", "Remise"], ["Remise"], ["Remise"], delay=3, guichet="Attestation ou relevé de notes", title="document"),
                   R("inscriptions", "Inscriptions par niveau", "GSA-FR-02", [("annee", "Année universitaire", T), ("niveau", "Niveau", T), ("prevus", "Places prévues", N), ("inscrits", "Inscrits", N)],
                     ["Ouverte", "Clôturée"], ["Clôturée"], title="niveau"),
               ],
               "indicators": [I("GSA-1", "Délai moyen de délivrance des documents (jours)", "Moyenne (date de remise − date de demande)", "avg_days", "documents", target=3, lower=True),
                              I("GSA-2", "Taux de documents remis sous 3 jours", "Documents remis dans le délai / demandes × 100", "in_time", "documents", target=90)]},
    "GRH-08": {"name": "Ressources humaines et compétences", "kind": "Support", "pilot": "Secrétaire général", "clauses": "7.1.2, 7.2, 7.3",
               "purpose": "Disposer d'un personnel compétent, formé et sensibilisé.",
               "inputs": ["Fiches de poste", "Besoins en formation", "Évaluations du personnel"],
               "outputs": ["Plan de formation réalisé", "Entretiens d'évaluation", "Compétences à jour"],
               "activities": ["Tenir les fiches de poste", "Recenser les besoins et planifier les formations", "Évaluer les compétences", "Sensibiliser au SMOE"],
               "registers": [
                   R("formations", "Plan de formation du personnel", "GRH-FR-01", [("theme", "Thème", T), ("population", "Population", T), ("date", "Date prévue", D), ("participants", "Participants", N)],
                     ["Planifiée", "Réalisée", "Annulée"], ["Réalisée", "Annulée"], ["Réalisée"], title="theme"),
                   R("entretiens", "Entretiens d'évaluation des compétences", "GRH-FR-02", [("agent", "Agent", T), ("poste", "Poste", T), ("date", "Date prévue", D)],
                     ["Planifié", "Réalisé"], ["Réalisé"], title="poste"),
                   R("postes", "Fiches de poste", "GRH-FR-03", [("poste", "Poste", T), ("service", "Service", T)], ["Brouillon", "Validée"], ["Validée"]),
               ],
               "indicators": [I("GRH-1", "Taux de réalisation du plan de formation du personnel", "Formations réalisées / formations planifiées échues × 100", "status_ratio", "formations", "Annuelle", 80, num=["Réalisée"], den=["Réalisée", "Annulée", "Planifiée"], due_only=True),
                              I("GRH-2", "Taux d'entretiens d'évaluation réalisés", "Entretiens réalisés / entretiens prévus × 100", "status_ratio", "entretiens", "Annuelle", 90, num=["Réalisé"], den=None),
                              I("GRH-3", "Taux de fiches de poste validées", "Fiches validées / postes × 100", "status_ratio", "postes", "Annuelle", 100, num=["Validée"], den=None)]},
    "GVU-10": {"name": "Vie universitaire", "kind": "Support", "pilot": "Responsable vie universitaire", "clauses": "7.1.4, 8.5.4",
               "purpose": "Offrir aux apprenants un environnement d'accueil, d'activités et d'accompagnement.",
               "inputs": ["Demandes des clubs", "Calendrier universitaire", "Besoins des apprenants"],
               "outputs": ["Activités et événements réalisés", "Clubs actifs", "Accueil des nouveaux apprenants"],
               "activities": ["Accompagner les clubs", "Instruire les demandes d'activité", "Organiser l'accueil et les événements", "Mesurer la participation"],
               "registers": [
                   R("activites", "Activités et événements", "GVU-FR-01", [("titre", "Activité", T), ("club", "Club ou organisateur", T), ("date", "Date", D), ("vises", "Participants visés", N), ("participants", "Participants", N)],
                     ["Demandée", "Autorisée", "Réalisée", "Refusée"], ["Réalisée", "Refusée"], ["Réalisée"], delay=7, guichet="Demande d'activité de club", title="titre"),
                   R("clubs", "Clubs", "GVU-FR-02", [("club", "Club", T), ("encadrant", "Encadrant", T), ("membres", "Membres", N)], ["Actif", "Inactif"], ["Actif", "Inactif"], ["Actif"]),
               ],
               "indicators": [I("GVU-1", "Taux de participation aux activités", "Participants / participants visés × 100", "sum_ratio", "activites", "Annuelle", 70, num="participants", den="vises"),
                              I("GVU-2", "Taux de clubs actifs", "Clubs actifs / clubs × 100", "status_ratio", "clubs", "Annuelle", 80, num=["Actif"], den=None)]},
    "GAF-11": {"name": "Finances et achats", "kind": "Support", "pilot": "Secrétaire général", "clauses": "7.1.1, 8.4",
               "purpose": "Exécuter le budget et acheter auprès de fournisseurs évalués, dans les délais.",
               "inputs": ["Budget voté", "Demandes d'achat des services", "Offres des fournisseurs"],
               "outputs": ["Budget exécuté", "Achats réceptionnés", "Fournisseurs évalués"],
               "activities": ["Suivre l'exécution budgétaire", "Traiter les demandes d'achat", "Réceptionner et contrôler", "Évaluer les fournisseurs"],
               "registers": [
                   R("budget", "Exécution budgétaire", "GAF-FR-01", [("rubrique", "Rubrique", T), ("budget", "Budget (TND)", N), ("engage", "Engagé (TND)", N)], ["Ouvert", "Clôturé"], ["Clôturé"]),
                   R("achats", "Demandes d'achat", "GAF-FR-02", [("objet", "Objet", T), ("service", "Service demandeur", T), ("fournisseur", "Fournisseur", T), ("montant", "Montant (TND)", N)],
                     ["Demandé", "Commandé", "Réceptionné", "Annulé"], ["Réceptionné", "Annulé"], ["Réceptionné"], delay=45, title="objet"),
                   R("fournisseurs", "Évaluation des fournisseurs", "GAF-FR-03", [("fournisseur", "Fournisseur", T), ("note", "Note /20", N)], ["Retenu", "À surveiller", "Écarté"], ["Retenu", "À surveiller", "Écarté"], ["Retenu"]),
               ],
               "indicators": [I("GAF-1", "Taux d'exécution du budget", "Engagé / budget × 100", "sum_ratio", "budget", "Annuelle", 90, num="engage", den="budget"),
                              I("GAF-2", "Taux d'achats réceptionnés dans les délais", "Achats réceptionnés sous 45 jours / achats × 100", "in_time", "achats", target=85),
                              I("GAF-3", "Taux de fournisseurs retenus à l'évaluation", "Fournisseurs retenus / fournisseurs évalués × 100", "status_ratio", "fournisseurs", "Annuelle", 80, num=["Retenu"], den=None)]},
}

def _hook_campus():
    keep = [x for x in campus.INDICATORS if x[0] == "GSG" or x[1] == "PAC-1"]
    campus.INDICATORS[:] = keep + indicators()
    campus.LOWER_IS_BETTER.clear(); campus.LOWER_IS_BETTER.update(LOWER)


GUICHET = {f"smoe:{p}:{r['key']}": (r["guichet"], p, r) for p, d in PROCESSES.items() for r in d["registers"] if r.get("guichet")}


def init() -> None:
    with store.conn() as c:
        c.executescript(SCHEMA)


def reg(process: str, key: str) -> dict:
    p = PROCESSES.get(process)
    r = next((x for x in (p or {}).get("registers", []) if x["key"] == key), None)
    if not r:
        raise ValueError("Registre inconnu")
    return r


def _row(r: dict) -> dict:
    r["data"] = json.loads(r["data"] or "{}")
    rg = reg(r["process"], r["register"])
    r["title"] = str(r["data"].get(rg["title"]) or rg["label"])
    r["late"] = bool(r["due"] and r["status"] not in rg["done"] and r["due"] < dt.date.today().isoformat()) or \
        bool(r["due"] and r["done_at"] and r["done_at"][:10] > r["due"] and r["status"] in rg["done"])
    return r


def add(cid: int, process: str, register: str, data: dict, status: str | None = None, now: str | None = None,
        requester: str = "", ticket: str | None = None) -> dict:
    rg = reg(process, register)
    clean = {}
    for k, _, typ in rg["fields"]:
        v = data.get(k)
        if v in (None, ""):
            continue
        if typ == N:
            try:
                v = float(v)
                v = int(v) if v.is_integer() else v
            except (TypeError, ValueError):
                raise ValueError(f"Valeur numérique attendue pour « {k} »")
        elif typ.startswith("select:") and v not in typ[7:].split("|"):
            raise ValueError(f"Valeur non prévue pour « {k} »")
        clean[k] = str(v)[:300] if isinstance(v, str) else v
    st = status or rg["statuses"][0]
    if st not in rg["statuses"]:
        raise ValueError("Statut inconnu")
    now = now or campus._now()
    due = (campus._d(now) + dt.timedelta(days=rg["delay"])).strftime("%Y-%m-%d") if rg["delay"] else None
    rid = store._exec("INSERT INTO s_records(client_id,process,register,data,status,created_at,due,ticket,requester) VALUES (?,?,?,?,?,?,?,?,?)",
                      (cid, process, register, json.dumps(clean, ensure_ascii=False), st, now, due, ticket, requester[:120]))
    if st in rg["done"]:
        store._exec("UPDATE s_records SET done_at=? WHERE id=?", (now, rid))
    return get(rid)


def get(rid: int) -> dict | None:
    r = store._rows("SELECT * FROM s_records WHERE id=?", (rid,))
    return _row(r[0]) if r else None


def find_ticket(cid: int, ticket: str) -> dict | None:
    r = store._rows("SELECT * FROM s_records WHERE client_id=? AND ticket=?", (cid, ticket.strip().upper()))
    return _row(r[0]) if r else None


def update(rid: int, ch: dict, now: str | None = None) -> dict:
    r = get(rid)
    if not r:
        raise KeyError(rid)
    rg = reg(r["process"], r["register"])
    now = now or campus._now()
    if "data" in ch:
        merged = {**r["data"], **(ch["data"] or {})}
        for k, _, typ in rg["fields"]:
            if typ == N and merged.get(k) not in (None, ""):
                try:
                    merged[k] = float(merged[k]); merged[k] = int(merged[k]) if merged[k].is_integer() else merged[k]
                except (TypeError, ValueError):
                    raise ValueError(f"Valeur numérique attendue pour « {k} »")
        store._exec("UPDATE s_records SET data=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), rid))
    st = ch.get("status")
    if st:
        if st not in rg["statuses"]:
            raise ValueError("Statut inconnu")
        done_at = now if st in rg["done"] and not r["done_at"] else (r["done_at"] if st in rg["done"] else None)
        store._exec("UPDATE s_records SET status=?, done_at=? WHERE id=?", (st, done_at, rid))
    if "satisfied" in ch:
        store._exec("UPDATE s_records SET satisfied=? WHERE id=?", (1 if ch["satisfied"] else 0, rid))
    return get(rid)


def records(cid: int, process: str, register: str | None = None, limit: int = 500) -> list[dict]:
    q, a = "SELECT * FROM s_records WHERE client_id=? AND process=?", [cid, process]
    if register:
        q += " AND register=?"; a.append(register)
    return [_row(r) for r in store._rows(q + " ORDER BY id DESC LIMIT ?", (*a, limit))]


# ------------------------------------------------------------------ indicateurs
def indicators() -> list[tuple]:
    """Format campus.INDICATORS : (processus, code, nom, formule, fréquence, cible, source)."""
    out = []
    for p, d in PROCESSES.items():
        for i in d["indicators"]:
            rg = reg(p, i["reg"])
            out.append((p, i["code"], i["name"], i["formula"], i["freq"], i["target"], f"{rg['label']} ({rg['form']})"))
    return out


LOWER = {i["code"] for d in PROCESSES.values() for i in d["indicators"] if i["lower"]}
_IND = {i["code"]: (p, i) for p, d in PROCESSES.items() for i in d["indicators"]}


def value(cid: int, code: str, start: str, end: str) -> tuple[float | None, str] | None:
    """Valeur calculée sur les registres de la période, ou None s'il n'y a aucune donnée."""
    if code not in _IND:
        return None
    p, i = _IND[code]
    rg = reg(p, i["reg"])
    rows = [_row(r) for r in store._rows("SELECT * FROM s_records WHERE client_id=? AND process=? AND register=? AND created_at BETWEEN ? AND ?",
                                         (cid, p, i["reg"], start, end + " 23:59"))]
    if not rows:
        return None
    num = lambda r, k: float(r["data"].get(k) or 0)
    today = dt.date.today().isoformat()
    k = i["kind"]
    if k == "sum_ratio":
        n, d = sum(num(r, i["num"]) for r in rows), sum(num(r, i["den"]) for r in rows)
        return (round(100 * n / d, 1) if d else None), f"{n:g} / {d:g}"
    if k == "status_ratio":
        L = rows
        if i.get("where"):
            L = [r for r in L if num(r, "gravite") * num(r, "probabilite") >= i["where"][1]]
        if i.get("due_only"):
            L = [r for r in L if r["status"] in rg["done"] or (r["data"].get("date") or "9") < today]
        if i["den"]:
            L = [r for r in L if r["status"] in i["den"]]
        n = [r for r in L if r["status"] in i["num"]]
        return (round(100 * len(n) / len(L), 1) if L else None), f"{len(n)}/{len(L)}"
    if k == "in_time":
        L = [r for r in rows if r["status"] in rg["done"] or (r["due"] and r["due"] < today)]
        n = [r for r in L if r["status"] in rg["ok"] and r["done_at"] and r["done_at"][:10] <= (r["due"] or "9") and r["satisfied"] != 0]
        return (round(100 * len(n) / len(L), 1) if L else None), f"{len(n)}/{len(L)} dans le délai"
    if k == "avg_days":
        a, b = i.get("a"), i.get("b")
        ds = []
        for r in rows:
            x = campus._d(r["data"].get(a)) if a else campus._d(r["done_at"])
            y = campus._d(r["data"].get(b)) if b else campus._d(r["created_at"])
            if x and y and (a or r["status"] in rg["done"]):
                ds.append((x - y).total_seconds() / 86400)
        return (round(sum(ds) / len(ds), 1) if ds else None), f"moyenne sur {len(ds)}"
    if k == "date_le":
        L = [r for r in rows if r["status"] in rg["done"]]
        n = [r for r in L if r["status"] in rg["ok"] and (r["data"].get(i["a"]) or "9") <= (r["data"].get(i["b"]) or "")]
        return (round(100 * len(n) / len(L), 1) if L else None), f"{len(n)}/{len(L)}"
    return None


def overview(cid: int) -> list[dict]:
    k = {i["code"]: i for i in campus.compute(cid)["indicators"]}
    out = []
    for p, d in PROCESSES.items():
        regs = []
        for r in d["registers"]:
            rs = records(cid, p, r["key"], 5000)
            regs.append({"key": r["key"], "label": r["label"], "form": r["form"], "n": len(rs), "open": sum(1 for x in rs if x["status"] not in r["done"]),
                         "late": sum(1 for x in rs if x["late"] and x["status"] not in r["done"])})
        inds = [k[i["code"]] for i in d["indicators"] if i["code"] in k]
        out.append({"code": p, **{x: d[x] for x in ("name", "kind", "pilot", "clauses", "purpose", "inputs", "outputs", "activities")},
                    "registers": regs, "indicators": inds})
    return out


def meta() -> dict:
    return {p: {**{x: d[x] for x in ("name", "kind", "pilot", "clauses", "purpose", "inputs", "outputs", "activities")},
                "registers": [{k: r[k] for k in ("key", "label", "form", "fields", "statuses", "done", "delay", "guichet", "title")} for r in d["registers"]],
                "indicators": [{k: i[k] for k in ("code", "name", "formula", "freq", "target", "lower")} for i in d["indicators"]]} for p, d in PROCESSES.items()}


_hook_campus()


# ------------------------------------------------------------------ agents
def _proc_doc(r, p, d, k):
    regs = d["registers"]
    secs = [{"heading": "Finalité", "paragraphs": [d["purpose"]]},
            {"heading": "Identification", "table": {"columns": ["Rubrique", "Contenu"], "rows": [["Code", p], ["Type", f"Processus de {d['kind'].lower()}"], ["Pilote", d["pilot"]], ["Exigences ISO 21001", d["clauses"]]]}},
            {"heading": "Éléments d'entrée", "bullets": d["inputs"]}, {"heading": "Éléments de sortie", "bullets": d["outputs"]},
            {"heading": "Activités", "bullets": d["activities"]},
            {"heading": "Enregistrements", "table": {"columns": ["Code", "Registre", "Délai de traitement"], "rows": [[x["form"], x["label"], f"{x['delay']} jours" if x["delay"] else "—"] for x in regs]}},
            {"heading": "Indicateurs", "table": {"columns": ["Code", "Indicateur", "Formule", "Fréquence", "Cible"], "rows": [[i["code"], i["name"], i["formula"], i["freq"], f"{i['target']}{' j' if i['lower'] else ' %'}"] for i in d["indicators"]]}}]
    return r.doc({"kind": "fiche_processus", "title": f"Fiche processus {p} — {d['name']}", "client": r.client["name"], "date": agents._today(), "ai": False, "standard": "ISO 21001",
                  "footer": "Fiche proposée par Kapsi Campus à partir des exigences ISO 21001 : à valider par le pilote et le RSMOE.", "sections": secs})


def agent_fiches(r) -> None:
    """Rédige la fiche de chaque processus du SMOE (finalité, entrées, sorties, activités, enregistrements, indicateurs)."""
    for p, d in PROCESSES.items():
        _proc_doc(r, p, d, None)
    r.log(f"{len(PROCESSES)} fiches processus rédigées (plus la fiche GSG existante de l'établissement).", "ok")


def agent_revue_processus(r) -> None:
    """Revue de chaque processus : registres, retards, indicateurs, actions ouvertes sur les écarts."""
    ov = overview(r.cid)
    existing = {(a["clause"], a["status"]) for a in store.list_actions(r.cid, "ISO 21001")}
    opened = 0
    for o in ov:
        late = sum(x["late"] for x in o["registers"])
        ko = [i for i in o["indicators"] if i["ok"] is False]
        for i in ko:
            if (i["code"], "Ouverte") in existing or (i["code"], "En cours") in existing:
                continue
            store.add_action(r.cid, {"standard": "ISO 21001", "source": f"Indicateur {i['code']}", "clause": i["code"],
                                     "finding": f"{i['name']} : {i['value']} pour une cible de {i['target']}.", "cause": "À analyser avec le pilote du processus (5 pourquoi).",
                                     "action": "Plan d'amélioration à définir en revue de processus.", "owner": o["pilot"], "due": agents._today(30), "status": "Ouverte"})
            opened += 1
        r.log(f"{o['code']} · {o['name']} : {sum(x['n'] for x in o['registers'])} enregistrement(s), {late} en retard, {len(ko)} indicateur(s) sous la cible.", "warn" if late or ko else "ok")
        late_rows = []
        for rg in PROCESSES[o["code"]]["registers"]:
            late_rows += [[rg["label"], x["title"], x["created_at"][:10], x["due"] or "", x["status"]] for x in records(r.cid, o["code"], rg["key"], 2000) if x["late"] and x["status"] not in rg["done"]][:15]
        r.doc({"kind": "revue_processus", "title": f"Revue du processus {o['code']} — {r.client['name']}", "client": r.client["name"], "date": agents._today(), "ai": False, "standard": "ISO 21001",
               "footer": "Revue préparée par un agent Kapsi Campus, à tenir et valider par le pilote du processus.",
               "sections": [{"heading": "Processus", "paragraphs": [f"{o['name']} · pilote : {o['pilot']}. {o['purpose']}"]},
                            {"heading": "Activité des registres", "table": {"columns": ["Registre", "Enregistrements", "Ouverts", "En retard"], "rows": [[x["label"], x["n"], x["open"], x["late"]] for x in o["registers"]]}},
                            {"heading": "Indicateurs", "table": {"columns": ["Code", "Indicateur", "Valeur", "Cible", "Statut"],
                                                                 "rows": [[i["code"], i["name"], "—" if i["value"] is None else i["value"], i["target"], "Atteint" if i["ok"] else "Sous la cible" if i["ok"] is False else "À mesurer"] for i in o["indicators"]]}},
                            {"heading": "Dossiers en retard", "table": {"columns": ["Registre", "Objet", "Créé le", "Échéance", "Statut"], "rows": late_rows}} if late_rows else {"heading": "Dossiers en retard", "paragraphs": ["Aucun."]}]})
    r.log(f"{opened} action(s) ouverte(s) sur les indicateurs sous la cible.", "ok")


def agent_revue_direction(r) -> None:
    """Prépare les éléments d'entrée de la revue de direction (ISO 21001, 9.3.2)."""
    k = campus.compute(r.cid)
    acts = store.list_actions(r.cid, None)
    ov = overview(r.cid)
    sat = [i for i in k["indicators"] if i["code"] in ("PAC-3", "PED-2", "GSG-3")]
    aud = records(r.cid, "PAC", "audits", 200)
    nc = records(r.cid, "PAC", "nc", 500)
    obj = records(r.cid, "DIR", "objectifs", 200)
    risks = [x for x in records(r.cid, "DIR", "risques", 500) if float(x["data"].get("gravite") or 0) * float(x["data"].get("probabilite") or 0) >= 9]
    fmt = lambda i: "—" if i["value"] is None else f"{i['value']}"
    r.doc({"kind": "revue_direction", "title": f"Préparation de la revue de direction — {r.client['name']}", "client": r.client["name"], "date": agents._today(), "ai": False, "standard": "ISO 21001",
           "footer": "Éléments d'entrée préparés par Kapsi Campus. Les décisions sont prises par la direction en séance.",
           "sections": [
               {"heading": "Ordre du jour (ISO 21001, 9.3.2)", "bullets": ["Suivi des décisions de la revue précédente", "Enjeux internes et externes, parties intéressées", "Satisfaction des apprenants et des parties intéressées",
                                                                          "Atteinte des objectifs", "Performance des processus", "Non-conformités et actions correctives", "Résultats d'audit", "Performance des prestataires",
                                                                          "Adéquation des ressources", "Risques et opportunités", "Opportunités d'amélioration"]},
               {"heading": "Satisfaction", "table": {"columns": ["Indicateur", "Valeur", "Cible"], "rows": [[f"{i['code']} {i['name']}", fmt(i), i["target"]] for i in sat]}},
               {"heading": "Objectifs qualité", "table": {"columns": ["Objectif", "Processus", "Cible", "Statut"], "rows": [[x["data"].get("objectif", ""), x["data"].get("processus", ""), x["data"].get("cible", ""), x["status"]] for x in obj]}} if obj else {"heading": "Objectifs qualité", "paragraphs": ["Aucun objectif enregistré : à définir."]},
               {"heading": "Performance des processus", "table": {"columns": ["Processus", "Pilote", "Indicateurs atteints", "Sous la cible", "À mesurer"],
                                                                  "rows": [[f"{o['code']} {o['name']}", o["pilot"], sum(1 for i in o["indicators"] if i["ok"]), sum(1 for i in o["indicators"] if i["ok"] is False), sum(1 for i in o["indicators"] if i["ok"] is None)] for o in ov]}},
               {"heading": "Audits et non-conformités", "bullets": [f"Audits internes : {sum(a['status'] == 'Réalisé' for a in aud)} réalisé(s) sur {len(aud)} programmé(s)",
                                                                    f"Non-conformités : {len(nc)} dont {sum(x['status'] != 'Clôturée' for x in nc)} ouverte(s)",
                                                                    f"Actions : {len(acts)} dont {sum(a['status'] != 'Clôturée' for a in acts)} ouverte(s)"]},
               {"heading": "Risques critiques (gravité × probabilité ≥ 9)", "table": {"columns": ["Risque", "Processus", "G × P", "Statut"], "rows": [[x["data"].get("risque", ""), x["data"].get("processus", ""), f"{float(x['data'].get('gravite', 0)) * float(x['data'].get('probabilite', 0)):g}", x["status"]] for x in risks]}} if risks else {"heading": "Risques critiques", "paragraphs": ["Aucun risque critique enregistré."]},
               {"heading": "Décisions à prendre", "bullets": ["Cibles des indicateurs pour l'année suivante", "Ressources pour les actions des indicateurs sous la cible", "Programme d'audit de l'année suivante", "Mise à jour des objectifs qualité"]}]})
    r.log("Dossier de revue de direction prêt (éléments d'entrée ISO 21001, 9.3.2).", "ok")


def agent_pilote_smoe(r) -> None:
    for key in ("smoe_fiches", "smoe_revue_processus", "campus_tableau", "smoe_revue_direction"):
        r.log(f"— {agents.AGENTS[key][0]} —", "step")
        agents.AGENTS[key][2](r)


agents.AGENTS.update({
    "campus_smoe": ("Pilote SMOE", "Fait tourner tout le système : fiches processus, revue de chaque processus, tableau de bord, dossier de revue de direction.", agent_pilote_smoe),
    "smoe_fiches": ("Rédacteur des fiches processus", "Rédige la fiche de chaque processus : finalité, entrées, sorties, activités, enregistrements, indicateurs.", agent_fiches),
    "smoe_revue_processus": ("Revue des processus", "Pour chaque processus : activité des registres, dossiers en retard, indicateurs ; ouvre les actions sur les écarts.", agent_revue_processus),
    "smoe_revue_direction": ("Revue de direction", "Prépare les éléments d'entrée de la revue de direction (ISO 21001, 9.3.2) à partir de tout le système.", agent_revue_direction),
})


# ------------------------------------------------------------------ démonstration
def seed_demo(cid: int, seed: int = 31) -> None:
    rnd = random.Random(seed)
    today = dt.date.today()
    day = lambda back: (today - dt.timedelta(days=back))
    ts = lambda d: dt.datetime.combine(d, dt.time(rnd.randint(8, 15), rnd.choice([0, 15, 30]))).strftime("%Y-%m-%d %H:%M")
    mods = ["Algorithmique", "Bases de données", "Réseaux", "Systèmes embarqués", "Génie logiciel", "Mathématiques discrètes", "Anglais", "Systèmes temps réel", "Sécurité informatique", "IA et apprentissage"]
    names = ["Étudiant A", "Étudiant B", "Étudiante C", "Étudiant D", "Étudiante E", "Étudiant F", "Étudiante G", "Étudiant H"]

    def closed(p, rgk, data, created, delay_ok=True, status=None, extra_days=None):
        rg = reg(p, rgk)
        rec = add(cid, p, rgk, data, now=ts(created))
        if status is None:
            return rec
        d = rg["delay"] or 3
        took = extra_days if extra_days is not None else (rnd.randint(0, max(0, d - 1)) if delay_ok else d + rnd.randint(1, 6))
        when = created + dt.timedelta(days=took)
        if when > today:
            return rec
        update(rec["id"], {"status": status}, now=ts(when))
        return rec

    # DIR
    for o, p_, c, st in [("Augmenter la satisfaction des apprenants", "PAC", "≥ 75 %", "Atteint"), ("Publier les résultats sous 15 jours", "EXD-06", "≤ 15 j", "Atteint"),
                         ("Placer 90 % des apprenants en stage", "GSP-05", "≥ 90 %", "Non atteint"), ("Délivrer les attestations sous 3 jours", "GSA-07", "≤ 3 j", "Atteint"),
                         ("Réaliser 80 % du plan de formation du personnel", "GRH-08", "≥ 80 %", "En cours"), ("Rendre 100 % des syllabus disponibles", "PED-04", "100 %", "En cours")]:
        rec = add(cid, "DIR", "objectifs", {"objectif": o, "processus": p_, "cible": c, "echeance": day(-60).isoformat()}, now=ts(day(200)))
        if st != "En cours":
            update(rec["id"], {"status": st}, now=ts(day(20)))
    rv = add(cid, "DIR", "revues", {"date": day(150).isoformat(), "participants": 9, "decisions": 7}, now=ts(day(170)))
    update(rv["id"], {"status": "Tenue"}, now=ts(day(150)))
    add(cid, "DIR", "revues", {"date": day(-20).isoformat()}, now=ts(day(10)))
    for pi_, at in [("Apprenants", "Qualité des enseignements, employabilité, services"), ("Enseignants", "Moyens pédagogiques, charge"), ("Employeurs", "Compétences des diplômés"),
                    ("Ministère et université", "Conformité, indicateurs"), ("Parents", "Information, sécurité")]:
        add(cid, "DIR", "parties", {"partie": pi_, "attentes": at, "surveillance": "Enquête annuelle"}, status="Revue", now=ts(day(180)))
    for rk, p_, g, pr, stt in [("Panne du réseau pendant les examens en ligne", "EXD-06", 4, 3, "Maîtrisé"), ("Départ d'enseignants vacataires en cours de semestre", "PED-04", 3, 3, "Ouvert"),
                               ("Retard de signature des conventions par les entreprises", "GSP-05", 3, 4, "Ouvert"), ("Perte de dossiers papier de scolarité", "GSA-07", 4, 2, "Maîtrisé"),
                               ("Partenariats industriels pour les PFE (opportunité)", "GSP-05", 2, 3, "Ouvert")]:
        add(cid, "DIR", "risques", {"risque": rk, "processus": p_, "gravite": g, "probabilite": pr, "action": "Plan de continuité et suivi"}, status=stt, now=ts(day(120)))
    # PAC
    for p_, back, st, n in [("PED-04", 140, "Réalisé", 2), ("GSA-07", 110, "Réalisé", 1), ("EXD-06", 80, "Réalisé", 3), ("GSP-05", 40, "Planifié", 0), ("GRH-08", -30, "Planifié", 0), ("GSG", 60, "Réalisé", 2)]:
        rec = add(cid, "PAC", "audits", {"processus": p_, "date": day(back).isoformat(), "auditeur": "Auditeur interne qualifié", "constats": n}, now=ts(day(200)))
        if st == "Réalisé":
            update(rec["id"], {"status": "Réalisé"}, now=ts(day(back)))
    for k in range(14):
        cr = day(rnd.randint(10, 170))
        closed("PAC", "nc", {"source": rnd.choice(["Audit", "Réclamation", "Indicateur", "Constat interne"]), "processus": rnd.choice(["PED-04", "EXD-06", "GSA-07", "GSG", "GSP-05"]),
                             "description": rnd.choice(["Syllabus non disponible", "PV de délibération non signé", "Registre non tenu à jour", "Délai de réponse dépassé", "Enregistrement manquant"])},
               cr, rnd.random() > 0.3, "Clôturée" if rnd.random() > 0.2 else None)
    for pop, n, sat in [("Apprenants", 412, 318), ("Enseignants", 58, 44), ("Personnel", 41, 30), ("Employeurs", 23, 19)]:
        add(cid, "PAC", "enquetes", {"population": pop, "periode": f"{today.year - (today.month < 9)}-{today.year + (today.month >= 9)}", "repondants": n, "satisfaits": sat}, status="Analysée", now=ts(day(90)))
    # PED
    for m in mods:
        prog = rnd.choice([21, 28, 42]); real = prog - rnd.choice([0, 0, 0, 1, 2])
        add(cid, "PED-04", "seances", {"module": m, "niveau": rnd.choice(["L1", "L2", "L3", "M1"]), "enseignant": "Enseignant", "programmees": prog, "realisees": real}, status="Clôturé", now=ts(day(40)))
        add(cid, "PED-04", "syllabus", {"module": m, "niveau": "L3", "responsable": "Responsable de module"}, status="Validé" if mods.index(m) < 9 else "Soumis", now=ts(day(160)))
        n = rnd.randint(25, 60)
        add(cid, "PED-04", "evaluations", {"module": m, "repondants": n, "satisfaits": int(n * rnd.uniform(0.66, 0.93))}, status="Analysée", now=ts(day(35)))
    for k in range(18):
        cr = day(rnd.randint(5, 150))
        closed("PED-04", "rattrapages", {"module": rnd.choice(mods), "date": cr.isoformat(), "motif": rnd.choice(["Absence enseignant", "Jour férié", "Panne de salle"])},
               cr, rnd.random() > 0.07, "Rattrapée" if rnd.random() > 0.05 else "Non rattrapée")
    # GSP
    for k in range(40):
        cr = day(rnd.randint(2, 160))
        closed("GSP-05", "conventions", {"etudiant": rnd.choice(names), "niveau": rnd.choice(["L2", "L3", "M2"]), "entreprise": rnd.choice(["Entreprise TIC", "Banque", "Opérateur télécom", "Industrie électronique", "Startup"]),
                                         "type": rnd.choice(["Initiation", "Perfectionnement", "PFE"])}, cr, rnd.random() > 0.07, "Signée" if rnd.random() > 0.05 else "Refusée")
    for k in range(24):
        prev = day(rnd.randint(-40, 150))
        stt = "Soutenu" if prev < today and rnd.random() > 0.12 else ("Reporté" if prev < today else "En cours")
        sout = prev + dt.timedelta(days=0 if rnd.random() > 0.15 else rnd.randint(7, 40))
        add(cid, "GSP-05", "pfe", {"etudiant": rnd.choice(names), "sujet": rnd.choice(["Plateforme IoT", "Détection d'intrusions par IA", "Application mobile", "Système embarqué temps réel", "Tableau de bord BI"]),
                                   "encadrant": "Encadrant universitaire", "prevue": prev.isoformat(), "soutenance": sout.isoformat() if stt == "Soutenu" else ""}, status=stt, now=ts(day(200)))
    for promo, c, pl in [("L2", 120, 112), ("L3", 110, 104), ("M2", 45, 39)]:
        add(cid, "GSP-05", "placement", {"promotion": promo, "concernes": c, "places": pl}, status="Clôturé", now=ts(day(60)))
    # EXD
    for sess, niv, last, pub, ins, adm in [("Principale S1", "L1", 120, 107, 180, 140), ("Principale S1", "L2", 118, 105, 150, 121), ("Principale S1", "L3", 117, 103, 130, 117),
                                           ("Contrôle S1", "L1", 95, 86, 49, 30), ("Principale S1", "M1", 116, 101, 60, 51)]:
        add(cid, "EXD-06", "sessions", {"session": sess, "niveau": niv, "dernier_examen": day(last).isoformat(), "publication": day(pub).isoformat(), "inscrits": ins, "admis": adm}, status="Publiée", now=ts(day(last + 20)))
    for k in range(26):
        cr = day(rnd.randint(85, 110))
        closed("EXD-06", "reclamations_notes", {"etudiant": rnd.choice(names), "module": rnd.choice(mods), "motif": "Vérification de la note"}, cr, rnd.random() > 0.12, rnd.choice(["Traitée", "Traitée", "Rejetée"]))
    # GSA
    for k in range(160):
        cr = day(rnd.randint(1, 170))
        closed("GSA-07", "documents", {"etudiant": rnd.choice(names), "document": rnd.choice(["Attestation d'inscription", "Attestation d'inscription", "Attestation de présence", "Relevé de notes", "Relevé de notes", "Attestation de réussite"]),
                                       "niveau": rnd.choice(["L1", "L2", "L3", "M1", "M2"])}, cr, rnd.random() > 0.05, "Remise" if rnd.random() > 0.04 else None)
    for niv, prev_, ins in [("L1", 200, 192), ("L2", 160, 151), ("L3", 140, 133), ("M1", 60, 57), ("M2", 50, 46)]:
        add(cid, "GSA-07", "inscriptions", {"annee": f"{today.year - (today.month < 9)}-{today.year + (today.month >= 9)}", "niveau": niv, "prevus": prev_, "inscrits": ins}, status="Clôturée", now=ts(day(70)))
    # GRH
    for th, back, st in [("Sensibilisation ISO 21001", 150, "Réalisée"), ("Accueil et qualité de service", 120, "Réalisée"), ("Outils numériques (Kapsi Campus)", 30, "Réalisée"),
                         ("Sécurité incendie", 90, "Annulée"), ("Auditeurs internes ISO 19011", 60, "Réalisée"), ("Gestion des archives", 10, "Planifiée"), ("Anglais professionnel", -40, "Planifiée")]:
        rec = add(cid, "GRH-08", "formations", {"theme": th, "population": "Personnel administratif et technique", "date": day(back).isoformat(), "participants": rnd.randint(8, 25)}, now=ts(day(200)))
        if st != "Planifiée":
            update(rec["id"], {"status": st}, now=ts(day(max(back, 1))))
    for k, poste in enumerate(["Agent de scolarité", "Agent de tirage", "Technicien informatique", "Magasinier", "Secrétaire de direction", "Agent d'accueil", "Comptable", "Archiviste", "Chauffeur", "Responsable des stages"]):
        add(cid, "GRH-08", "entretiens", {"agent": f"Agent {k + 1}", "poste": poste, "date": day(rnd.randint(-30, 120)).isoformat()}, status="Réalisé" if k < 9 else "Planifié", now=ts(day(150)))
        add(cid, "GRH-08", "postes", {"poste": poste, "service": "Secrétariat général"}, status="Validée" if k < 9 else "Brouillon", now=ts(day(180)))
    # GVU
    for club, enc, mem, st in [("Club robotique", "Enseignant", 34, "Actif"), ("Club IEEE", "Enseignant", 41, "Actif"), ("Club culturel", "Enseignant", 22, "Actif"), ("Club sportif", "Enseignant", 55, "Actif"), ("Club entrepreneuriat", "Enseignant", 9, "Inactif")]:
        add(cid, "GVU-10", "clubs", {"club": club, "encadrant": enc, "membres": mem}, status=st, now=ts(day(190)))
    for t_, club, back, vis, par in [("Journée d'accueil des nouveaux", "Vie universitaire", 80, 200, 172), ("Hackathon IA", "Club IEEE", 60, 80, 74), ("Compétition de robotique", "Club robotique", 45, 60, 41),
                                     ("Forum entreprises", "Stages", 30, 300, 250), ("Tournoi sportif", "Club sportif", 20, 120, 108), ("Soirée culturelle", "Club culturel", -10, 150, 0)]:
        cr = day(back + 15)
        rec = add(cid, "GVU-10", "activites", {"titre": t_, "club": club, "date": day(back).isoformat(), "vises": vis, "participants": par or ""}, now=ts(cr))
        if back > 0:
            update(rec["id"], {"status": "Autorisée"}, now=ts(cr + dt.timedelta(days=rnd.randint(1, 9))))
            update(rec["id"], {"status": "Réalisée"}, now=ts(day(back)))
    # GAF
    for rub, b, e in [("Fonctionnement", 420000, 371000), ("Équipement pédagogique", 260000, 198000), ("Maintenance des bâtiments", 90000, 84000), ("Vie universitaire", 40000, 31000), ("Formation du personnel", 25000, 16500)]:
        add(cid, "GAF-11", "budget", {"rubrique": rub, "budget": b, "engage": e}, now=ts(day(30)))
    for k in range(22):
        cr = day(rnd.randint(10, 170))
        closed("GAF-11", "achats", {"objet": rnd.choice(["Toners", "Postes informatiques", "Vidéoprojecteurs", "Papier", "Pièces de climatisation", "Licences logicielles"]),
                                    "service": rnd.choice(["Informatique", "Services généraux", "Scolarité", "Direction des études"]), "fournisseur": rnd.choice(["Fournisseur A", "Fournisseur B", "Fournisseur C"]),
                                    "montant": rnd.choice([800, 2400, 6500, 18000, 42000])}, cr, rnd.random() > 0.1, "Réceptionné" if rnd.random() > 0.1 else None)
    for f, n, st in [("Fournisseur A", 16, "Retenu"), ("Fournisseur B", 13, "Retenu"), ("Fournisseur C", 9, "À surveiller"), ("Fournisseur D", 15, "Retenu")]:
        add(cid, "GAF-11", "fournisseurs", {"fournisseur": f, "note": n}, status=st, now=ts(day(60)))
