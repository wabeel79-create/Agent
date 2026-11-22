"""Moteur Kapsi-Q : base de connaissances multi-normes, générateurs de livrables,
audit tierce partie, rédacteur IA. Fonctionne entièrement hors ligne ; le modèle
de langage (llm.py) ne sert qu'à enrichir les textes quand il est configuré."""
from __future__ import annotations

import datetime as dt
import json
import random
import re
from pathlib import Path

from .llm import llm

KNOW = Path(__file__).parent / "knowledge"
_load = lambda n: json.loads((KNOW / n).read_text(encoding="utf-8"))  # noqa: E731

_STD = _load("standards.json")
BACKBONE = _STD["backbone"]
STANDARDS = _STD["standards"]
ROADMAP = _STD["roadmap"]
ISO9001_DETAIL = _load("iso9001.json")["clauses"]
TRANSITION = _load("transition_2026.json")["changes"]
INTEGRATED = _load("integrated.json")

GAP_STATUS = {"C": "Conforme", "P": "Partiellement conforme", "NC": "Non conforme", "NA": "Non applicable"}
AUDIT_GRADES = {"PF": "Point fort", "C": "Conforme", "OA": "Opportunité d'amélioration",
                "NCm": "Non-conformité mineure", "NCM": "Non-conformité majeure", "NA": "Non audité / NA"}
AUDIT_TYPES = {"stage1": "Audit initial — étape 1", "stage2": "Audit initial — étape 2 (certification)",
               "surveillance": "Audit de surveillance", "recertification": "Audit de renouvellement",
               "blanc": "Audit à blanc (pré-certification)"}


# ------------------------------------------------------------ connaissances
def _ckey(cid: str) -> tuple:
    if cid.startswith("A."):
        return (100, *[int(x) for x in cid[2:].split(".")])
    return tuple(int(x) for x in cid.split("."))


def clauses(std: str) -> list[dict]:
    if std not in STANDARDS:
        raise KeyError(std)
    base = ISO9001_DETAIL if std == "ISO 9001" else BACKBONE
    out = {c["id"]: {**c, "questions": list(c["questions"]), "evidence": list(c["evidence"])} for c in base}
    for s in STANDARDS[std]["specific"]:
        if s["id"] in out:
            o = out[s["id"]]
            o["questions"] += [q for q in s["questions"] if q not in o["questions"]]
            o["evidence"] += [e for e in s["evidence"] if e not in o["evidence"]]
        else:
            out[s["id"]] = {**s, "specific": True}
    return sorted(out.values(), key=lambda c: _ckey(c["id"]))


def chapter(cid: str) -> str:
    return "Annexe A" if cid.startswith("A.") else cid.split(".")[0]


def catalog_standards() -> list[dict]:
    return [{"code": k, "label": v["label"], "system": v["system"], "color": v["color"],
             "version": v["version"], "clauses": len(clauses(k))} for k, v in STANDARDS.items()]


# ------------------------------------------------------------------ helpers
def _doc(title: str, client: dict, sections: list[dict], kind: str, std: str = "") -> dict:
    return {"kind": kind, "title": title, "standard": std, "client": client.get("name", ""),
            "date": dt.date.today().isoformat(), "sections": sections, "ai": False,
            "footer": "Projet généré par Kapsi-Q, à valider par le consultant avant diffusion."}


def _ctx(c: dict) -> str:
    return (f"{c.get('name', 'Organisme')} — secteur : {c.get('sector') or 'non précisé'} ; "
            f"effectif : {c.get('size') or '?'} ; activités : {c.get('activities') or 'non précisées'}")


def _acts(c: dict) -> list[str]:
    return [a.strip() for a in re.split(r"[,;\n]", c.get("activities") or "") if a.strip()] or ["Activité principale"]


def _enrich(doc: dict, prompt: str, fallback: str) -> str:
    if not llm.available:
        return fallback
    out = llm.generate(prompt, max_tokens=500)
    if out:
        doc["ai"] = True
        return out
    return fallback


def _std(std: str | None) -> str:
    std = std or "ISO 9001"
    if std not in STANDARDS:
        raise KeyError(std)
    return std


# --------------------------------------------------------------- livrables
def policy(c: dict, std: str = None) -> dict:
    std = _std(std); S = STANDARDS[std]
    d = _doc(f"Politique {S['focus']} — {c.get('name', '')}", c, [], "policy", std)
    base = (f"La direction de {c.get('name', 'l’organisme')} a mis en place un système de management "
            f"{S['focus']} conforme à {std}, adapté à ses activités ({c.get('activities') or c.get('sector') or ''}) "
            f"et à son contexte.")
    intro = _enrich(d, f"Rédige l'introduction (5 phrases) d'une politique {S['focus']} {std} pour : {_ctx(c)}.", base)
    d["sections"] = [
        {"heading": "Engagement de la direction", "paragraphs": [intro]},
        {"heading": "Nos engagements", "bullets": S["policy_axes"]},
        {"heading": "Mise en œuvre", "paragraphs": [
            "Ces engagements se déclinent en objectifs mesurables revus lors de chaque revue de direction. "
            "La direction fournit les ressources nécessaires et communique cette politique à tout le personnel "
            "et aux parties intéressées concernées.", "Signature de la direction : ____________   Date : ________"]}]
    return d


