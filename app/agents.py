"""Agents Kapsi-Q.

Chaque agent joue un rôle de l'équipe qualité (responsable qualité, auditeur interne, formateur…).
Il lit les dossiers autorisés du client, produit des documents (enregistrés dans Kapsi-Q et en Word
dans le dossier de sortie), propose des cotations et des actions, et journalise chaque étape.

Garde-fous :
  - tout document produit a le statut « À valider » jusqu'à validation par une personne compétente ;
  - les agents ne remplacent jamais une réponse saisie par un humain dans le diagnostic ;
  - les audits produits par les agents sont des propositions que l'auditeur relit dans la grille ;
  - la pré-certification est une simulation : seul un organisme certificateur accrédité délivre un certificat.
"""
from __future__ import annotations

import datetime as dt
import re
import threading
import traceback

from . import engine, expertise, export, files, store
from .llm import llm

CORE = {"4.1", "4.3", "5.2", "6.1", "6.2", "7.5", "9.2", "9.3", "10.2"}
STOP = set("avec dans pour sont leur leurs elle cette ces des les une par sur aux est qui que tout tous entre selon "
           "chaque plus sans être avoir fait faire site liste".split())


def _today(days: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


class Run:
    def __init__(self, rid: int, client: dict, std: str, agent: str):
        self.rid, self.client, self.std, self.agent = rid, client, std, agent
        self.cid = client["id"]
        self.lines: list[dict] = []
        self.out: dict = {"documents": [], "alerts": []}

    def log(self, msg: str, kind: str = "info") -> None:
        self.lines.append({"t": dt.datetime.now().strftime("%H:%M:%S"), "kind": kind, "msg": msg})
        store.update_run(self.rid, log=self.lines)

    def doc(self, d: dict, agent: str | None = None) -> int:
        d.setdefault("standard", self.std)
        try:
            path = files.write_output(self.client["name"], self.std, d["title"] + ".docx", export.to_docx(d))
        except Exception as e:  # le document reste disponible dans Kapsi-Q
            path = None
            self.log(f"Écriture du fichier Word impossible ({type(e).__name__}) ; document conservé dans Kapsi-Q", "warn")
        did = store.save_document(self.cid, d, agent=agent or self.agent, path=path)
        self.out["documents"].append({"id": did, "title": d["title"], "path": path})
        self.log(f"Document produit : {d['title']}", "doc")
        store.update_run(self.rid, outputs=self.out)
        return did

    def save(self) -> None:
        store.update_run(self.rid, outputs=self.out)


# ------------------------------------------------------------------ outils
def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9]{4,}", s.lower()) if w not in STOP]


def find_evidence(item: str, limit: int = 3) -> list[dict]:
    ws = _words(item)
    if not ws:
        return []
    hits = files.search_and(ws, limit)
    if not hits and len(ws) > 2:
        hits = files.search_and(sorted(ws, key=len, reverse=True)[:2], limit)
    return hits


def evidence_map(std: str) -> dict[str, list[dict]]:
    out = {}
    for cl in engine.clauses(std):
        seen, hits = set(), []
        for ev in cl["evidence"]:
            for h in find_evidence(ev):
                if h["path"] not in seen:
                    seen.add(h["path"]); hits.append(h)
        out[cl["id"]] = hits[:5]
    return out


def apply_proposals(cid: int, std: str, props: dict) -> int:
    """Applique les cotations proposées, sans jamais remplacer une réponse saisie par un humain."""
    current = store.get_gap(cid, std)
    todo = {k: {"status": v["status"], "note": v["note"]} for k, v in props.items()
            if k not in current or (current[k].get("note") or "").startswith("[Agent]")}
    if todo:
        store.save_gap(cid, std, todo)
    return len(todo)


def _mark(cid: int, std: str, tasks: list[str]) -> None:
    proj = next((p for p in store.list_projects(cid) if p["standard"] == std), None)
    if not proj:
        store.add_project(cid, std); proj = {"progress": {}}
    prog = dict(proj["progress"])
    for ph in engine.ROADMAP:
        for t in ph["tasks"]:
            if t in tasks:
                prog[f"{ph['phase']}|{t}"] = True
    store.set_progress(cid, std, prog)


def _ctx(c: dict) -> str:
    return f"{c['name']} ({c.get('sector') or 'secteur non précisé'}, {c.get('size') or '?'} salariés ; activités : {c.get('activities') or 'non précisées'})"


