"""Pilotes IA : un co-pilote par processus du SMOE (ISO 21001).

Chaque pilote IA surveille son processus, relance, prépare et alerte. Il n'a que des droits de préparation :
il ne change jamais un statut saisi par une personne, ne clôture ni action ni non-conformité, ne valide aucun document.
Les décisions reviennent au pilote humain nommé (ISO 21001, 5.3 : les responsabilités sont attribuées à des personnes).
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from . import agents, campus, smoe, store

SCHEMA = """
CREATE TABLE IF NOT EXISTS p_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, process TEXT, level TEXT,
  message TEXT, created_at TEXT, status TEXT DEFAULT 'Nouvelle', run_id INTEGER);
"""

RIGHTS = ["Lire les registres, indicateurs et documents de son processus", "Relancer les dossiers en retard (liste de relance)",
          "Ouvrir une action sur un indicateur sous la cible", "Préparer les documents de pilotage (statut « À valider »)", "Alerter le pilote humain"]
FORBIDDEN = ["Changer un statut saisi par une personne", "Clôturer une action ou une non-conformité", "Valider un document", "Modifier une cible"]

# code : (nom du pilote IA, mission, ce qu'il surveille, routine hebdomadaire, quand il escalade)
PILOTS = {
    "DIR": ("Pilote IA Stratégie", "Tenir le cap des objectifs et préparer les décisions de la direction.",
            ["Objectifs qualité et leurs échéances", "Risques critiques (gravité × probabilité ≥ 9)", "Date de la prochaine revue de direction"],
            ["Point d'avancement des objectifs", "Revue des risques critiques ouverts", "Préparation de la revue de direction à J-30"],
            ["Objectif échu non atteint", "Risque critique sans action", "Revue de direction dans moins de 30 jours sans dossier"]),
    "PAC": ("Pilote IA Amélioration", "Faire vivre l'amélioration continue : audits, non-conformités, satisfaction.",
            ["Programme d'audit", "Non-conformités et leur délai de 30 jours", "Actions correctives", "Enquêtes de satisfaction"],
            ["Suivi du programme d'audit", "Relance des NC et actions échues", "Synthèse de satisfaction"],
            ["Audit programmé non réalisé", "NC ouverte au-delà de 30 jours", "Satisfaction sous la cible"]),
    "PED-04": ("Pilote IA Pédagogie", "Garantir que les enseignements prévus sont délivrés et évalués.",
               ["Séances programmées et réalisées", "Syllabus non validés", "Séances à rattraper", "Évaluation des enseignements"],
               ["Taux de réalisation par module", "Relance des rattrapages", "Relance des syllabus en attente"],
               ["Module sous 90 % de séances réalisées", "Rattrapage en attente depuis plus de 14 jours", "Satisfaction d'un module sous 60 %"]),
    "GSP-05": ("Pilote IA Stages", "Placer chaque apprenant en stage et tenir les soutenances à la date prévue.",
               ["Demandes de convention (délai 5 jours)", "PFE et dates de soutenance", "Taux de placement par promotion"],
               ["Relance des conventions en attente", "Soutenances des 14 prochains jours", "Placement par promotion"],
               ["Convention en attente au-delà du délai", "Soutenance dans moins de 14 jours sans avancement", "Placement sous la cible"]),
    "EXD-06": ("Pilote IA Examens", "Publier les résultats à temps et traiter chaque réclamation sur les notes.",
               ["Sessions et délai de publication (15 jours)", "Réclamations sur les notes (7 jours)", "Taux de réussite"],
               ["Sessions à publier", "Relance des réclamations", "Analyse des taux de réussite"],
               ["Résultats non publiés 12 jours après le dernier examen", "Réclamation hors délai", "Taux de réussite d'un niveau sous 70 %"]),
    "GSA-07": ("Pilote IA Scolarité", "Remettre chaque document de scolarité en moins de 3 jours.",
               ["Demandes de documents (guichet)", "Documents prêts non remis", "Inscriptions par niveau"],
               ["Relance des documents en retard", "Documents prêts à faire retirer", "Taux de remplissage des niveaux"],
               ["Document en retard", "Document prêt non retiré depuis 5 jours"]),
    "GRH-08": ("Pilote IA Compétences", "Faire réaliser le plan de formation et les entretiens.",
               ["Plan de formation du personnel", "Entretiens d'évaluation", "Fiches de poste"],
               ["Formations passées non réalisées", "Entretiens à planifier", "Fiches de poste à valider"],
               ["Formation prévue passée sans réalisation", "Plan de formation sous la cible"]),
    "GSG": ("Pilote IA Services généraux", "Servir chaque demande à temps et tenir les plannings.",
            ["Demandes du guichet et leurs échéances", "Plannings de nettoyage, gardiennage, maintenance", "Réclamations", "Fiches de vie des équipements"],
            ["Relance des demandes en retard", "Tâches de planning non cochées", "Équipements les plus défaillants"],
            ["Demande en retard", "Réclamation hors délai", "Équipement avec 3 pannes ou plus en 12 mois"]),
    "GVU-10": ("Pilote IA Vie universitaire", "Animer la vie des apprenants et instruire vite les demandes d'activité.",
               ["Demandes d'activité (7 jours)", "Participation aux activités", "Clubs actifs"],
               ["Demandes d'activité en attente", "Bilan de participation", "Clubs inactifs"],
               ["Demande d'activité hors délai", "Participation sous la cible"]),
    "GAF-11": ("Pilote IA Finances", "Exécuter le budget et recevoir les achats dans les délais.",
               ["Exécution budgétaire par rubrique", "Achats et leur délai de 45 jours", "Évaluation des fournisseurs"],
               ["Achats en retard", "Rubriques sous-consommées", "Fournisseurs à surveiller"],
               ["Achat en retard", "Rubrique sous 50 % d'exécution au second semestre", "Fournisseur à surveiller relancé"]),
}
ORDER = ["DIR", "PAC", "PED-04", "GSP-05", "EXD-06", "GSA-07", "GRH-08", "GSG", "GVU-10", "GAF-11"]


def init() -> None:
    with store.conn() as c:
        c.executescript(SCHEMA)


def _days(a: str | None, b: dt.date | None = None) -> float:
    x = campus._d(a)
    return ((dt.datetime.combine(b or dt.date.today(), dt.time()) - x).total_seconds() / 86400) if x else 0


def human(cid: int, code: str) -> str:
    v = store.get_setting(f"pilots.human.{cid}.{code}")
    if v:
        return v
    if code == "GSG":
        return "Secrétaire général"
    return smoe.PROCESSES[code]["pilot"]


def set_human(cid: int, code: str, name: str) -> None:
    if code not in PILOTS:
        raise ValueError("Processus inconnu")
    store.set_setting(f"pilots.human.{cid}.{code}", name.strip()[:120])


def auto(cid: int) -> str:
    return store.get_setting(f"pilots.auto.{cid}") or "off"


def set_auto(cid: int, mode: str) -> None:
    if mode not in ("off", "quotidien", "hebdomadaire"):
        raise ValueError("Mode inconnu")
    store.set_setting(f"pilots.auto.{cid}", mode)


# ------------------------------------------------------------------ règles de surveillance propres à chaque processus
def _checks(cid: int, code: str) -> list[tuple[str, str, str]]:
    """(niveau, message, relance éventuelle). niveau : alerte (escalade au pilote humain) | info."""
    out: list[tuple[str, str, str]] = []
    today = dt.date.today()
    rec = lambda reg: smoe.records(cid, code, reg, 5000)
    d = lambda r, k: r["data"].get(k) or ""
    if code == "DIR":
        for r in rec("objectifs"):
            if r["status"] == "En cours" and d(r, "echeance") and d(r, "echeance") < today.isoformat():
                out.append(("alerte", f"Objectif échu non atteint : « {d(r, 'objectif')} » ({d(r, 'processus')}).", "Décider : prolonger, réviser ou déclarer non atteint"))
        for r in rec("risques"):
            g = float(r["data"].get("gravite") or 0) * float(r["data"].get("probabilite") or 0)
            if g >= 9 and r["status"] == "Ouvert":
                out.append(("alerte", f"Risque critique ouvert (G×P = {g:g}) : {d(r, 'risque')}.", f"Responsable du processus {d(r, 'processus')}"))
        nxt = [r for r in rec("revues") if r["status"] == "Planifiée" and d(r, "date") >= today.isoformat()]
        for r in nxt:
            j = (dt.date.fromisoformat(d(r, "date")) - today).days
            if j <= 30:
                out.append(("alerte", f"Revue de direction dans {j} jour(s) : lancer l'agent Revue de direction pour préparer le dossier.", ""))
        if not nxt:
            out.append(("info", "Aucune revue de direction planifiée : en planifier une (au moins une par an).", ""))
    elif code == "PAC":
        for r in rec("audits"):
            if r["status"] == "Planifié" and d(r, "date") and d(r, "date") < today.isoformat():
                out.append(("alerte", f"Audit programmé non réalisé : processus {d(r, 'processus')} (prévu le {d(r, 'date')}).", "Auditeur désigné"))
        for r in rec("nc"):
            if r["late"] and r["status"] != "Clôturée":
                out.append(("alerte", f"Non-conformité hors délai : {r['title']} ({d(r, 'processus')}).", f"Pilote du processus {d(r, 'processus')}"))
        late_acts = [a for a in store.list_actions(cid, None) if a["status"] != "Clôturée" and a["due"] and a["due"] < today.isoformat()]
        if late_acts:
            out.append(("alerte", f"{len(late_acts)} action(s) corrective(s) échue(s) non clôturée(s).", "Responsables des actions"))
    elif code == "PED-04":
        for r in rec("seances"):
            p, s = float(r["data"].get("programmees") or 0), float(r["data"].get("realisees") or 0)
            if p and s / p < 0.9:
                out.append(("alerte", f"Module {d(r, 'module')} ({d(r, 'niveau')}) : {s:g}/{p:g} séances réalisées.", f"Enseignant {d(r, 'enseignant')}"))
        for r in rec("rattrapages"):
            if r["status"] == "À rattraper" and _days(r["created_at"]) > 14:
                out.append(("alerte", f"Rattrapage en attente depuis {int(_days(r['created_at']))} jours : {d(r, 'module')}.", "Responsable du module"))
        for r in rec("syllabus"):
            if r["status"] != "Validé":
                out.append(("info", f"Syllabus non validé : {d(r, 'module')} ({r['status']}).", f"{d(r, 'responsable')}"))
        for r in rec("evaluations"):
            n, s = float(r["data"].get("repondants") or 0), float(r["data"].get("satisfaits") or 0)
            if n and s / n < 0.6:
                out.append(("alerte", f"Satisfaction faible sur {d(r, 'module')} : {round(100 * s / n)} %.", "Entretien avec l'enseignant"))
    elif code == "GSP-05":
        for r in rec("conventions"):
            if r["status"] == "Demandée" and r["late"]:
                out.append(("alerte", f"Convention en attente hors délai : {d(r, 'etudiant')} chez {d(r, 'entreprise')}.", "Service des stages"))
        for r in rec("pfe"):
            if r["status"] in ("Affecté", "En cours") and d(r, "prevue"):
                j = (dt.date.fromisoformat(d(r, "prevue")) - today).days
                if 0 <= j <= 14:
                    out.append(("alerte" if r["status"] == "Affecté" else "info", f"Soutenance dans {j} jour(s) : « {d(r, 'sujet')} » ({r['status']}).", f"Encadrant {d(r, 'encadrant')}"))
    elif code == "EXD-06":
        for r in rec("sessions"):
            if r["status"] != "Publiée" and d(r, "dernier_examen") and _days(d(r, "dernier_examen")) > 12:
                out.append(("alerte", f"Résultats non publiés : {d(r, 'session')} {d(r, 'niveau')}, dernier examen il y a {int(_days(d(r, 'dernier_examen')))} jours.", "Président du jury"))
            ins, adm = float(r["data"].get("inscrits") or 0), float(r["data"].get("admis") or 0)
            if ins and adm / ins < 0.7:
                out.append(("info", f"Taux de réussite {round(100 * adm / ins)} % en {d(r, 'niveau')} ({d(r, 'session')}) : à analyser en conseil pédagogique.", ""))
        for r in rec("reclamations_notes"):
            if r["status"] == "Déposée" and r["late"]:
                out.append(("alerte", f"Réclamation sur note hors délai : {d(r, 'module')} ({d(r, 'etudiant')}).", "Enseignant du module"))
    elif code == "GSA-07":
        for r in rec("documents"):
            if r["status"] == "Demandée" and r["late"]:
                out.append(("alerte", f"Document en retard : {d(r, 'document')} pour {d(r, 'etudiant')} (échéance {r['due']}).", "Agent de scolarité"))
            if r["status"] == "Prête" and _days(r["created_at"]) > 5:
                out.append(("info", f"Document prêt non retiré : {d(r, 'document')} pour {d(r, 'etudiant')}.", "Prévenir l'étudiant"))
    elif code == "GRH-08":
        for r in rec("formations"):
            if r["status"] == "Planifiée" and d(r, "date") and d(r, "date") < today.isoformat():
                out.append(("alerte", f"Formation prévue le {d(r, 'date')} non réalisée : {d(r, 'theme')}.", "Responsable RH"))
        for r in rec("entretiens"):
            if r["status"] == "Planifié" and d(r, "date") and d(r, "date") < today.isoformat():
                out.append(("info", f"Entretien d'évaluation en retard : {d(r, 'poste')}.", "Responsable hiérarchique"))
        for r in rec("postes"):
            if r["status"] != "Validée":
                out.append(("info", f"Fiche de poste à valider : {d(r, 'poste')}.", ""))
    elif code == "GVU-10":
        for r in rec("activites"):
            if r["status"] == "Demandée" and r["late"]:
                out.append(("alerte", f"Demande d'activité sans réponse : {r['title']} ({d(r, 'club')}).", "Responsable vie universitaire"))
        for r in rec("clubs"):
            if r["status"] == "Inactif":
                out.append(("info", f"Club inactif : {d(r, 'club')} : relancer ou fermer.", ""))
    elif code == "GAF-11":
        for r in rec("achats"):
            if r["status"] in ("Demandé", "Commandé") and r["late"]:
                out.append(("alerte", f"Achat en retard : {d(r, 'objet')} ({d(r, 'service')}, {d(r, 'montant')} TND).", f"Fournisseur {d(r, 'fournisseur')}"))
        if today.month >= 7 or today.month <= 1:
            for r in rec("budget"):
                b, e = float(r["data"].get("budget") or 0), float(r["data"].get("engage") or 0)
                if b and e / b < 0.5:
                    out.append(("alerte", f"Rubrique sous-consommée : {d(r, 'rubrique')} ({round(100 * e / b)} %).", ""))
        for r in rec("fournisseurs"):
            if r["status"] == "À surveiller":
                out.append(("info", f"Fournisseur à surveiller : {d(r, 'fournisseur')} (note {d(r, 'note')}/20).", ""))
    elif code == "GSG":
        late = [q for q in campus.list_requests(cid, limit=3000) if q["status"] in ("Nouvelle", "Planifiée", "En cours") and q["late"]]
        for q in late[:15]:
            out.append(("alerte", f"Demande en retard : {q['type_label']} · {q['title']} ({q['dept'] or q['requester']}).", q["assignee"] or q["service"]))
        for c in [c for c in campus.list_complaints(cid, 1000) if c["late"]][:10]:
            out.append(("alerte", f"Réclamation hors délai : {c['subject'][:80]} ({c['service']}).", c["service"]))
        s = campus.summary(cid)
        if s["tasks_overdue"]:
            out.append(("info", f"{s['tasks_overdue']} tâche(s) de planning non cochée(s) sur 30 jours.", "Chefs d'équipe"))
        for a in [a for a in campus.list_assets(cid) if a["curatives_12m"] >= 3][:5]:
            out.append(("alerte", f"Équipement défaillant : {a['label']} ({a['location']}), {a['curatives_12m']} pannes en 12 mois.", "Inscrire au budget (GAF-11)"))
    return out


def _health(inds: list[dict], n_alerts: int) -> int:
    m = [i for i in inds if i["ok"] is not None]
    base = 100 * sum(1 for i in m if i["ok"]) / len(m) if m else 50
    return max(0, round(base - min(30, 3 * n_alerts)))


def run_pilot(r, code: str) -> dict:
    name, mission, watch, weekly, escal = PILOTS[code]
    k = [i for i in campus.compute(r.cid)["indicators"] if i["process"] == code]
    checks = _checks(r.cid, code)
    alerts = [c for c in checks if c[0] == "alerte"]
    ko = [i for i in k if i["ok"] is False]
    existing = {(a["clause"], a["status"]) for a in store.list_actions(r.cid, None)}
    opened = 0
    for i in ko:
        if (i["code"], "Ouverte") in existing or (i["code"], "En cours") in existing:
            continue
        store.add_action(r.cid, {"standard": "ISO 21001", "source": name, "clause": i["code"], "finding": f"{i['name']} : {i['value']} pour une cible de {i['target']}.",
                                 "cause": "À analyser avec le pilote du processus.", "action": "Plan d'amélioration à décider par le pilote.", "owner": human(r.cid, code),
                                 "due": agents._today(30), "status": "Ouverte"})
        opened += 1
    health = _health(k, len(alerts))
    now = campus._now()
    store._exec("UPDATE p_alerts SET status='Remplacée' WHERE client_id=? AND process=? AND status='Nouvelle'", (r.cid, code))
    for lvl, msg, _ in checks:
        store._exec("INSERT INTO p_alerts(client_id,process,level,message,created_at,run_id) VALUES (?,?,?,?,?,?)", (r.cid, code, lvl, msg, now, r.rid))
    store.set_setting(f"pilots.last.{r.cid}.{code}", f"{now}|{health}|{len(alerts)}")
    r.log(f"{name} · santé {health}/100 · {len(alerts)} alerte(s) pour {human(r.cid, code)} · {opened} action(s) ouverte(s).", "warn" if alerts else "ok")
    fmt = lambda i: "—" if i["value"] is None else (f"{i['value']} j" if i["lower_better"] else f"{i['value']} %")
    r.doc({"kind": "pilote_ia", "title": f"Point du {name} ({code}) — {r.client['name']}", "client": r.client["name"], "date": agents._today(), "ai": False, "standard": "ISO 21001",
           "footer": f"Préparé par le {name}, co-pilote du processus. Décisions et validation : {human(r.cid, code)}.",
           "sections": [
               {"heading": "En bref", "paragraphs": [f"Santé du processus : {health}/100. {len(alerts)} point(s) à décider par le pilote, {len(checks) - len(alerts)} information(s), {opened} action(s) ouverte(s) sur des indicateurs sous la cible."]},
               {"heading": "Indicateurs", "table": {"columns": ["Code", "Indicateur", "Valeur", "Cible", "Statut"], "rows": [[i["code"], i["name"], fmt(i), i["target"], "Atteint" if i["ok"] else "Sous la cible" if i["ok"] is False else "À mesurer"] for i in k]}},
               {"heading": f"À décider par {human(r.cid, code)}", "table": {"columns": ["Constat", "À relancer"], "rows": [[m, w] for _, m, w in alerts]}} if alerts else {"heading": "À décider", "paragraphs": ["Rien à escalader cette semaine."]},
               {"heading": "Informations", "bullets": [m for lv, m, _ in checks if lv == "info"] or ["Aucune."]},
               {"heading": "Ce que le pilote IA a fait", "bullets": [f"Analysé {len(k)} indicateur(s) et les registres du processus", f"Ouvert {opened} action(s) d'amélioration (statut « Ouverte », à confirmer)", "Préparé ce point au statut « À valider »"]},
               {"heading": "Mandat du pilote IA", "table": {"columns": ["Peut", "Ne peut pas"], "rows": [[a, b] for a, b in zip(RIGHTS, FORBIDDEN + [""])]}}]})
    return {"code": code, "health": health, "alerts": len(alerts), "opened": opened}


def agent_all(r) -> None:
    res = [run_pilot(r, c) for c in ORDER]
    worst = sorted(res, key=lambda x: x["health"])[:3]
    fragile = ", ".join("%s (%s/100)" % (x["code"], x["health"]) for x in worst)
    r.log(f"10 pilotes IA passés. Processus les plus fragiles : {fragile}.", "ok")
    r.out["pilots"] = res


def status(cid: int) -> list[dict]:
    out = []
    for c in ORDER:
        name, mission, watch, weekly, escal = PILOTS[c]
        last = (store.get_setting(f"pilots.last.{cid}.{c}") or "").split("|")
        al = store._rows("SELECT level, message, created_at FROM p_alerts WHERE client_id=? AND process=? AND status='Nouvelle' ORDER BY level, id", (cid, c))
        pname = "Services généraux" if c == "GSG" else smoe.PROCESSES[c]["name"]
        out.append({"code": c, "process": pname, "ai": name, "mission": mission, "watch": watch, "weekly": weekly, "escalation": escal, "human": human(cid, c),
                    "last_run": last[0] if last[0] else None, "health": int(last[1]) if len(last) > 1 else None, "alerts": al})
    return out


def ack(aid: int) -> None:
    store._exec("UPDATE p_alerts SET status='Vue' WHERE id=?", (aid,))


agents.AGENTS.update({"pia_tous": ("Pilotes IA", "Fait passer les 10 pilotes IA : santé de chaque processus, alertes au pilote humain, actions sur les écarts, point hebdomadaire.", agent_all)})
for _c in ORDER:
    agents.AGENTS[f"pia_{_c}"] = (PILOTS[_c][0], PILOTS[_c][1], (lambda code: lambda r: run_pilot(r, code))(_c))


# ------------------------------------------------------------------ passage automatique (poste hôte allumé)
def _due(cid: int, mode: str, now: dt.datetime) -> bool:
    if mode == "off" or now.hour < 7 or (mode == "hebdomadaire" and now.weekday() != 0):
        return False
    return (store.get_setting(f"pilots.autolast.{cid}") or "") < now.date().isoformat()


def scheduler_loop(stop: threading.Event, every: int = 600) -> None:
    while not stop.wait(every):
        try:
            now = dt.datetime.now()
            for c in store.list_clients():
                if _due(c["id"], auto(c["id"]), now):
                    store.set_setting(f"pilots.autolast.{c['id']}", now.date().isoformat())
                    agents.start(c["id"], "pia_tous", "ISO 21001")
        except Exception:  # le planificateur ne doit jamais arrêter le serveur
            time.sleep(5)


_stop = threading.Event()


def start_scheduler() -> None:
    threading.Thread(target=scheduler_loop, args=(_stop,), daemon=True).start()