def process_map(c: dict, std: str = None) -> dict:
    rows = [["Management", "Pilotage stratégique et revue de direction", "Direction", "Taux d'atteinte des objectifs"],
            ["Management", "Amélioration continue et audits", "Responsable système", "Taux de clôture des actions"],
            ["Réalisation", "Commercial et revue des exigences", "Responsable commercial", "Taux de transformation"]]
    rows += [["Réalisation", a[:1].upper() + a[1:], "À désigner", "Conformité / délais"] for a in _acts(c)]
    rows += [["Réalisation", "Livraison et satisfaction client", "Responsable commercial", "Indice de satisfaction"],
             ["Support", "Achats et prestataires externes", "Responsable achats", "Note fournisseurs"],
             ["Support", "Ressources humaines et compétences", "RH", "Réalisation du plan de formation"],
             ["Support", "Infrastructure et maintenance", "Maintenance", "Disponibilité équipements"],
             ["Support", "Informations documentées", "Responsable système", "Documents à jour"]]
    return _doc(f"Cartographie des processus — {c.get('name', '')}", c, [
        {"heading": "Processus, pilotes et indicateurs", "table": {"columns": ["Type", "Processus", "Pilote", "Indicateur clé"], "rows": rows}},
        {"heading": "Interactions", "paragraphs": [
            "Entrée : exigences des clients et des parties intéressées. Sortie : satisfaction et produits/services conformes.",
            "Les processus de management pilotent la réalisation ; les processus support fournissent les ressources."]}],
        "process_map", std or "")


def procedure_documents(c: dict, std: str = None) -> dict:
    return _doc(f"Procédure — Maîtrise des informations documentées ({c.get('name', '')})", c, [
        {"heading": "1. Objet et domaine", "paragraphs": ["Règles de création, validation, diffusion, modification, conservation et élimination des documents et enregistrements du système de management."]},
        {"heading": "2. Responsabilités", "table": {"columns": ["Étape", "Responsable"], "rows": [
            ["Rédaction", "Pilote de processus"], ["Vérification", "Responsable système"],
            ["Approbation", "Direction"], ["Diffusion et archivage", "Responsable système"]]}},
        {"heading": "3. Déroulement", "bullets": [
            "Codification TYPE-PROCESSUS-NN (ex. PR-QUA-01) et indice de révision.",
            "Cartouche Rédigé / Vérifié / Approuvé ; historique des révisions.",
            "Diffusion via la liste des documents en vigueur ; retrait des versions périmées.",
            "Documents externes (normes, réglementation) identifiés et suivis.",
            "Enregistrements : durée de conservation, support, lieu et protection définis.",
            "Sauvegarde et contrôle d'accès des documents électroniques."]},
        {"heading": "4. Enregistrements associés", "bullets": ["Liste des documents en vigueur", "Tableau de conservation des enregistrements"]}],
        "procedure", std or "")


RISK_TEMPLATES = {
    "ISO 9001": (["Processus", "Risque / opportunité", "Gravité (1-4)", "Probabilité (1-4)", "Criticité", "Action", "Responsable"],
                 lambda a: [[a, f"Non-conformité produit en {a.lower()}", 3, 2, 6, "Contrôle en cours de fabrication", ""],
                            [a, f"Opportunité : réduction des délais en {a.lower()}", 2, 3, 6, "Projet d'amélioration", ""]]),
    "ISO 14001": (["Activité", "Aspect environnemental", "Impact", "Condition (N/A/U)", "Cotation", "Significatif ?", "Maîtrise"],
                  lambda a: [[a, "Consommation d'énergie", "Épuisement des ressources", "N", "", "", ""],
                             [a, "Production de déchets", "Pollution des sols", "N", "", "", ""],
                             [a, "Déversement accidentel", "Pollution des eaux", "U", "", "", ""]]),
    "ISO 45001": (["Unité de travail", "Danger", "Risque", "Gravité (1-4)", "Probabilité (1-4)", "Criticité", "Mesure (hiérarchie)"],
                  lambda a: [[a, "Machines en mouvement", "Écrasement, coupure", 4, 2, 8, "Protection collective (carters)"],
                             [a, "Manutention manuelle", "TMS", 2, 3, 6, "Aide mécanique, formation gestes et postures"],
                             [a, "Bruit", "Surdité", 3, 2, 6, "Réduction à la source, EPI"]]),
    "ISO 27001": (["Actif", "Menace", "Vulnérabilité", "C/I/D", "Impact (1-4)", "Vraisemblance (1-4)", "Traitement (mesure annexe A)"],
                  lambda a: [[f"Données de {a.lower()}", "Rançongiciel", "Sauvegardes non testées", "D", 4, 2, "A.8.13 Sauvegarde"],
                             [f"Données de {a.lower()}", "Accès non autorisé", "Droits non revus", "C", 3, 2, "A.5.18 Droits d'accès"]]),
    "ISO 22000": (["Étape", "Danger (B/C/P/A)", "Cause", "Gravité", "Probabilité", "CCP / PRPo / PRP", "Mesure de maîtrise"],
                  lambda a: [[a, "Biologique", "Contamination croisée", 3, 2, "PRPo", "Plan de nettoyage"],
                             [a, "Physique", "Corps étranger", 3, 1, "CCP", "Détecteur de métaux"]]),
}