# ------------------------------------------------------------------ agents
def agent_preuves(r: Run) -> None:
    """Analyste des preuves : indexe les dossiers et rapproche chaque exigence de ses preuves."""
    if not files.roots():
        r.log("Aucun dossier déclaré : ajoutez les dossiers du client (ou son Google Drive synchronisé) dans Réglages → Documents et Drive.", "warn")
        r.out["gap_proposals"] = {}; r.save(); return
    r.log("Indexation des dossiers autorisés…")
    st = files.index_all(progress=lambda m: r.log(m))
    r.log(f"{st['fichiers']} fichiers trouvés, {st['lus']} lus ou mis à jour.")
    em = evidence_map(r.std)
    human = {k for k, v in store.get_gap(r.cid, r.std).items() if not (v.get("note") or "").startswith("[Agent]")}
    props, rows = {}, []
    for cl in engine.clauses(r.std):
        hits = em[cl["id"]]
        n = len(hits)
        status = "C" if n >= 2 else "P" if n == 1 else "NC"
        names = [h["name"] for h in hits]
        props[cl["id"]] = {"status": status, "note": ("[Agent] Preuves trouvées : " + ", ".join(names[:3])) if names else "[Agent] Aucune preuve trouvée dans les dossiers",
                           "files": [h["path"] for h in hits]}
        rows.append([cl["id"], cl["title"], ", ".join(cl["evidence"]), "\n".join(names[:3]) or "—", status, "Réponse humaine conservée" if cl["id"] in human else ""])
    k = {s: sum(1 for p in props.values() if p["status"] == s) for s in ("C", "P", "NC")}
    r.log(f"Proposition : {k['C']} conformes, {k['P']} partielles, {k['NC']} sans preuve.")
    r.doc({"kind": "evidence_map", "title": f"Cartographie des preuves {r.std} — {r.client['name']}", "client": r.client["name"], "date": _today(), "ai": False,
           "footer": "Rapprochement automatique par l'agent Analyste des preuves : la présence d'un document ne prouve pas son application ; à confirmer sur le terrain.",
           "sections": [{"heading": "Synthèse", "paragraphs": [f"{st['fichiers']} fichiers analysés. Exigences avec au moins deux preuves : {k['C']} ; une preuve : {k['P']} ; aucune : {k['NC']}."]},
                        {"heading": "Preuves par exigence", "table": {"columns": ["Chapitre", "Exigence", "Preuves attendues", "Documents trouvés", "Proposition", "Remarque"], "rows": rows}}]})
    r.out["gap_proposals"] = props
    r.save()


def agent_qualite(r: Run) -> None:
    """Responsable qualité : construit le système documentaire du client."""
    c, std = r.client, r.std
    r.log(f"Construction du système documentaire {std} pour {c['name']}.")
    for kind in ("policy", "process_map", "risk_register", "objectives", "management_review"):
        r.doc(engine.GENERATORS[kind][1](c, std))
    if std == "ISO 27001":
        r.doc(engine.soa(c, std))
    if std == "ISO 9001":
        r.doc(engine.transition_2026(c, std))
    procs = expertise.procedures_for(std)
    r.log(f"Rédaction de {len(procs)} procédures" + (" (adaptées par l'IA locale)." if llm.available else "."))
    for p in procs:
        intro = llm.generate(f"En 3 phrases, rédige l'objet de la procédure « {p[1]} » ({std}) adaptée à {_ctx(c)}.", max_tokens=250) if llm.available else None
        r.doc(expertise.procedure_doc(c, std, p, intro))
    _mark(r.cid, std, ["Rédiger la politique", "Cartographie et fiches processus", "Rédiger les procédures et modes opératoires",
                       "Registre des risques et opportunités", "Fixer les objectifs et le planning du projet"])
    r.log("Feuille de route mise à jour (phases planification et documentation). Documents au statut « À valider ».", "ok")


