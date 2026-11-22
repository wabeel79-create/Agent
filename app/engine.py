"""Moteur Kapsi ISO.

Trois couches :
1. Base de connaissances ISO (JSON locaux, aucun accès Internet).
2. Générateurs déterministes : produisent des livrables fiables même sans modèle d'IA.
3. Modèle de langage optionnel (enrichissement et questions libres) :
   - KAPSI_BACKEND=kapsi  -> module Python défini par KAPSI_MODEL_MODULE exposant generate(prompt) -> str
   - KAPSI_BACKEND=ollama -> serveur Ollama local (KAPSI_LLM_URL, KAPSI_LLM_MODEL)
   - KAPSI_BACKEND=none   -> (par défaut) générateurs seuls, 100 % hors ligne
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import re
import urllib.request
from pathlib import Path

KNOW = Path(__file__).parent / "knowledge"


def _load(name: str) -> dict:
    return json.loads((KNOW / name).read_text(encoding="utf-8"))


ISO9001 = _load("iso9001.json")["clauses"]
TRANSITION = _load("transition_2026.json")["changes"]
INTEGRATED = _load("integrated.json")
CLAUSE_BY_ID = {c["id"]: c for c in ISO9001}

STATUS_LABEL = {"C": "Conforme", "P": "Partiellement conforme", "NC": "Non conforme", "NA": "Non applicable"}
STATUS_PRIORITY = {"NC": "Haute", "P": "Moyenne", "C": "-", "NA": "-"}


# --------------------------------------------------------------------------- LLM
class LLM:
    def __init__(self) -> None:
        self.backend = os.getenv("KAPSI_BACKEND", "none").lower()
        self._kapsi = None
        if self.backend == "kapsi":
            mod = os.getenv("KAPSI_MODEL_MODULE", "")
            try:
                self._kapsi = importlib.import_module(mod)
            except Exception:  # module absent : on reste en mode générateurs
                self.backend = "none"

    @property
    def available(self) -> bool:
        return self.backend in ("kapsi", "ollama")

    def generate(self, prompt: str, timeout: int = 120) -> str | None:
        try:
            if self.backend == "kapsi" and self._kapsi:
                return str(self._kapsi.generate(prompt))
            if self.backend == "ollama":
                url = os.getenv("KAPSI_LLM_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
                body = json.dumps({"model": os.getenv("KAPSI_LLM_MODEL", "qwen2.5:7b"),
                                   "prompt": prompt, "stream": False}).encode()
                req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())["response"].strip()
        except Exception:
            return None
        return None


llm = LLM()


# ------------------------------------------------------------------- helpers
def _doc(title: str, client: dict, sections: list[dict], kind: str) -> dict:
    return {
        "kind": kind,
        "title": title,
        "client": client.get("name", ""),
        "date": dt.date.today().isoformat(),
        "sections": sections,
        "footer": "Projet généré par Kapsi ISO, à valider par le consultant avant diffusion.",
    }


def _ctx(client: dict) -> str:
    return (f"{client.get('name', 'Organisme')}, "
            f"{client.get('sector', 'secteur non précisé')}, "
            f"{client.get('size', '?')} salariés, activités : {client.get('activities', 'non précisées')}")


def _enrich(prompt: str, fallback: str) -> str:
    if not llm.available:
        return fallback
    out = llm.generate(prompt)
    return out or fallback


# ---------------------------------------------------------------- generators
def policy(client: dict) -> dict:
    name = client.get("name", "L'organisme")
    base = (f"La direction de {name} s'engage à satisfaire durablement ses clients en fournissant "
            f"des produits et services conformes à leurs exigences et aux exigences légales et "
            f"réglementaires applicables, dans le secteur {client.get('sector', '')}.")
    intro = _enrich(f"Rédige en français un paragraphe d'introduction de politique qualité ISO 9001 pour : {_ctx(client)}. 5 phrases maximum.", base)
    axes = [
        "Écouter nos clients et mesurer régulièrement leur satisfaction.",
        "Maîtriser nos processus en identifiant et traitant les risques et les opportunités.",
        "Développer les compétences et l'implication de notre personnel.",
        "Promouvoir une culture qualité et un comportement éthique à tous les niveaux.",
        "Évaluer et développer nos fournisseurs et partenaires.",
        "Améliorer en continu l'efficacité de notre système de management de la qualité.",
    ]
    return _doc(f"Politique qualité — {name}", client, [
        {"heading": "Engagement de la direction", "paragraphs": [intro]},
        {"heading": "Nos axes stratégiques", "bullets": axes},
        {"heading": "Engagement", "paragraphs": [
            "La direction s'engage à fournir les ressources nécessaires, à communiquer cette politique "
            "à l'ensemble du personnel et à la revoir lors de chaque revue de direction.",
            "Signature : ____________________   Date : ____________"]},
    ], "policy")


def process_map(client: dict) -> dict:
    ops = [a.strip() for a in re.split(r"[,;\n]", client.get("activities", "")) if a.strip()] or ["Réalisation"]
    rows = [["Management", "Pilotage stratégique", "Direction", "Taux d'atteinte des objectifs"],
            ["Management", "Amélioration continue / audits", "Responsable qualité", "Taux de clôture des actions"],
            ["Réalisation", "Commercial / revue des exigences", "Responsable commercial", "Taux de transformation"]]
    rows += [["Réalisation", a.capitalize(), "Pilote à désigner", "Taux de conformité / délais"] for a in ops]
    rows += [["Réalisation", "Livraison et satisfaction client", "Responsable commercial", "Indice de satisfaction"],
             ["Support", "Achats et fournisseurs", "Responsable achats", "Note fournisseurs"],
             ["Support", "Ressources humaines et compétences", "RH", "Taux de réalisation du plan de formation"],
             ["Support", "Infrastructure et maintenance", "Maintenance", "Disponibilité équipements"],
             ["Support", "Informations documentées", "Responsable qualité", "Documents à jour"]]
    return _doc(f"Cartographie des processus — {client.get('name', '')}", client, [
        {"heading": "Processus et pilotes", "table": {"columns": ["Type", "Processus", "Pilote", "Indicateur clé"], "rows": rows}},
        {"heading": "Interactions", "paragraphs": [
            "Entrée : exigences des clients et des parties intéressées. Sortie : satisfaction client et produits/services conformes.",
            "Les processus de management pilotent les processus de réalisation ; les processus support fournissent les ressources."]},
    ], "process_map")


def procedure_documents(client: dict) -> dict:
    return _doc(f"Procédure — Maîtrise des informations documentées ({client.get('name', '')})", client, [
        {"heading": "1. Objet", "paragraphs": ["Définir les règles de création, validation, diffusion, modification, conservation et élimination des informations documentées du SMQ."]},
        {"heading": "2. Domaine d'application", "paragraphs": ["Tous les documents et enregistrements internes et d'origine externe relatifs au SMQ."]},
        {"heading": "3. Références", "paragraphs": ["ISO 9001, chapitre 7.5."]},
        {"heading": "4. Responsabilités", "table": {"columns": ["Étape", "Responsable"], "rows": [
            ["Rédaction", "Pilote de processus"], ["Vérification", "Responsable qualité"],
            ["Approbation", "Direction"], ["Diffusion et archivage", "Responsable qualité"]]}},
        {"heading": "5. Déroulement", "bullets": [
            "Codification : TYPE-PROCESSUS-NN (ex. PR-QUA-01) avec indice de révision.",
            "Création selon le modèle en vigueur ; cartouche Rédigé / Vérifié / Approuvé.",
            "Diffusion via la liste des documents en vigueur ; retrait des versions périmées.",
            "Modification : demande, mise à jour, nouvelle approbation, historique des révisions.",
            "Documents externes : identification, suivi des mises à jour (normes, réglementation).",
            "Enregistrements : durée de conservation, support, lieu et protection définis dans le tableau des enregistrements."]},
        {"heading": "6. Enregistrements associés", "bullets": ["Liste des documents en vigueur", "Tableau de conservation des enregistrements"]},
    ], "procedure")


def audit_checklist(client: dict, clauses: list[str] | None = None) -> dict:
    sel = [CLAUSE_BY_ID[c] for c in clauses if c in CLAUSE_BY_ID] if clauses else ISO9001
    rows = []
    for c in sel:
        for q in c["questions"]:
            rows.append([c["id"], c["title"], q, ", ".join(c["evidence"]), "", ""])
    return _doc(f"Check-list d'audit interne ISO 9001 — {client.get('name', '')}", client, [
        {"heading": "Informations audit", "paragraphs": ["Auditeur : ________   Audité : ________   Date : ________   Processus : ________"]},
        {"heading": "Questions d'audit", "table": {"columns": ["Chapitre", "Exigence", "Question", "Preuves attendues", "Constat", "C / P / NC"], "rows": rows}},
    ], "audit_checklist")


def gap_analysis(client: dict, answers: dict[str, dict]) -> dict:
    """answers = {"4.1": {"status": "P", "note": "..."}, ...}"""
    rows, actions, score_n, score = [], [], 0, 0.0
    for c in ISO9001:
        a = answers.get(c["id"], {})
        st = a.get("status", "NC")
        rows.append([c["id"], c["title"], STATUS_LABEL.get(st, st), a.get("note", "")])
        if st != "NA":
            score_n += 1
            score += {"C": 1, "P": 0.5}.get(st, 0)
        if st in ("NC", "P"):
            actions.append([c["id"], f"Mettre en place : {', '.join(c['evidence'])}", STATUS_PRIORITY[st], "", ""])
    pct = round(100 * score / score_n) if score_n else 0
    counts = {k: sum(1 for c in ISO9001 if answers.get(c["id"], {}).get("status", "NC") == k) for k in STATUS_LABEL}
    synth = (f"Taux de conformité global estimé : {pct} %. "
             f"{counts['C']} exigences conformes, {counts['P']} partiellement conformes, "
             f"{counts['NC']} non conformes, {counts['NA']} non applicables.")
    reco = _enrich(f"En tant que consultant ISO 9001, rédige en français 4 phrases de recommandations pour {_ctx(client)} dont l'analyse d'écarts donne : {synth}",
                   "Prioriser les écarts de priorité haute, en commençant par le contexte, les risques et la maîtrise documentaire, qui structurent le reste du système.")
    return _doc(f"Rapport d'analyse d'écarts ISO 9001 — {client.get('name', '')}", client, [
        {"heading": "Synthèse", "paragraphs": [synth, reco], "score": pct},
        {"heading": "Évaluation par exigence", "table": {"columns": ["Chapitre", "Exigence", "Statut", "Observation"], "rows": rows}},
        {"heading": "Plan d'actions", "table": {"columns": ["Chapitre", "Action", "Priorité", "Responsable", "Échéance"], "rows": actions}},
    ], "gap_analysis")


def transition_2026(client: dict) -> dict:
    rows = [[c["clause"], c["topic"], c["change"], c["action"], "", ""] for c in TRANSITION]
    return _doc(f"Plan de transition ISO 9001:2015 → ISO 9001:2026 — {client.get('name', '')}", client, [
        {"heading": "Contexte", "paragraphs": [
            "ISO 9001:2026 a été publiée le 16 septembre 2026. Une période de transition de trois ans est prévue ; "
            "les modalités exactes sont fixées par l'IAF et les organismes d'accréditation.",
            "Ce plan liste les écarts à traiter. Le consultant doit vérifier chaque point contre le texte officiel."]},
        {"heading": "Écarts et actions", "table": {"columns": ["Chapitre", "Sujet", "Évolution", "Action proposée", "Responsable", "Échéance"], "rows": rows}},
        {"heading": "Calendrier suggéré", "bullets": [
            "Mois 1 : formation de la direction et du responsable qualité aux évolutions.",
            "Mois 2-3 : mise à jour du contexte, des risques/opportunités et de la politique.",
            "Mois 4 : sensibilisation du personnel, audit interne sur la version 2026.",
            "Mois 5 : revue de direction, puis audit de transition avec l'organisme certificateur."]},
    ], "transition_2026")


def integrated_matrix(client: dict, standards: list[str] | None = None) -> dict:
    stds = [s for s in (standards or INTEGRATED["standards"]) if s in INTEGRATED["standards"]]
    rows = [[r["clause"], r["common"]] + [r.get(s, "") for s in stds] for r in INTEGRATED["rows"]]
    return _doc(f"Matrice du système intégré — {client.get('name', '')}", client, [
        {"heading": "Correspondance des exigences", "table": {"columns": ["Chapitre", "Thème commun"] + stds, "rows": rows}},
        {"heading": "Documents mutualisables", "bullets": [
            "Analyse de contexte et parties intéressées uniques", "Procédure unique de maîtrise documentaire",
            "Programme d'audit interne intégré (ISO 19011)", "Revue de direction unique",
            "Procédure unique de non-conformités et actions correctives"]},
    ], "integrated_matrix")


def training_quiz(client: dict, n: int = 10) -> dict:
    """Quiz de sensibilisation (pour les sessions de formation du cabinet)."""
    import random
    rnd = random.Random(client.get("name", "") + str(n))
    pool = rnd.sample(ISO9001, min(n, len(ISO9001)))
    rows = []
    for c in pool:
        wrong = rnd.sample([x for x in ISO9001 if x["id"] != c["id"]], 3)
        opts = [c["title"]] + [w["title"] for w in wrong]
        rnd.shuffle(opts)
        rows.append([f"Quel chapitre traite de : « {c['summary']} »", " / ".join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(opts)),
                     "ABCD"[opts.index(c["title"])]])
    return _doc(f"Quiz de sensibilisation ISO 9001 — {client.get('name', '')}", client, [
        {"heading": "Questions", "table": {"columns": ["Question", "Propositions", "Réponse"], "rows": rows}},
    ], "training_quiz")


GENERATORS = {
    "policy": ("Politique qualité", policy),
    "process_map": ("Cartographie des processus", process_map),
    "procedure_documents": ("Procédure maîtrise documentaire (§7.5)", procedure_documents),
    "audit_checklist": ("Check-list d'audit interne", audit_checklist),
    "transition_2026": ("Plan de transition 2015 → 2026", transition_2026),
    "integrated_matrix": ("Matrice système intégré QSE-Énergie", integrated_matrix),
    "training_quiz": ("Quiz de formation", training_quiz),
}


# ----------------------------------------------------------------------- Q&A
def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9]{3,}", s.lower())}


def ask(question: str) -> dict:
    """Recherche dans la base locale ; le modèle reformule si disponible."""
    q = _tokens(question)
    m = re.search(r"\b(\d{1,2}\.\d)\b", question)
    scored = []
    for c in ISO9001:
        txt = " ".join([c["title"], c["summary"], *c["questions"], *c["evidence"]])
        s = len(q & _tokens(txt)) + (10 if m and m.group(1) == c["id"] else 0)
        scored.append((s, c))
    for t in TRANSITION:
        s = len(q & _tokens(" ".join(t.values()))) + (2 if "2026" in question else 0)
        scored.append((s, {"id": t["clause"], "title": "Transition 2026 — " + t["topic"], "summary": t["change"] + " Action : " + t["action"]}))
    scored.sort(key=lambda x: -x[0])
    hits = [c for s, c in scored[:3] if s > 0]
    if not hits:
        return {"answer": "Je n'ai pas trouvé d'élément correspondant dans la base ISO locale. Reformulez avec un numéro de chapitre (ex. 7.5).", "sources": []}
    base = " ".join(f"§{h['id']} {h['title']} : {h['summary']}" for h in hits)
    ans = _enrich(f"Tu es un expert ISO 9001. Réponds en français, de façon précise et courte, à : « {question} ». "
                  f"Appuie-toi uniquement sur : {base}", base)
    return {"answer": ans, "sources": [f"§{h['id']} {h['title']}" for h in hits]}