def risk_register(c: dict, std: str = None) -> dict:
    std = _std(std)
    cols, fn = RISK_TEMPLATES.get(std, RISK_TEMPLATES["ISO 9001"])
    rows = [r for a in _acts(c) for r in fn(a)]
    names = {"ISO 14001": "Analyse environnementale (aspects et impacts)", "ISO 45001": "Évaluation des risques professionnels (DUER)",
             "ISO 27001": "Appréciation des risques de sécurité de l'information", "ISO 22000": "Analyse des dangers (HACCP)"}
    return _doc(f"{names.get(std, 'Registre des risques et opportunités')} — {c.get('name', '')}", c, [
        {"heading": "Méthode", "paragraphs": ["Cotation de 1 à 4 ; criticité = gravité × probabilité. Seuil d'action à fixer par la direction (ex. ≥ 6). "
                                              "Lignes pré-remplies à partir des activités du client : à compléter et coter en atelier."]},
        {"heading": "Registre", "table": {"columns": cols, "rows": rows}}], "risk_register", std)


def objectives(c: dict, std: str = None) -> dict:
    std = _std(std)
    ex = {"ISO 9001": [["Satisfaction client", "Indice de satisfaction", "≥ 85 %", "Semestrielle"], ["Réclamations", "Nb réclamations / 1000 livraisons", "< 5", "Mensuelle"], ["Délais", "Taux de livraison à temps", "≥ 95 %", "Mensuelle"]],
          "ISO 14001": [["Énergie", "kWh / unité produite", "-5 % / an", "Mensuelle"], ["Déchets", "Taux de valorisation", "≥ 60 %", "Trimestrielle"], ["Eau", "m³ / unité produite", "-3 % / an", "Mensuelle"]],
          "ISO 45001": [["Accidents", "Taux de fréquence", "-20 % / an", "Mensuelle"], ["Prévention", "Réalisation du plan de prévention", "≥ 90 %", "Trimestrielle"], ["Exercices", "Exercices d'évacuation réalisés", "2 / an", "Semestrielle"]],
          "ISO 21001": [["Satisfaction", "Satisfaction des apprenants", "≥ 80 %", "Par session"], ["Réussite", "Taux de réussite", "≥ 85 %", "Annuelle"], ["Réclamations", "Délai de traitement", "< 15 j", "Mensuelle"]],
          "ISO 27001": [["Incidents", "Incidents majeurs", "0", "Mensuelle"], ["Sauvegardes", "Tests de restauration réussis", "100 %", "Trimestrielle"], ["Sensibilisation", "Personnel sensibilisé", "100 %", "Annuelle"]],
          "ISO 50001": [["Performance", "IPÉ kWh / unité", "-5 % vs SER", "Mensuelle"], ["UES", "UES avec plan d'action", "100 %", "Annuelle"], ["Comptage", "Taux de couverture du comptage", "≥ 90 %", "Annuelle"]],
          "ISO 22000": [["Sécurité", "Dépassements de limites critiques", "0", "Mensuelle"], ["Hygiène", "Conformité des analyses", "≥ 98 %", "Mensuelle"], ["Traçabilité", "Test de traçabilité < 4 h", "100 %", "Semestrielle"]],
          "ISO 42001": [["Gouvernance", "Systèmes d'IA évalués", "100 %", "Annuelle"], ["Incidents", "Incidents IA traités", "100 %", "Trimestrielle"], ["Formation", "Personnel formé", "100 %", "Annuelle"]]}
    rows = [r + ["", ""] for r in ex[std]]
    return _doc(f"Objectifs et indicateurs {std} — {c.get('name', '')}", c, [
        {"heading": "Tableau des objectifs (exemples à adapter)", "table": {"columns": ["Thème", "Indicateur", "Cible", "Fréquence", "Responsable", "Résultat"], "rows": rows}}],
        "objectives", std)


def audit_checklist(c: dict, std: str = None) -> dict:
    std = _std(std)
    rows = [[cl["id"], cl["title"], q, ", ".join(cl["evidence"]), "", ""] for cl in clauses(std) for q in cl["questions"]]
    return _doc(f"Check-list d'audit {std} — {c.get('name', '')}", c, [
        {"heading": "Informations audit", "paragraphs": ["Auditeur : ________   Audité : ________   Date : ________   Processus : ________"]},
        {"heading": "Questions d'audit", "table": {"columns": ["Chapitre", "Exigence", "Question", "Preuves attendues", "Constat", "Cotation"], "rows": rows}}],
        "audit_checklist", std)