def agent_formateur(r: Run) -> None:
    """Formateur : plan de formation, supports, quiz, émargements, suivi."""
    c, std = r.client, r.std
    mods = expertise.trainings_for(std)
    existing = {t["module"] for t in store.list_trainings(r.cid) if t["standard"] == std}
    plan_rows = []
    for i, m in enumerate(mods):
        quiz = engine.training_quiz({**c, "name": c["name"] + m[0]}, std, n=6)["sections"][0]["table"]["rows"]
        did = r.doc(expertise.training_pack(c, std, m, quiz))
        date = _today(7 * (i + 1))
        if m[1] not in existing:
            store.add_training(r.cid, {"standard": std, "module": m[1], "audience": m[3], "duration": m[4], "planned": date, "document_id": did})
        plan_rows.append([m[0], m[1], m[3], m[4], date])
    r.doc({"kind": "training_plan", "title": f"Plan de formation {std} — {c['name']}", "client": c["name"], "date": _today(), "ai": False,
           "footer": "Plan proposé par l'agent Formateur — à valider par la direction.",
           "sections": [{"heading": "Plan", "table": {"columns": ["Code", "Module", "Public", "Durée", "Date proposée"], "rows": plan_rows}},
                        {"heading": "Évaluation de l'efficacité", "bullets": ["Quiz en fin de session (seuil 70 %)", "Évaluation à chaud", "Observation au poste à 3 mois par le responsable hiérarchique"]}]})
    r.log(f"{len(mods)} formations planifiées dans l'onglet Formations.", "ok")


def _grades(r: Run, strict: bool) -> tuple[dict, dict]:
    answers = store.get_gap(r.cid, r.std)
    em = evidence_map(r.std) if files.roots() else {}
    findings, skipped = {}, []
    for cl in engine.clauses(r.std):
        st = answers.get(cl["id"], {}).get("status")
        ev = em.get(cl["id"], [])
        names = ", ".join(h["name"] for h in ev[:3])
        if not st:
            if strict:
                findings[f"{r.std}|{cl['id']}"] = {"grade": "NCm", "note": "[Agent] Exigence non démontrée (non évaluée)", "evidence": ""}
            else:
                skipped.append(cl["id"])
            continue
        if st == "NA":
            g, note = "NA", "Non applicable"
        elif st == "C":
            if em and not ev:
                g, note = ("NCm", "Conformité déclarée mais aucune preuve documentaire trouvée") if strict else ("OA", "Conforme selon le diagnostic ; preuve documentaire à présenter")
            else:
                g, note = "C", "Conforme"
        elif st == "P":
            g, note = "NCm", "Exigence partiellement mise en œuvre"
        else:
            g, note = ("NCM", "Exigence fondamentale non mise en œuvre") if cl["id"] in CORE else ("NCm", "Exigence non mise en œuvre")
        findings[f"{r.std}|{cl['id']}"] = {"grade": g, "note": f"[Agent] {note}", "evidence": names or ("Diagnostic du " + _today() if not em else "")}
    return findings, {"skipped": skipped}


def agent_auditeur(r: Run) -> None:
    """Auditeur interne : programme, audit proposé, rapport, actions correctives."""
    c, std = r.client, r.std
    r.doc(engine.internal_audit_programme(c, std))
    findings, info = _grades(r, strict=False)
    if not findings:
        r.log("Diagnostic vide : lancez d'abord l'Analyste des preuves ou faites le diagnostic.", "warn"); return
    a = store.create_audit(r.cid, {"type": "interne", "standards": [std], "date": _today(), "lead_auditor": "Agent Auditeur interne — à valider"})
    store.save_findings(a["id"], findings)
    a = store.get_audit(a["id"])
    s = engine.audit_stats(a)
    r.log(f"Audit interne n°{a['id']} proposé : conformité {s['conformity']} %, {s['counts']['NCM']} NC majeure(s), {s['counts']['NCm']} NC mineure(s).")
    if info["skipped"]:
        r.log(f"{len(info['skipped'])} exigences non évaluées au diagnostic n'ont pas été cotées.", "warn")
    r.doc(engine.audit_plan(c, a))
    r.doc(engine.audit_report(c, a))
    n = _actions_from_audit(r, a, f"Audit interne n°{a['id']}")
    r.out["audit_id"] = a["id"]
    _mark(r.cid, std, ["Établir le programme d'audit"])
    r.log(f"{n} action(s) corrective(s) ouverte(s). Relisez et validez l'audit dans la grille d'audit.", "ok")


def _actions_from_audit(r: Run, a: dict, source: str) -> int:
    open_ = {(x["standard"], x["clause"].split(" ")[0]) for x in store.list_actions(r.cid) if x["status"] != "Clôturée"}
    titles = {cl["id"]: cl["title"] for cl in engine.clauses(r.std)}
    n = 0
    for key, f in a["findings"].items():
        if f.get("grade") in ("NCm", "NCM"):
            std, cid_ = key.split("|", 1)
            if (std, cid_) in open_:
                continue
            store.add_action(r.cid, {"standard": std, "source": source, "clause": f"{cid_} {titles.get(cid_, '')}",
                                     "finding": f"{'NC majeure' if f['grade'] == 'NCM' else 'NC mineure'} : {f['note'].replace('[Agent] ', '')}",
                                     "due": _today(15 if f["grade"] == "NCM" else 30), "status": "Ouverte"})
            n += 1
    return n


def agent_capa(r: Run) -> None:
    """Actions correctives : analyse des causes et plan d'actions."""
    ev = {cl["id"]: cl for cl in engine.clauses(r.std)}
    acts = [a for a in store.list_actions(r.cid, r.std) if a["status"] != "Clôturée"]
    if not acts:
        r.log("Aucune action ouverte pour cette norme.", "ok"); return
    rows = []
    for a in acts:
        cl = ev.get(a["clause"].split(" ")[0])
        if not a["cause"]:
            cause = ("5 pourquoi à confirmer en atelier — hypothèses : méthode non formalisée, responsabilités non définies, "
                     "manque de formation, absence de suivi.")
            action = ("Mettre en place : " + ", ".join(cl["evidence"]) + " ; former les personnes concernées ; vérifier l'efficacité sous 3 mois.") if cl else "Définir et mettre en œuvre l'action, puis vérifier son efficacité."
            if llm.available:
                txt = llm.generate(f"Non-conformité {r.std} {a['clause']} : {a['finding']} chez {_ctx(r.client)}. Donne en 2 lignes : 'Cause probable : …' puis 'Action : …'.", max_tokens=200)
                if txt and "Action" in txt:
                    m = re.search(r"Cause probable\s*:\s*(.+?)\s*Action\s*:\s*(.+)", txt, re.S)
                    if m:
                        cause, action = m.group(1).strip(), m.group(2).strip()
            store.update_action(a["id"], {"cause": cause, "action": action, "owner": a["owner"] or "Responsable du système"})
            a = {**a, "cause": cause, "action": action, "owner": a["owner"] or "Responsable du système"}
        rows.append([str(a["id"]), a["clause"], a["finding"], a["cause"], a["action"], a["owner"], a["due"], a["status"]])
    r.doc({"kind": "capa_plan", "title": f"Plan d'actions correctives {r.std} — {r.client['name']}", "client": r.client["name"], "date": _today(), "ai": llm.available,
           "footer": "Analyses proposées par l'agent Actions correctives — causes à confirmer avec les personnes concernées.",
           "sections": [{"heading": "Actions", "table": {"columns": ["N°", "Exigence", "Constat", "Cause", "Action", "Responsable", "Échéance", "Statut"], "rows": rows}}]})
    r.log(f"{len(rows)} action(s) analysée(s).", "ok")


def readiness(cid: int, std: str) -> dict:
    gs = engine.gap_score(std, store.get_gap(cid, std))
    proj = next((p for p in store.list_projects(cid) if p["standard"] == std), {"progress": {}})
    ntask = sum(len(p["tasks"]) for p in engine.ROADMAP)
    road = round(100 * sum(1 for v in proj["progress"].values() if v) / ntask)
    docs = [d for d in store.list_documents(cid) if (d["standard"] or "").startswith(std)]
    val = round(100 * sum(1 for d in docs if d["status"] == "Validé") / len(docs)) if docs else 0
    audits = [a for a in store.list_audits(cid) if std in a["standards"] and a["type"] in ("interne", "blanc", "stage1", "stage2", "surveillance")]
    last = engine.audit_stats(audits[0]) if audits else None
    acts = store.list_actions(cid, std)
    closed = round(100 * sum(1 for a in acts if a["status"] == "Clôturée") / len(acts)) if acts else 100
    overdue = [a for a in acts if a["status"] != "Clôturée" and a["due"] and a["due"] < _today()]
    trs = [t for t in store.list_trainings(cid) if t["standard"] == std]
    trained = round(100 * sum(1 for t in trs if t["status"] == "Réalisée") / len(trs)) if trs else 0
    score = round(0.35 * (gs["score"] or 0) + 0.15 * road + 0.15 * val + 0.15 * ((last or {}).get("conformity") or 0) + 0.10 * trained + 0.10 * closed)
    verdict = ("Prêt pour l'audit de certification" if score >= 85 else "Audit à blanc recommandé avant la certification" if score >= 60 else "Mise en place à poursuivre")
    alerts = []
    if (gs["score"] or 0) < 70: alerts.append(f"Conformité du diagnostic faible ({gs['score'] if gs['score'] is not None else 0} %).")
    if docs and val < 50: alerts.append(f"Seulement {val} % des documents sont validés.")
    if overdue: alerts.append(f"{len(overdue)} action(s) corrective(s) en retard.")
    if not audits: alerts.append("Aucun audit interne réalisé.")
    if last and last["counts"]["NCM"]: alerts.append(f"{last['counts']['NCM']} NC majeure(s) au dernier audit.")
    if trs and trained < 50: alerts.append(f"Plan de formation réalisé à {trained} %.")
    nxt = [t for ph in engine.ROADMAP for t in ph["tasks"] if not proj["progress"].get(f"{ph['phase']}|{t}")][:5]
    return {"score": score, "verdict": verdict, "gap": gs["score"], "roadmap": road, "validated": val, "audit": (last or {}).get("conformity"),
            "trained": trained, "closed": closed, "overdue": len(overdue), "alerts": alerts, "next": nxt, "documents": len(docs)}