def internal_audit_programme(c: dict, std: str = None) -> dict:
    std = _std(std)
    procs = ["Direction"] + [a[:1].upper() + a[1:] for a in _acts(c)] + ["Achats", "RH", "Système"]
    months = ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]
    rows = [[p, months[(i * 2) % 12], "Auditeur interne à désigner", std] for i, p in enumerate(procs)]
    return _doc(f"Programme d'audit interne {std} — {c.get('name', '')}", c, [
        {"heading": "Principes (ISO 19011)", "bullets": ["Tous les processus audités au moins une fois par cycle.", "Fréquence renforcée sur les processus à risque ou ayant eu des NC.", "Auditeurs formés et indépendants de l'activité auditée."]},
        {"heading": "Planning annuel", "table": {"columns": ["Processus", "Mois", "Auditeur", "Référentiel"], "rows": rows}}],
        "internal_audit_programme", std)


def management_review(c: dict, std: str = None) -> dict:
    std = _std(std)
    inputs = ["Suivi des actions des revues précédentes", "Évolution des enjeux internes et externes",
              "Satisfaction et retours des parties intéressées", "Atteinte des objectifs", "Performance des processus",
              "Non-conformités et actions correctives", "Résultats de surveillance et de mesure", "Résultats d'audits",
              "Performance des prestataires externes", "Adéquation des ressources", "Efficacité des actions face aux risques",
              "Opportunités d'amélioration"]
    extra = {"ISO 14001": ["Obligations de conformité et aspects significatifs"], "ISO 45001": ["Résultats de la consultation des travailleurs", "Incidents et accidents"],
             "ISO 27001": ["Résultats de l'appréciation des risques et du plan de traitement", "Incidents de sécurité"],
             "ISO 50001": ["Performance énergétique et IPÉ"], "ISO 22000": ["Résultats de vérification des PRP et du plan HACCP", "Situations d'urgence et retraits"]}
    rows = [[i, "", ""] for i in inputs + extra.get(std, [])]
    return _doc(f"PV de revue de direction {std} — {c.get('name', '')}", c, [
        {"heading": "Participants et date", "paragraphs": ["Date : ________   Participants : ________"]},
        {"heading": "Données d'entrée", "table": {"columns": ["Point", "Constat / données", "Commentaire"], "rows": rows}},
        {"heading": "Décisions (éléments de sortie)", "table": {"columns": ["Décision", "Responsable", "Échéance"], "rows": [["Opportunités d'amélioration", "", ""], ["Modifications du système", "", ""], ["Besoins en ressources", "", ""]]}}],
        "management_review", std)


def soa(c: dict, std: str = None) -> dict:
    counts = {"A.5": 37, "A.6": 8, "A.7": 14, "A.8": 34}
    themes = {"A.5": "Organisationnelle", "A.6": "Personnes", "A.7": "Physique", "A.8": "Technologique"}
    rows = [[f"{k}.{i}", themes[k], "Intitulé selon la norme", "Oui", "", "À évaluer"] for k, n in counts.items() for i in range(1, n + 1)]
    return _doc(f"Déclaration d'applicabilité ISO 27001 — {c.get('name', '')}", c, [
        {"heading": "Mode d'emploi", "paragraphs": ["93 mesures de l'annexe A (2022). Pour chaque mesure : applicabilité, justification (risque, exigence légale ou contractuelle) et état de mise en œuvre. Renseigner les intitulés à partir de la norme achetée par le client."]},
        {"heading": "Mesures", "table": {"columns": ["Mesure", "Thème", "Intitulé", "Applicable", "Justification", "Statut"], "rows": rows}}],
        "soa", "ISO 27001")


def roadmap_doc(c: dict, std: str = None, progress: dict | None = None) -> dict:
    std = _std(std); progress = progress or {}
    rows = [[p["phase"], t, "Fait" if progress.get(f"{p['phase']}|{t}") else "À faire"] for p in ROADMAP for t in p["tasks"]]
    return _doc(f"Feuille de route de mise en place {std} — {c.get('name', '')}", c, [
        {"heading": "Documents clés à produire", "bullets": STANDARDS[std]["key_docs"]},
        {"heading": "Étapes du projet", "table": {"columns": ["Phase", "Tâche", "État"], "rows": rows}}], "roadmap", std)


def transition_2026(c: dict, std: str = None) -> dict:
    rows = [[t["clause"], t["topic"], t["change"], t["action"], "", ""] for t in TRANSITION]
    return _doc(f"Plan de transition ISO 9001:2015 → 2026 — {c.get('name', '')}", c, [
        {"heading": "Contexte", "paragraphs": ["ISO 9001:2026 a été publiée le 16 septembre 2026, avec une transition de trois ans. Les modalités exactes sont fixées par l'IAF et les organismes d'accréditation. Vérifier chaque point contre le texte officiel."]},
        {"heading": "Écarts et actions", "table": {"columns": ["Chapitre", "Sujet", "Évolution", "Action", "Responsable", "Échéance"], "rows": rows}}],
        "transition_2026", "ISO 9001")