def agent_pilote(r: Run) -> None:
    """Pilote du système : tableau de pilotage, alertes et prochaines étapes."""
    k = readiness(r.cid, r.std)
    r.out["readiness"] = k; r.out["alerts"] = k["alerts"]
    rows = [["Conformité du diagnostic", f"{k['gap'] if k['gap'] is not None else '—'} %"], ["Avancement de la feuille de route", f"{k['roadmap']} %"],
            ["Documents validés", f"{k['validated']} % de {k['documents']}"], ["Conformité au dernier audit", f"{k['audit'] if k['audit'] is not None else '—'} %"],
            ["Formations réalisées", f"{k['trained']} %"], ["Actions correctives clôturées", f"{k['closed']} %"], ["Actions en retard", str(k["overdue"])]]
    r.doc({"kind": "dashboard", "title": f"Tableau de pilotage {r.std} — {r.client['name']}", "client": r.client["name"], "date": _today(), "ai": False,
           "footer": "Indice de préparation calculé par l'agent Pilote du système (indicatif).",
           "sections": [{"heading": "Indice de préparation à la certification", "paragraphs": [f"{k['score']} / 100 — {k['verdict']}."], "score": k["score"]},
                        {"heading": "Indicateurs", "table": {"columns": ["Indicateur", "Valeur"], "rows": rows}},
                        {"heading": "Alertes", "bullets": k["alerts"] or ["Aucune alerte."]},
                        {"heading": "Prochaines étapes", "bullets": k["next"] or ["Toutes les étapes de la feuille de route sont cochées."]}]})
    r.log(f"Indice de préparation : {k['score']}/100 — {k['verdict']}.", "ok")
    for a in k["alerts"]:
        r.log(a, "warn")


def agent_certification(r: Run) -> None:
    """Pré-certification : simulation des étapes 1 et 2 de l'audit de certification."""
    c, std = r.client, r.std
    r.log("Simulation d'un audit de certification (ne remplace pas l'organisme certificateur accrédité).")
    docs = store.list_documents(r.cid)
    titles = " ".join(d["title"].lower() for d in docs if (d["standard"] or "").startswith(std))
    stage1 = []
    for kd in engine.STANDARDS[std]["key_docs"]:
        ws = [w for w in _words(kd) if len(w) >= 5][:2]
        ok = bool(ws) and all(w in titles for w in ws)
        stage1.append([kd, "Présent" if ok else "À produire"])
    missing = [x[0] for x in stage1 if x[1] != "Présent"]
    r.log(f"Étape 1 (revue documentaire) : {len(stage1) - len(missing)}/{len(stage1)} documents clés présents.")
    findings, _ = _grades(r, strict=True)
    a = store.create_audit(r.cid, {"type": "blanc", "standards": [std], "date": _today(), "lead_auditor": "Agent Pré-certification — simulation"})
    store.save_findings(a["id"], findings)
    a = store.get_audit(a["id"])
    s = engine.audit_stats(a)
    r.log(f"Étape 2 simulée : conformité {s['conformity']} % — {s['verdict']}.", "ok" if s["counts"]["NCM"] == 0 else "warn")
    r.doc(engine.audit_report(c, a))
    r.doc({"kind": "precert", "title": f"Préparation à la certification {std} — {c['name']}", "client": c["name"], "date": _today(), "ai": False,
           "footer": "Simulation produite par l'agent Pré-certification. Seul un organisme certificateur accrédité (ISO/IEC 17021-1) peut délivrer un certificat.",
           "sections": [{"heading": "Conclusion de la simulation", "paragraphs": [f"{s['verdict']}. Conformité simulée : {s['conformity']} %. {s['counts']['NCM']} NC majeure(s), {s['counts']['NCm']} NC mineure(s)."]},
                        {"heading": "Étape 1 — documents clés", "table": {"columns": ["Document", "État"], "rows": stage1}},
                        {"heading": "Points bloquants", "bullets": ([f"Produire : {m}" for m in missing] + [f"Lever les NC majeures ({s['counts']['NCM']})"] * bool(s["counts"]["NCM"])) or ["Aucun point bloquant identifié."]}]})
    r.out["audit_id"] = a["id"]
    _mark(r.cid, std, ["Audit à blanc par le consultant"])