def integrated_matrix(c: dict, std: str = None) -> dict:
    stds = INTEGRATED["standards"]
    rows = [[r["clause"], r["common"]] + [r.get(s, "") for s in stds] for r in INTEGRATED["rows"]]
    return _doc(f"Matrice du système intégré — {c.get('name', '')}", c, [
        {"heading": "Correspondance", "table": {"columns": ["Chapitre", "Thème commun"] + stds, "rows": rows}},
        {"heading": "Documents mutualisables", "bullets": ["Contexte et parties intéressées", "Maîtrise documentaire", "Programme d'audit intégré", "Revue de direction unique", "Traitement des NC et actions correctives"]}],
        "integrated_matrix", "")


def training_quiz(c: dict, std: str = None, n: int = 10) -> dict:
    std = _std(std); pool = clauses(std)
    rnd = random.Random(f"{c.get('name')}{std}")
    rows = []
    for cl in rnd.sample(pool, min(n, len(pool))):
        opts = [cl["title"]] + [w["title"] for w in rnd.sample([x for x in pool if x["id"] != cl["id"]], 3)]
        rnd.shuffle(opts)
        rows.append([f"Quel chapitre traite de : « {cl['summary']} »", " / ".join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(opts)), "ABCD"[opts.index(cl["title"])]])
    return _doc(f"Quiz de formation {std} — {c.get('name', '')}", c, [{"heading": "Questions", "table": {"columns": ["Question", "Propositions", "Réponse"], "rows": rows}}], "training_quiz", std)


GENERATORS = {
    "roadmap": ("Feuille de route de mise en place", roadmap_doc, None),
    "policy": ("Politique", policy, None),
    "process_map": ("Cartographie des processus", process_map, None),
    "risk_register": ("Registre risques / aspects / dangers", risk_register, None),
    "objectives": ("Objectifs et indicateurs", objectives, None),
    "procedure_documents": ("Procédure maîtrise documentaire", procedure_documents, None),
    "internal_audit_programme": ("Programme d'audit interne", internal_audit_programme, None),
    "audit_checklist": ("Check-list d'audit", audit_checklist, None),
    "management_review": ("PV de revue de direction", management_review, None),
    "training_quiz": ("Quiz de formation", training_quiz, None),
    "soa": ("Déclaration d'applicabilité", soa, ["ISO 27001"]),
    "transition_2026": ("Transition ISO 9001:2026", transition_2026, ["ISO 9001"]),
    "integrated_matrix": ("Matrice système intégré", integrated_matrix, None),
}


# ---------------------------------------------------------- analyse d'écarts
def gap_score(std: str, answers: dict) -> dict:
    cls = clauses(std); n = s = 0.0; by_ch: dict[str, list] = {}
    counts = {k: 0 for k in GAP_STATUS}
    for cl in cls:
        st = answers.get(cl["id"], {}).get("status")
        if not st:
            continue
        counts[st] += 1
        if st == "NA":
            continue
        v = {"C": 1, "P": 0.5}.get(st, 0)
        n += 1; s += v
        by_ch.setdefault(chapter(cl["id"]), []).append(v)
    return {"score": round(100 * s / n) if n else None, "answered": sum(counts.values()), "total": len(cls),
            "counts": counts, "by_chapter": {k: round(100 * sum(v) / len(v)) for k, v in by_ch.items()}}


def gap_analysis(c: dict, std: str, answers: dict) -> dict:
    sc = gap_score(std, answers)
    rows, actions = [], []
    for cl in clauses(std):
        a = answers.get(cl["id"], {}); st = a.get("status", "")
        rows.append([cl["id"], cl["title"], GAP_STATUS.get(st, "Non évalué"), a.get("note", "")])
        if st in ("NC", "P"):
            actions.append([cl["id"], "Mettre en place : " + ", ".join(cl["evidence"]), "Haute" if st == "NC" else "Moyenne", "", ""])
    k = sc["counts"]
    synth = (f"Taux de conformité {std} : {sc['score'] if sc['score'] is not None else '—'} % "
             f"({sc['answered']}/{sc['total']} exigences évaluées : {k['C']} conformes, {k['P']} partielles, {k['NC']} non conformes, {k['NA']} NA).")
    d = _doc(f"Rapport d'analyse d'écarts {std} — {c.get('name', '')}", c, [], "gap_analysis", std)
    reco = _enrich(d, f"Consultant {std} : 4 phrases de recommandations prioritaires pour {_ctx(c)}. Résultat du diagnostic : {synth}. "
                      f"Exigences non conformes : {', '.join(a[0] for a in actions[:12])}.",
                   "Traiter d'abord les écarts de priorité haute en commençant par le contexte, les risques et la maîtrise documentaire, qui structurent le reste du système.")
    d["sections"] = [
        {"heading": "Synthèse", "paragraphs": [synth, reco], "score": sc["score"], "chart": {"type": "radar", "data": sc["by_chapter"]}},
        {"heading": "Évaluation par exigence", "table": {"columns": ["Chapitre", "Exigence", "Statut", "Observation"], "rows": rows}},
        {"heading": "Plan d'actions", "table": {"columns": ["Chapitre", "Action", "Priorité", "Responsable", "Échéance"], "rows": actions}}]
    return d


# ---------------------------------------------------- audit tierce partie
# Durées indicatives inspirées du tableau IAF MD5 (SMQ) — à confirmer par l'organisme certificateur.
_MD5 = [(5, 1.5), (10, 2), (15, 2.5), (25, 3), (45, 4), (65, 5), (85, 6), (125, 7), (175, 8), (275, 9),
        (425, 10), (625, 11), (875, 12), (1175, 13), (1550, 14), (2025, 15), (10**9, 16)]
_FACTOR = {"ISO 14001": 1.1, "ISO 45001": 1.1, "ISO 22000": 1.1, "ISO 27001": 1.2}


def audit_duration(size: int, stds: list[str], atype: str) -> dict:
    base = next(d for lim, d in _MD5 if size <= lim)
    initial = sum(base * _FACTOR.get(s, 1.0) for s in stds)
    if len(stds) > 1:
        initial *= 0.8  # réduction possible pour un système intégré
    r = lambda x: max(0.5, round(x * 2) / 2)  # noqa: E731
    days = {"stage1": r(initial * 0.3), "stage2": r(initial * 0.7), "surveillance": r(initial / 3),
            "recertification": r(initial * 2 / 3), "blanc": r(initial * 0.5)}[atype]
    return {"initial_total": r(initial), "days": days}


def _j(x: float) -> str:
    return (f"{x:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def audit_plan(c: dict, a: dict) -> dict:
    stds = a["standards"]; size = int(re.sub(r"\D", "", str(c.get("size") or "")) or 10)
    dur = audit_duration(size, stds, a["type"])
    slots = ["Réunion d'ouverture, présentation du plan, visite des installations"]
    if a["type"] == "stage1":
        slots += ["Revue documentaire : domaine d'application, politique, objectifs",
                  "Contexte, parties intéressées, risques, exigences légales",
                  "Programme d'audit interne et revue de direction", "Préparation de l'étape 2 et points sensibles"]
    else:
        slots += ["Direction : contexte, leadership, politique, objectifs, risques (4 à 6)",
                  "Support : ressources, compétences, sensibilisation, documentation (7)"]
        slots += [f"Processus « {x} » : maîtrise opérationnelle (8)" for x in _acts(c)]
        for s in stds:
            sp = [x["id"] for x in STANDARDS[s]["specific"]]
            if sp:
                slots.append(f"Exigences spécifiques {s} : {', '.join(sp)}")
        slots += ["Évaluation des performances : surveillance, audit interne, revue de direction (9)",
                  "Amélioration : NC et actions correctives (10)", "Suivi des NC de l'audit précédent" if a["type"] in ("surveillance", "recertification") else "Échantillonnage complémentaire sur le terrain"]
    slots += ["Synthèse de l'équipe d'audit", "Réunion de clôture : constats et suite"]
    halfdays = max(2, int(dur["days"] * 2)); n = len(slots)
    rows = []
    for i, s in enumerate(slots):
        hd = halfdays - 1 if i == n - 1 else min(halfdays - 2, i * (halfdays - 1) // max(1, n - 1))
        rows.append([f"Jour {hd // 2 + 1}", "Matin" if hd % 2 == 0 else "Après-midi", s, a.get("lead_auditor") or "Auditeur responsable"])
    return _doc(f"Plan d'audit — {AUDIT_TYPES[a['type']]} — {c.get('name', '')}", c, [
        {"heading": "Informations", "table": {"columns": ["Élément", "Valeur"], "rows": [
            ["Référentiel(s)", ", ".join(stds)], ["Type d'audit", AUDIT_TYPES[a["type"]]], ["Date", a.get("date") or "À fixer"],
            ["Effectif déclaré", str(size)], ["Durée indicative", f"{_j(dur['days'])} jour(s) — base audit initial total {_j(dur['initial_total'])} j"],
            ["Auditeur responsable", a.get("lead_auditor") or "—"], ["Domaine d'application", c.get("activities") or "—"]]}},
        {"heading": "Programme", "table": {"columns": ["Jour", "Créneau", "Thème / processus audité", "Auditeur"], "rows": rows}},
        {"heading": "Notes", "bullets": ["Durée indicative inspirée de l'IAF MD5 : l'organisme certificateur fixe la durée officielle.",
                                         "Échantillonnage des enregistrements sur la période de fonctionnement du système.",
                                         "Les constats sont cotés : point fort, conforme, opportunité d'amélioration, NC mineure, NC majeure."]}],
        "audit_plan", ", ".join(stds))


def audit_stats(a: dict) -> dict:
    counts = {k: 0 for k in AUDIT_GRADES}; by_std = {}; by_ch: dict[str, list] = {}
    for key, f in (a.get("findings") or {}).items():
        g = f.get("grade")
        if g not in AUDIT_GRADES:
            continue
        counts[g] += 1
        std, cid = key.split("|", 1)
        if g == "NA":
            continue
        ok = 1 if g in ("PF", "C", "OA") else 0
        by_std.setdefault(std, []).append(ok); by_ch.setdefault(chapter(cid), []).append(ok)
    ev = sum(v for k, v in counts.items() if k != "NA")
    ok = counts["PF"] + counts["C"] + counts["OA"]
    total = sum(len(clauses(s)) for s in a["standards"])
    pct = lambda v: round(100 * sum(v) / len(v))  # noqa: E731
    if counts["NCM"]:
        verdict = ("Certification non recommandée en l'état", "Les non-conformités majeures doivent être corrigées et leur correction vérifiée (sur site ou sur preuves) dans le délai fixé par l'organisme certificateur.")
    elif counts["NCm"]:
        verdict = ("Certification recommandée sous réserve", "Recommandée sous réserve de l'acceptation du plan d'actions correctives pour les NC mineures (causes, corrections, actions, délais).")
    elif ev:
        verdict = ("Certification recommandée", "Aucune non-conformité relevée.")
    else:
        verdict = ("Audit non commencé", "")
    return {"counts": counts, "evaluated": ev, "total": total, "conformity": round(100 * ok / ev) if ev else None,
            "progress": round(100 * sum(counts.values()) / total) if total else 0,
            "by_standard": {k: pct(v) for k, v in by_std.items()}, "by_chapter": {k: pct(v) for k, v in by_ch.items()},
            "verdict": verdict[0], "verdict_text": verdict[1]}


def audit_report(c: dict, a: dict) -> dict:
    st = audit_stats(a); idx = {}
    for s in a["standards"]:
        for cl in clauses(s):
            idx[f"{s}|{cl['id']}"] = (s, cl)
    ncs, ofi, strong = [], [], []
    n = 0
    for key, f in sorted((a.get("findings") or {}).items(), key=lambda kv: (kv[0].split("|")[0], _ckey(kv[0].split("|")[1]))):
        if key not in idx:
            continue
        s, cl = idx[key]; g = f.get("grade")
        if g in ("NCm", "NCM"):
            n += 1
            ncs.append([f"NC-{n:02d}", AUDIT_GRADES[g], s, f"{cl['id']} {cl['title']}", f.get("note", ""), f.get("evidence", "")])
        elif g == "OA":
            ofi.append([s, f"{cl['id']} {cl['title']}", f.get("note", "")])
        elif g == "PF":
            strong.append([s, f"{cl['id']} {cl['title']}", f.get("note", "")])
    k = st["counts"]
    summary = (f"{st['evaluated']} exigences évaluées sur {st['total']}. Taux de conformité : {st['conformity'] if st['conformity'] is not None else '—'} %. "
               f"{k['NCM']} NC majeure(s), {k['NCm']} NC mineure(s), {k['OA']} opportunité(s) d'amélioration, {k['PF']} point(s) fort(s).")
    d = _doc(f"Rapport d'audit — {AUDIT_TYPES[a['type']]} — {c.get('name', '')}", c, [], "audit_report", ", ".join(a["standards"]))
    concl = _enrich(d, f"Rédige la conclusion (5 phrases) d'un rapport d'audit de certification tierce partie {', '.join(a['standards'])} pour {_ctx(c)}. "
                       f"Résultats : {summary} Décision proposée : {st['verdict']}. Constats NC : " + "; ".join(f"{x[3]} : {x[4]}" for x in ncs[:8]),
                    st["verdict_text"])
    d["sections"] = [
        {"heading": "Informations", "table": {"columns": ["Élément", "Valeur"], "rows": [
            ["Référentiel(s)", ", ".join(a["standards"])], ["Type", AUDIT_TYPES[a["type"]]], ["Date", a.get("date") or ""],
            ["Auditeur responsable", a.get("lead_auditor") or ""], ["Domaine", c.get("activities") or ""]]}},
        {"heading": "Synthèse", "paragraphs": [summary], "score": st["conformity"],
         "chart": {"type": "bar", "data": {AUDIT_GRADES[g]: v for g, v in k.items() if g != "NA"}}},
        {"heading": "Conclusion et recommandation", "paragraphs": [st["verdict"] + ".", concl]},
        {"heading": "Fiches de non-conformité", "table": {"columns": ["N°", "Type", "Norme", "Exigence", "Constat", "Preuve"], "rows": ncs}},
        {"heading": "Opportunités d'amélioration", "table": {"columns": ["Norme", "Exigence", "Constat"], "rows": ofi}},
        {"heading": "Points forts", "table": {"columns": ["Norme", "Exigence", "Constat"], "rows": strong}},
        {"heading": "Plan d'actions correctives (à remplir par l'audité)", "table": {"columns": ["N°", "Correction", "Analyse des causes", "Action corrective", "Responsable", "Délai"], "rows": [[x[0], "", "", "", "", ""] for x in ncs]}}]
    return d


def audit_questions(std: str, cid: str) -> dict:
    """Aide à l'auditeur : questions, preuves et techniques d'échantillonnage pour une exigence."""
    cl = next((x for x in clauses(std) if x["id"] == cid), None)
    if not cl:
        raise KeyError(cid)
    tips = ["Demander les enregistrements sur au moins 3 mois", "Interroger un pilote et un opérateur",
            "Vérifier la cohérence entre le document et la pratique terrain", "Échantillonner au hasard (√n + 1 pour les grandes populations)"]
    return {"clause": cl, "tips": tips}


# ------------------------------------------------------------ rédacteur IA
DOC_TYPES = ["Procédure", "Instruction de travail", "Fiche processus", "Politique", "Domaine d'application",
             "Manuel du système", "Rapport", "Formulaire / enregistrement", "Support de formation", "Courrier / e-mail", "Autre"]


def write_document(c: dict, std: str, doc_type: str, subject: str, instructions: str = "") -> dict:
    std = _std(std)
    rel = [cl for cl in clauses(std) if set(re.findall(r"\w{4,}", subject.lower())) & set(re.findall(r"\w{4,}", (cl["title"] + " " + cl["summary"]).lower()))][:4]
    ref = "; ".join(f"§{x['id']} {x['title']} : {x['summary']}" for x in rel)
    d = _doc(f"{doc_type} — {subject} ({c.get('name', '')})", c, [], "ai_writer", std)
    prompt = (f"Rédige un document de type « {doc_type} » sur « {subject} » pour un système {std}.\n"
              f"Organisme : {_ctx(c)}.\nExigences liées : {ref or 'à déterminer'}.\n"
              f"Consignes du consultant : {instructions or 'aucune'}.\n"
              "Structure avec des titres préfixés par '## ' et des listes à puces préfixées par '- '. "
              "Pour une procédure : objet, domaine, références, définitions, responsabilités, déroulement, enregistrements.")
    out = llm.generate(prompt, max_tokens=2500) if llm.available else None
    if out:
        d["ai"] = True
        d["sections"] = _md_to_sections(out)
    else:
        d["sections"] = [
            {"heading": "1. Objet", "paragraphs": [f"Définir les dispositions relatives à « {subject} »."]},
            {"heading": "2. Domaine d'application", "paragraphs": [f"S'applique à {c.get('name', 'l’organisme')} — {c.get('activities') or ''}."]},
            {"heading": "3. Références", "bullets": [f"{std} §{x['id']} {x['title']}" for x in rel] or [std]},
            {"heading": "4. Responsabilités", "table": {"columns": ["Activité", "Responsable"], "rows": [["Application", ""], ["Vérification", ""], ["Approbation", "Direction"]]}},
            {"heading": "5. Déroulement", "bullets": ["Étape 1 : …", "Étape 2 : …", "Étape 3 : …"]},
            {"heading": "6. Enregistrements", "bullets": sorted({e for x in rel for e in x["evidence"]}) or ["…"]},
            {"heading": "Note", "paragraphs": ["Modèle structuré généré sans modèle d'IA. Connectez un modèle (Réglages → IA) pour obtenir un texte rédigé complet." +
                                               (f" Dernière erreur : {llm.last_error}" if llm.last_error else "")]}]
    return d


def _md_to_sections(text: str) -> list[dict]:
    secs: list[dict] = []
    cur = {"heading": "Document", "paragraphs": [], "bullets": []}
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if cur["paragraphs"] or cur["bullets"]:
                secs.append(cur)
            cur = {"heading": s.lstrip("# ").strip("* "), "paragraphs": [], "bullets": []}
        elif re.match(r"^([-*•]|\d+[.)])\s+", s):
            cur["bullets"].append(re.sub(r"^([-*•]|\d+[.)])\s+", "", s).replace("**", ""))
        else:
            cur["paragraphs"].append(s.replace("**", ""))
    secs.append(cur)
    return [{k: v for k, v in x.items() if v} for x in secs if x.get("paragraphs") or x.get("bullets")]


# ------------------------------------------------------------- assistant
def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9]{3,}", s.lower()))


def ask(question: str, std: str | None = None) -> dict:
    q = _tokens(question); m = re.search(r"\b(\d{1,2}(?:\.\d){1,2}|A\.\d)\b", question)
    named = [s for s in STANDARDS if s.split()[1] in question] or ([std] if std in STANDARDS else list(STANDARDS))
    scored = []
    for s in named:
        for cl in clauses(s):
            txt = " ".join([cl["title"], cl["summary"], *cl["questions"], *cl["evidence"]])
            sc = len(q & _tokens(txt)) + (8 if m and m.group(1) == cl["id"] else 0) + (0.5 if cl.get("specific") else 0)
            scored.append((sc, s, cl))
    for t in TRANSITION:
        sc = len(q & _tokens(" ".join(t.values()))) + (3 if "2026" in question else 0)
        scored.append((sc, "ISO 9001", {"id": t["clause"], "title": "Transition 2026 — " + t["topic"], "summary": t["change"] + " Action : " + t["action"]}))
    scored.sort(key=lambda x: -x[0])
    hits = [(s, h) for sc, s, h in scored[:4] if sc > 0]
    if not hits:
        out = llm.generate(question) if llm.available else None
        return {"answer": out or "Aucun élément trouvé dans la base locale. Précisez la norme et le chapitre (ex. « ISO 14001 6.1.2 »).", "sources": [], "ai": bool(out)}
    base = "\n".join(f"{s} §{h['id']} {h['title']} : {h['summary']}" for s, h in hits)
    out = llm.generate(f"Question du consultant : « {question} »\nÉléments de la base Kapsi-Q :\n{base}\nRéponds de façon précise et opérationnelle.") if llm.available else None
    return {"answer": out or base, "sources": [f"{s} §{h['id']} {h['title']}" for s, h in hits], "ai": bool(out)}