def agent_mission(r: Run) -> None:
    """Chef de mission : enchaîne les agents, du diagnostic au tableau de pilotage."""
    steps = [("Analyste des preuves", agent_preuves), ("Responsable qualité", agent_qualite), ("Formateur", agent_formateur),
             ("Auditeur interne", agent_auditeur), ("Actions correctives", agent_capa), ("Pilote du système", agent_pilote)]
    for name, fn in steps:
        r.log(f"— {name} —", "step")
        fn(r)
        if fn is agent_preuves and r.out.get("gap_proposals"):
            n = apply_proposals(r.cid, r.std, r.out["gap_proposals"])
            r.log(f"{n} exigence(s) sans réponse humaine pré-remplie(s) dans le diagnostic (notes « [Agent] »).")
    r.log("Mission terminée. Validez les documents et l'audit interne proposés.", "ok")


AGENTS = {
    "mission": ("Chef de mission", "Enchaîne tous les agents : preuves, documentation, formation, audit interne, actions, pilotage.", agent_mission),
    "preuves": ("Analyste des preuves", "Lit les dossiers et le Drive du client et rapproche chaque exigence de ses preuves ; propose les cotations du diagnostic.", agent_preuves),
    "qualite": ("Responsable qualité", "Construit le système documentaire : politique, cartographie, registres, objectifs, procédures, PV de revue.", agent_qualite),
    "pilote": ("Pilote du système", "Suit la mise en place jusqu'à la certification : indice de préparation, alertes, prochaines étapes.", agent_pilote),
    "auditeur": ("Auditeur interne", "Programme, conduit un audit interne proposé à partir des preuves, rédige le rapport et ouvre les actions.", agent_auditeur),
    "formateur": ("Formateur", "Plan de formation, supports, quiz, émargements et suivi des sessions.", agent_formateur),
    "capa": ("Actions correctives", "Analyse les causes des non-conformités et propose les actions, responsables et échéances.", agent_capa),
    "certification": ("Pré-certification", "Simule les étapes 1 et 2 de l'audit de certification et liste les points bloquants.", agent_certification),
}


def run_sync(cid: int, agent: str, std: str) -> int:
    rid = store.create_run(cid, agent, std)
    _execute(rid, cid, agent, std)
    return rid


def start(cid: int, agent: str, std: str) -> int:
    rid = store.create_run(cid, agent, std)
    threading.Thread(target=_execute, args=(rid, cid, agent, std), daemon=True).start()
    return rid


_lock = threading.Lock()


def _execute(rid: int, cid: int, agent: str, std: str) -> None:
    client = store.get_client(cid)
    r = Run(rid, client, std, agent)
    with _lock:  # un agent à la fois : évite les écritures concurrentes
        try:
            r.log(f"Agent {AGENTS[agent][0]} démarré — {client['name']} — {std}.", "step")
            AGENTS[agent][2](r)
            r.save()
            store.update_run(rid, status="Terminé")
        except Exception as e:
            r.log(f"Erreur : {type(e).__name__} : {e}", "error")
            r.log(traceback.format_exc()[-600:], "error")
            store.update_run(rid, status="Échec")
