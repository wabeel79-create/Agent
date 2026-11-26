"""Kapsi Campus : gestion opérationnelle d'un établissement d'enseignement (ISO 21001).

Idée : chaque demande du quotidien (tirage, intervention, véhicule, fournitures, clé, courrier, réclamation)
devient un enregistrement ISO 21001. Les indicateurs du processus Services généraux (fiche GSG-PP)
se calculent tout seuls à partir de ces enregistrements, et les agents planifient, relancent et rédigent.
Le responsable valide.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import secrets

from . import agents, store

STD = "ISO 21001"

SCHEMA = """
CREATE TABLE IF NOT EXISTS c_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, type TEXT, form TEXT,
  requester TEXT, dept TEXT, title TEXT, details TEXT DEFAULT '{}', qty INTEGER DEFAULT 1, priority TEXT DEFAULT 'Normale',
  service TEXT, assignee TEXT, status TEXT DEFAULT 'Nouvelle', needed_by TEXT, created_at TEXT, done_at TEXT,
  received_at TEXT, satisfied INTEGER, remark TEXT, ticket TEXT);
CREATE TABLE IF NOT EXISTS c_assets (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, category TEXT, code TEXT,
  location TEXT, label TEXT, qty INTEGER DEFAULT 1, state TEXT DEFAULT 'En service', data TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS c_interventions (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, asset_id INTEGER,
  kind TEXT, nature TEXT, intervenant TEXT, date TEXT, description TEXT, cost REAL DEFAULT 0, downtime REAL DEFAULT 0,
  effective INTEGER DEFAULT 1, request_id INTEGER);
CREATE TABLE IF NOT EXISTS c_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, plan TEXT, label TEXT,
  location TEXT, who TEXT, date TEXT, done INTEGER DEFAULT 0, note TEXT, asset_id INTEGER);
CREATE TABLE IF NOT EXISTS c_mail (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, direction TEXT, number TEXT,
  date TEXT, correspondent TEXT, subject TEXT, service TEXT, status TEXT DEFAULT 'Enregistré', due TEXT, done_at TEXT);
CREATE TABLE IF NOT EXISTS c_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, date TEXT, caller TEXT,
  subject TEXT, routed_to TEXT, outcome TEXT);
CREATE TABLE IF NOT EXISTS c_complaints (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, date TEXT, source TEXT,
  channel TEXT, service TEXT, subject TEXT, status TEXT DEFAULT 'Ouverte', due TEXT, closed_at TEXT, satisfied INTEGER,
  response TEXT, ticket TEXT);
CREATE TABLE IF NOT EXISTS c_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, date TEXT, items INTEGER,
  nc INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS c_measures (client_id INTEGER, process TEXT, code TEXT, period TEXT, value REAL, note TEXT,
  PRIMARY KEY (client_id, process, code, period));
"""

# ------------------------------------------------------------------ référentiel
# Types de demandes : (libellé, formulaire, service, délai de traitement en jours, famille d'indicateur)
TYPES = {
    "tirage": ("Demande de tirage", "GSG-FR-03", "Tirage", 2, "tirage"),
    "intervention": ("Demande d'intervention", "GSG-FR-05", "Maintenance", 3, "logistique"),
    "informatique": ("Intervention informatique (SI)", "GSG-FR-05", "Informatique", 2, "logistique"),
    "vehicule": ("Demande de véhicule administratif", "GSG-FR-02", "Parc roulant", 3, "logistique"),
    "salle": ("Réservation de salle ou d'amphi", "GSG-FR-02", "Services généraux", 2, "logistique"),
    "video": ("Demande de vidéoprojecteur", "GSG-FR-13", "Services généraux", 1, "logistique"),
    "fourniture": ("Demande de fournitures", "GSG-FR-08", "Magasin", 3, "logistique"),
    "stylos": ("Demande de stylos pour tableau", "GSG-FR-14", "Magasin", 1, "logistique"),
    "cle": ("Demande de clé", "GSG-FR-12", "Accueil et sécurité", 1, "logistique"),
    "nettoyage": ("Demande de nettoyage", "GSG-FR-05", "Nettoyage", 1, "logistique"),
    "archive": ("Demande d'archivage ou de consultation", "GSG-PR-07", "Archives", 5, "logistique"),
}
STATUSES = ["Nouvelle", "Planifiée", "En cours", "Réalisée", "Réceptionnée", "Refusée"]
PLANS = {
    "nettoyage": ("Planning de nettoyage", "GSG-PL-02"),
    "gardiennage": ("Planning de gardiennage", "GSG-PL-01"),
    "tirage": ("Planning des agents de tirage", "GSG-PL-03"),
    "infrastructure": ("Planning d'entretien préventif de l'infrastructure", "GSG-PL-04"),
    "maintenance_info": ("Planning de maintenance préventive du matériel informatique", "GSG-PL-05"),
    "maintenance_impr": ("Planning de maintenance préventive du matériel d'impression", "GSG-PL-06"),
    "parc": ("Entretien préventif du parc roulant", "GSG-PR-05"),
}
CATEGORIES = {"informatique": ("Matériel informatique", "GSG-FR-06", "maintenance_info", 90),
              "impression": ("Matériel d'impression", "GSG-FR-04", "maintenance_impr", 30),
              "infrastructure": ("Infrastructure et équipements", "GSG-FR-15", "infrastructure", 180),
              "vehicule": ("Parc roulant", "GSG-FR-10", "parc", 180)}

# Cartographie type d'un établissement (codes de l'ISI quand ils figurent dans la fiche GSG-PP)
PROCESSES = [
    ("DIR", "Management", "Pilotage et stratégie de l'établissement", "Directeur", "4, 5, 6, 9.3", "auto"),
    ("PAC", "Management", "Amélioration continue (audits, non-conformités, enquêtes de satisfaction)", "RSMOE", "9.1, 9.2, 10", "qualite"),
    ("PED-04", "Réalisation", "Gestion des activités pédagogiques", "Directeur des études", "8.2, 8.3, 8.5, 7.1.6", "manuel"),
    ("GSP-05", "Réalisation", "Stages et projets de fin d'études", "Responsable des stages", "8.5, 8.4", "manuel"),
    ("EXD-06", "Réalisation", "Examens et délibérations", "Directeur des études", "8.5.1, 8.6, 8.7", "manuel"),
    ("GSA-07", "Réalisation", "Scolarité (inscriptions, attestations, diplômes)", "Secrétaire général", "8.5, 8.5.3, 7.5", "manuel"),
    ("GRH-08", "Support", "Ressources humaines et compétences", "Secrétaire général", "7.1.2, 7.2, 7.3", "manuel"),
    ("GSG", "Support", "Services généraux (environnement, sécurité, logistique, tirage, SI, archives)", "Secrétaire général", "7.1.3, 7.1.4, 7.1.5, 7.5, 8.4", "auto"),
    ("GVU-10", "Support", "Vie universitaire (clubs, activités, accueil des apprenants)", "Responsable vie universitaire", "7.1.4, 8.5.4", "manuel"),
    ("GAF-11", "Support", "Finances et achats", "Secrétaire général", "7.1.1, 8.4", "manuel"),
]

# Indicateurs. GSG : formules exactes de la fiche processus GSG-PP (calcul automatique).
# Autres processus : indicateurs proposés, à valider par les pilotes, saisis chaque période.
INDICATORS = [
    ("GSG", "GSG-1", "Taux de maîtrise de la planification des interventions de nettoyage", "Actions réalisées / actions planifiées × 100", "Trimestrielle", 90, "Planning nettoyage, fiche d'intervention nettoyage"),
    ("GSG", "GSG-2", "Taux de maîtrise de la planification des activités de gardiennage", "Actions réalisées / actions planifiées × 100", "Semestrielle", 95, "Planning de gardiennage, fiche de pointage"),
    ("GSG", "GSG-3", "Taux de respect des demandes de moyens logistiques", "Demandes satisfaites / demandes effectuées × 100", "Semestrielle", 85, "Registre de suivi des demandes de moyens logistiques"),
    ("GSG", "GSG-4", "Taux de respect des demandes de tirage dans les délais", "Demandes satisfaites dans le délai / demandes effectuées × 100", "Semestrielle", 90, "Registre de suivi de tirage"),
    ("GSG", "GSG-5", "Taux de conformité de gestion de l'archive", "1 − (NC de l'inventaire / somme des inventaires)", "Annuelle", 95, "PV d'inventaire de l'archive"),
    ("GSG", "GSG-6", "Taux de traitement efficace des réclamations", "Réclamations traitées dans le délai et satisfaites / total × 100", "Semestrielle", 80, "Registre des réclamations"),
    ("GSG", "GSG-7a", "Taux de maintenance préventive du parc informatique", "Interventions réalisées / interventions planifiées × 100", "Semestrielle", 90, "Planning de maintenance préventive du parc informatique"),
    ("GSG", "GSG-7b", "Taux d'efficacité des interventions curatives sur l'infrastructure SI", "Interventions curatives efficaces / interventions × 100", "Semestrielle", 85, "Registre de maintenance"),
    ("PED-04", "PED-1", "Taux de réalisation des séances d'enseignement programmées", "Séances réalisées / séances programmées × 100", "Semestrielle", 95, "Cahiers de textes, emplois du temps"),
    ("PED-04", "PED-2", "Satisfaction des apprenants sur les enseignements", "Réponses satisfaites / réponses × 100", "Semestrielle", 75, "Enquête d'évaluation des enseignements"),
    ("GSP-05", "GSP-1", "Taux d'apprenants ayant trouvé un stage dans les délais", "Apprenants placés / apprenants concernés × 100", "Annuelle", 90, "Registre des conventions de stage"),
    ("GSP-05", "GSP-2", "Taux de soutenances de PFE dans les délais", "Soutenances dans les délais / PFE × 100", "Annuelle", 90, "Planning des soutenances"),
    ("EXD-06", "EXD-1", "Délai moyen de publication des résultats (jours)", "Moyenne (date publication − date dernier examen)", "Semestrielle", 15, "PV de délibération"),
    ("EXD-06", "EXD-2", "Taux de réclamations sur les notes traitées dans les délais", "Réclamations traitées dans le délai / total × 100", "Semestrielle", 90, "Registre des réclamations de notes"),
    ("GSA-07", "GSA-1", "Délai moyen de délivrance des attestations (jours)", "Moyenne (date remise − date demande)", "Semestrielle", 3, "Registre des demandes d'attestations"),
    ("GRH-08", "GRH-1", "Taux de réalisation du plan de formation du personnel", "Formations réalisées / formations planifiées × 100", "Annuelle", 80, "Plan de formation"),
    ("GVU-10", "GVU-1", "Taux de participation des apprenants aux activités", "Participants / effectif × 100", "Annuelle", 30, "Registres des clubs et événements"),
    ("GAF-11", "GAF-1", "Taux d'exécution du budget", "Dépenses engagées / budget × 100", "Annuelle", 90, "Situation budgétaire"),
    ("PAC", "PAC-1", "Taux de clôture des actions correctives dans les délais", "Actions clôturées dans les délais / actions × 100", "Semestrielle", 80, "Plan d'actions"),
]
LOWER_IS_BETTER = {"EXD-1", "GSA-1"}


def init() -> None:
    with store.conn() as c:
        c.executescript(SCHEMA)


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _d(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for f, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return dt.datetime.strptime(s[:n], f)
        except ValueError:
            continue
    return None


def _rows(sql, args=()):
    return store._rows(sql, args)


def _exec(sql, args=()):
    return store._exec(sql, args)


# ------------------------------------------------------------------ guichet (code d'accès)
def guichet_code(cid: int, renew: bool = False) -> str:
    key = f"campus.code.{cid}"
    code = store.get_setting(key)
    if not code or renew:
        code = f"{secrets.randbelow(900000) + 100000}"
        store.set_setting(key, code)
    return code


def check_code(cid: int, code: str) -> bool:
    return bool(code) and secrets.compare_digest(str(code), guichet_code(cid))


# ------------------------------------------------------------------ demandes
def _ticket(prefix: str = "D") -> str:
    return f"{prefix}-{dt.datetime.now():%y%m}-{secrets.token_hex(2).upper()}"


def add_request(cid: int, d: dict, now: str | None = None) -> dict:
    t = d.get("type")
    if t not in TYPES:
        raise ValueError("Type de demande inconnu")
    label, form, service, delay, _ = TYPES[t]
    now = now or _now()
    need = d.get("needed_by") or (_d(now) + dt.timedelta(days=delay)).strftime("%Y-%m-%d %H:%M")
    if t == "tirage" and _d(need) and _d(need) < _d(now) + dt.timedelta(hours=48):
        need = (_d(now) + dt.timedelta(hours=48)).strftime("%Y-%m-%d %H:%M")  # GSG-FR-03 : dépôt 48 h à l'avance
    ticket = d.get("ticket") or _ticket()
    rid = _exec("""INSERT INTO c_requests(client_id,type,form,requester,dept,title,details,qty,priority,service,status,needed_by,created_at,ticket)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, t, form, (d.get("requester") or "").strip()[:120], (d.get("dept") or "").strip()[:120],
                 (d.get("title") or label).strip()[:200], json.dumps(d.get("details") or {}, ensure_ascii=False),
                 int(d.get("qty") or 1), d.get("priority") or "Normale", service, d.get("status") or "Nouvelle", need, now, ticket))
    return get_request(rid)


def get_request(rid: int) -> dict | None:
    r = _rows("SELECT * FROM c_requests WHERE id=?", (rid,))
    if not r:
        return None
    r = r[0]
    r["details"] = json.loads(r["details"] or "{}")
    r["type_label"] = TYPES.get(r["type"], (r["type"],))[0]
    r["late"] = _late(r)
    return r


def _late(r: dict) -> bool:
    end = _d(r.get("done_at")) or dt.datetime.now()
    nb = _d(r.get("needed_by"))
    return bool(nb and end > nb and r["status"] != "Refusée")


def find_ticket(cid: int, ticket: str) -> dict | None:
    r = _rows("SELECT id FROM c_requests WHERE client_id=? AND ticket=?", (cid, ticket.strip().upper()))
    return get_request(r[0]["id"]) if r else None


def list_requests(cid: int, status: str | None = None, rtype: str | None = None, limit: int = 300) -> list[dict]:
    q, a = "SELECT * FROM c_requests WHERE client_id=?", [cid]
    if status:
        q += " AND status=?"; a.append(status)
    if rtype:
        q += " AND type=?"; a.append(rtype)
    out = []
    for r in _rows(q + " ORDER BY id DESC LIMIT ?", (*a, limit)):
        r["details"] = json.loads(r["details"] or "{}")
        r["type_label"] = TYPES.get(r["type"], (r["type"],))[0]
        r["late"] = _late(r)
        out.append(r)
    return out


def update_request(rid: int, ch: dict, now: str | None = None) -> dict:
    r = get_request(rid)
    if not r:
        raise KeyError(rid)
    now = now or _now()
    st = ch.get("status")
    if st and st not in STATUSES:
        raise ValueError("Statut inconnu")
    sets, args = [], []
    for k in ("status", "assignee", "priority", "remark", "needed_by"):
        if k in ch and ch[k] is not None:
            sets.append(f"{k}=?"); args.append(ch[k])
    if st in ("Réalisée",) and not r["done_at"]:
        sets.append("done_at=?"); args.append(now)
    if st == "Réceptionnée":
        if not r["done_at"]:
            sets.append("done_at=?"); args.append(now)
        sets.append("received_at=?"); args.append(now)
        sets.append("satisfied=?"); args.append(1 if ch.get("satisfied", True) else 0)
    if sets:
        _exec(f"UPDATE c_requests SET {', '.join(sets)} WHERE id=?", (*args, rid))
    return get_request(rid)


# ------------------------------------------------------------------ équipements et fiches de vie
def add_asset(cid: int, a: dict) -> int:
    if a.get("category") not in CATEGORIES:
        raise ValueError("Catégorie inconnue")
    return _exec("INSERT INTO c_assets(client_id,category,code,location,label,qty,state,data) VALUES (?,?,?,?,?,?,?,?)",
                 (cid, a["category"], a.get("code", ""), a.get("location", ""), a.get("label", ""), int(a.get("qty") or 1),
                  a.get("state") or "En service", json.dumps(a.get("data") or {}, ensure_ascii=False)))


def list_assets(cid: int) -> list[dict]:
    out = _rows("SELECT * FROM c_assets WHERE client_id=? ORDER BY category, location, code", (cid,))
    since = (dt.datetime.now() - dt.timedelta(days=365)).strftime("%Y-%m-%d")
    cnt = {r["asset_id"]: r for r in _rows("""SELECT asset_id, SUM(kind='C') cur, SUM(kind='P') prev, SUM(cost) cost, SUM(downtime) down
                                               FROM c_interventions WHERE client_id=? AND date>=? GROUP BY asset_id""", (cid, since))}
    for a in out:
        a["data"] = json.loads(a["data"] or "{}")
        c = cnt.get(a["id"], {})
        a["curatives_12m"], a["preventives_12m"] = c.get("cur") or 0, c.get("prev") or 0
        a["cost_12m"], a["downtime_12m"] = c.get("cost") or 0, c.get("down") or 0
    return out


def add_intervention(cid: int, iv: dict) -> int:
    return _exec("""INSERT INTO c_interventions(client_id,asset_id,kind,nature,intervenant,date,description,cost,downtime,effective,request_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (cid, iv.get("asset_id"), iv.get("kind", "C"), iv.get("nature", "R"), iv.get("intervenant", "I"),
                  iv.get("date") or _now()[:10], iv.get("description", ""), float(iv.get("cost") or 0), float(iv.get("downtime") or 0),
                  1 if iv.get("effective", True) else 0, iv.get("request_id")))


def asset_life(aid: int) -> dict:
    a = _rows("SELECT * FROM c_assets WHERE id=?", (aid,))
    if not a:
        return {}
    a = a[0]; a["data"] = json.loads(a["data"] or "{}")
    a["interventions"] = _rows("SELECT * FROM c_interventions WHERE asset_id=? ORDER BY date DESC", (aid,))
    a["planned"] = _rows("SELECT * FROM c_tasks WHERE asset_id=? ORDER BY date DESC LIMIT 20", (aid,))
    return a


# ------------------------------------------------------------------ plannings
def add_task(cid: int, t: dict) -> int:
    if t.get("plan") not in PLANS:
        raise ValueError("Planning inconnu")
    return _exec("INSERT INTO c_tasks(client_id,plan,label,location,who,date,done,note,asset_id) VALUES (?,?,?,?,?,?,?,?,?)",
                 (cid, t["plan"], t.get("label", ""), t.get("location", ""), t.get("who", ""), t["date"], 1 if t.get("done") else 0,
                  t.get("note", ""), t.get("asset_id")))


def list_tasks(cid: int, plan: str | None = None, start: str | None = None, end: str | None = None) -> list[dict]:
    q, a = "SELECT * FROM c_tasks WHERE client_id=?", [cid]
    if plan:
        q += " AND plan=?"; a.append(plan)
    if start:
        q += " AND date>=?"; a.append(start)
    if end:
        q += " AND date<=?"; a.append(end)
    return _rows(q + " ORDER BY date, id", a)


def set_task(tid: int, done: bool, note: str | None = None) -> None:
    _exec("UPDATE c_tasks SET done=?, note=COALESCE(?,note) WHERE id=?", (1 if done else 0, note, tid))
    t = _rows("SELECT * FROM c_tasks WHERE id=?", (tid,))
    if done and t and t[0]["asset_id"]:  # la maintenance préventive réalisée entre dans la fiche de vie
        t = t[0]
        if not _rows("SELECT id FROM c_interventions WHERE asset_id=? AND kind='P' AND date=?", (t["asset_id"], t["date"])):
            add_intervention(t["client_id"], {"asset_id": t["asset_id"], "kind": "P", "nature": "E", "date": t["date"], "description": t["label"]})


# ------------------------------------------------------------------ courrier, appels, réclamations, archive
def add_mail(cid: int, m: dict) -> int:
    n = (_rows("SELECT COUNT(*) n FROM c_mail WHERE client_id=? AND direction=?", (cid, m.get("direction", "entrant")))[0]["n"] or 0) + 1
    return _exec("INSERT INTO c_mail(client_id,direction,number,date,correspondent,subject,service,status,due) VALUES (?,?,?,?,?,?,?,?,?)",
                 (cid, m.get("direction", "entrant"), m.get("number") or f"{dt.date.today():%Y}/{n:04d}", m.get("date") or _now()[:10],
                  m.get("correspondent", ""), m.get("subject", ""), m.get("service", ""), m.get("status") or "Enregistré", m.get("due")))


def list_mail(cid: int, limit: int = 200) -> list[dict]:
    return _rows("SELECT * FROM c_mail WHERE client_id=? ORDER BY date DESC, id DESC LIMIT ?", (cid, limit))


def update_mail(mid: int, status: str) -> None:
    _exec("UPDATE c_mail SET status=?, done_at=CASE WHEN ?='Traité' THEN ? ELSE done_at END WHERE id=?", (status, status, _now()[:10], mid))


def add_call(cid: int, c: dict) -> int:
    return _exec("INSERT INTO c_calls(client_id,date,caller,subject,routed_to,outcome) VALUES (?,?,?,?,?,?)",
                 (cid, c.get("date") or _now(), c.get("caller", ""), c.get("subject", ""), c.get("routed_to", ""), c.get("outcome", "")))


def list_calls(cid: int, limit: int = 100) -> list[dict]:
    return _rows("SELECT * FROM c_calls WHERE client_id=? ORDER BY date DESC LIMIT ?", (cid, limit))


COMPLAINT_SERVICES = [("Nettoyage", r"propre|sale|toilette|ménage|nettoy|poubelle|odeur"), ("Informatique", r"pc|ordinateur|réseau|wifi|wi-fi|internet|logiciel|imprim|labo"),
                      ("Maintenance", r"climatis|chauffage|lumi|électri|porte|fenêtre|fuite|robinet|table|chaise|panne|tableau"),
                      ("Tirage", r"tirage|photocop|copie"), ("Accueil et sécurité", r"sécurit|gardien|accueil|clé|vol|parking"),
                      ("Parc roulant", r"bus|véhicule|voiture|transport"), ("Scolarité", r"attestation|inscription|relevé|diplôme"),
                      ("Pédagogie", r"emploi du temps|cours|enseignant|séance|examen|note")]


def classify(text: str) -> str:
    s = (text or "").lower()
    for svc, pat in COMPLAINT_SERVICES:
        if re.search(pat, s):
            return svc
    return "Services généraux"


def add_complaint(cid: int, c: dict) -> dict:
    date = c.get("date") or _now()
    svc = c.get("service") or classify(c.get("subject", ""))
    ticket = c.get("ticket") or _ticket("R")
    cid2 = _exec("INSERT INTO c_complaints(client_id,date,source,channel,service,subject,status,due,ticket) VALUES (?,?,?,?,?,?,?,?,?)",
                 (cid, date, c.get("source", "Apprenant"), c.get("channel", "Guichet"), svc, (c.get("subject") or "")[:1000],
                  c.get("status") or "Ouverte", (_d(date) + dt.timedelta(days=7)).strftime("%Y-%m-%d"), ticket))
    return _rows("SELECT * FROM c_complaints WHERE id=?", (cid2,))[0]


def list_complaints(cid: int, limit: int = 200) -> list[dict]:
    out = _rows("SELECT * FROM c_complaints WHERE client_id=? ORDER BY date DESC LIMIT ?", (cid, limit))
    today = dt.date.today().isoformat()
    for c in out:
        c["late"] = c["status"] != "Clôturée" and (c["due"] or "9") < today
    return out


def update_complaint(kid: int, ch: dict) -> None:
    st = ch.get("status")
    if st and st not in ("Ouverte", "En traitement", "Clôturée"):
        raise ValueError("Statut inconnu")
    sets, args = [], []
    for k in ("status", "response", "service"):
        if ch.get(k) is not None:
            sets.append(f"{k}=?"); args.append(ch[k])
    if st == "Clôturée":
        sets += ["closed_at=?", "satisfied=?"]; args += [_now()[:10], 1 if ch.get("satisfied", True) else 0]
    if sets:
        _exec(f"UPDATE c_complaints SET {', '.join(sets)} WHERE id=?", (*args, kid))


def add_archive(cid: int, a: dict) -> int:
    return _exec("INSERT INTO c_archive(client_id,date,items,nc,note) VALUES (?,?,?,?,?)",
                 (cid, a.get("date") or _now()[:10], int(a.get("items") or 0), int(a.get("nc") or 0), a.get("note", "")))


# ------------------------------------------------------------------ indicateurs
def period_bounds(period: str | None) -> tuple[str, str, str]:
    """'S1-2026', 'S2-2026', 'T3-2026', '2026', ou None = 6 derniers mois."""
    today = dt.date.today()
    if not period:
        s = today - dt.timedelta(days=182)
        return s.isoformat(), today.isoformat(), "6 derniers mois"
    m = re.fullmatch(r"(S|T)([1-4])-(\d{4})", period)
    if m:
        k, n, y = m.group(1), int(m.group(2)), int(m.group(3))
        months = 6 if k == "S" else 3
        sm = (n - 1) * months + 1
        em = sm + months
        s = dt.date(y, sm, 1)
        e = (dt.date(y + (em > 12), (em - 1) % 12 + 1, 1) - dt.timedelta(days=1))
        return s.isoformat(), e.isoformat(), f"{'Semestre' if k == 'S' else 'Trimestre'} {n} {y}"
    if re.fullmatch(r"\d{4}", period):
        return f"{period}-01-01", f"{period}-12-31", f"Année {period}"
    raise ValueError("Période invalide")


def _pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def targets(cid: int) -> dict:
    raw = store.get_setting(f"campus.targets.{cid}")
    t = {i[1]: i[5] for i in INDICATORS}
    if raw:
        t.update(json.loads(raw))
    return t


def compute(cid: int, period: str | None = None) -> dict:
    s, e, label = period_bounds(period)
    e2 = e + " 23:59"
    tk = lambda plan: _rows("SELECT COUNT(*) n, SUM(done) d FROM c_tasks WHERE client_id=? AND plan=? AND date BETWEEN ? AND ? AND date<=?",
                            (cid, plan, s, e, dt.date.today().isoformat()))[0]
    out = {}
    n = tk("nettoyage"); out["GSG-1"] = (_pct(n["d"] or 0, n["n"]), f"{n['d'] or 0}/{n['n']} interventions")
    g = tk("gardiennage"); out["GSG-2"] = (_pct(g["d"] or 0, g["n"]), f"{g['d'] or 0}/{g['n']} rondes et postes")
    fam = [k for k, v in TYPES.items() if v[4] == "logistique"]
    q = f"SELECT * FROM c_requests WHERE client_id=? AND created_at BETWEEN ? AND ? AND type IN ({','.join('?' * len(fam))})"
    lg = _rows(q, (cid, s, e2, *fam))
    closed = [r for r in lg if r["status"] in ("Réalisée", "Réceptionnée", "Refusée")]
    ok = [r for r in closed if r["status"] != "Refusée" and r["satisfied"] != 0]
    out["GSG-3"] = (_pct(len(ok), len(closed)), f"{len(ok)}/{len(closed)} demandes clôturées satisfaites")
    tr = _rows("SELECT * FROM c_requests WHERE client_id=? AND type='tirage' AND created_at BETWEEN ? AND ? AND status IN ('Réalisée','Réceptionnée','Refusée')", (cid, s, e2))
    intime = [r for r in tr if r["status"] != "Refusée" and r["done_at"] and r["done_at"] <= (r["needed_by"] or "") and r["satisfied"] != 0]
    out["GSG-4"] = (_pct(len(intime), len(tr)), f"{len(intime)}/{len(tr)} tirages livrés à temps")
    ar = _rows("SELECT SUM(items) i, SUM(nc) nc FROM c_archive WHERE client_id=? AND date BETWEEN ? AND ?", (cid, s, e))[0]
    out["GSG-5"] = (round(100 * (1 - (ar["nc"] or 0) / ar["i"]), 1) if ar["i"] else None, f"{ar['nc'] or 0} NC sur {ar['i'] or 0} éléments inventoriés")
    cp = _rows("SELECT * FROM c_complaints WHERE client_id=? AND date BETWEEN ? AND ?", (cid, s, e2))
    eff = [c for c in cp if c["status"] == "Clôturée" and c["closed_at"] and c["closed_at"] <= (c["due"] or "") and c["satisfied"] != 0]
    out["GSG-6"] = (_pct(len(eff), len(cp)), f"{len(eff)}/{len(cp)} réclamations traitées dans le délai")
    m = tk("maintenance_info"); out["GSG-7a"] = (_pct(m["d"] or 0, m["n"]), f"{m['d'] or 0}/{m['n']} maintenances préventives")
    cu = _rows("""SELECT i.effective FROM c_interventions i JOIN c_assets a ON a.id=i.asset_id WHERE i.client_id=? AND i.kind='C'
                  AND a.category='informatique' AND i.date BETWEEN ? AND ?""", (cid, s, e))
    out["GSG-7b"] = (_pct(sum(x["effective"] for x in cu), len(cu)), f"{sum(x['effective'] for x in cu)}/{len(cu)} interventions curatives efficaces")
    manual = {r["code"]: r for r in _rows("SELECT * FROM c_measures WHERE client_id=? AND period=?", (cid, period or "courante"))}
    tg = targets(cid)
    res = []
    for proc, code, name, formula, freq, _, source in INDICATORS:
        if proc == "GSG":
            v, detail = out[code]; mode = "Automatique"
        elif code == "PAC-1":
            today = dt.date.today().isoformat()
            acts = [a for a in store.list_actions(cid, None) if (a["created_at"] or "")[:10] >= s and (a["status"] == "Clôturée" or (a["due"] or "9") < today)]
            done = [a for a in acts if a["status"] == "Clôturée"]
            v, detail, mode = _pct(len(done), len(acts)), f"{len(done)}/{len(acts)} actions arrivées à échéance clôturées", "Automatique"
        else:
            from . import smoe
            s2 = s if period else (dt.date.today() - dt.timedelta(days={"Annuelle": 365, "Semestrielle": 182, "Trimestrielle": 91}.get(freq, 182))).isoformat()
            sv = smoe.value(cid, code, s2, e)
            mm = manual.get(code)
            if sv and sv[0] is not None:
                v, detail, mode = sv[0], sv[1], "Automatique"
            else:
                v, detail, mode = (mm["value"] if mm else None), (mm["note"] if mm and mm["note"] else "Saisie du pilote ou registre vide"), "Saisie"
        t = tg.get(code)
        ok = None if v is None or t is None else (v <= t if code in LOWER_IS_BETTER else v >= t)
        res.append({"process": proc, "code": code, "name": name, "formula": formula, "freq": freq, "source": source,
                    "value": v, "target": t, "ok": ok, "detail": detail, "mode": mode, "lower_better": code in LOWER_IS_BETTER})
    return {"period": period or "courante", "label": label, "start": s, "end": e, "indicators": res}


def set_measure(cid: int, code: str, period: str, value: float, note: str = "") -> None:
    proc = next((i[0] for i in INDICATORS if i[1] == code), None)
    if not proc or proc == "GSG" or code == "PAC-1":
        raise ValueError("Indicateur calculé automatiquement ou inconnu")
    _exec("INSERT OR REPLACE INTO c_measures(client_id,process,code,period,value,note) VALUES (?,?,?,?,?,?)", (cid, proc, code, period, float(value), note))


def summary(cid: int) -> dict:
    today = dt.date.today().isoformat()
    cnt = lambda q, a=(): _rows(q, a)[0]["n"]
    open_req = cnt("SELECT COUNT(*) n FROM c_requests WHERE client_id=? AND status IN ('Nouvelle','Planifiée','En cours')", (cid,))
    late = len([r for r in list_requests(cid, limit=2000) if r["status"] in ("Nouvelle", "Planifiée", "En cours") and r["late"]])
    k = compute(cid)
    return {"open_requests": open_req, "late_requests": late,
            "new_requests": cnt("SELECT COUNT(*) n FROM c_requests WHERE client_id=? AND status='Nouvelle'", (cid,)),
            "to_receive": cnt("SELECT COUNT(*) n FROM c_requests WHERE client_id=? AND status='Réalisée'", (cid,)),
            "open_complaints": cnt("SELECT COUNT(*) n FROM c_complaints WHERE client_id=? AND status!='Clôturée'", (cid,)),
            "late_complaints": cnt("SELECT COUNT(*) n FROM c_complaints WHERE client_id=? AND status!='Clôturée' AND due<?", (cid, today)),
            "tasks_today": cnt("SELECT COUNT(*) n FROM c_tasks WHERE client_id=? AND date=?", (cid, today)),
            "tasks_overdue": cnt("SELECT COUNT(*) n FROM c_tasks WHERE client_id=? AND date<? AND date>=? AND done=0", (cid, today, (dt.date.today() - dt.timedelta(days=30)).isoformat())),
            "assets": cnt("SELECT COALESCE(SUM(qty),0) n FROM c_assets WHERE client_id=?", (cid,)),
            "mail_open": cnt("SELECT COUNT(*) n FROM c_mail WHERE client_id=? AND status!='Traité'", (cid,)),
            "kpi_ok": sum(1 for i in k["indicators"] if i["ok"]), "kpi_ko": sum(1 for i in k["indicators"] if i["ok"] is False),
            "kpi_na": sum(1 for i in k["indicators"] if i["ok"] is None), "indicators": [i for i in k["indicators"] if i["process"] == "GSG"],
            "by_type": _rows("SELECT type, COUNT(*) n FROM c_requests WHERE client_id=? AND created_at>=? GROUP BY type ORDER BY n DESC",
                             (cid, (dt.date.today() - dt.timedelta(days=182)).isoformat())),
            "by_month": _rows("SELECT substr(created_at,1,7) m, COUNT(*) n, SUM(status IN ('Réalisée','Réceptionnée')) d FROM c_requests WHERE client_id=? GROUP BY m ORDER BY m DESC LIMIT 6", (cid,))[::-1]}


def processes(cid: int) -> list[dict]:
    k = {i["code"]: i for i in compute(cid)["indicators"]}
    out = []
    for code, kind, name, pilot, clauses, mode in PROCESSES:
        inds = [k[i[1]] for i in INDICATORS if i[0] == code]
        out.append({"code": code, "kind": kind, "name": name, "pilot": pilot, "clauses": clauses, "mode": mode,
                    "indicators": inds, "ok": sum(1 for i in inds if i["ok"]), "ko": sum(1 for i in inds if i["ok"] is False)})
    return out


# ------------------------------------------------------------------ agents Campus
_today = agents._today
ASSIGNEES = {"Tirage": "Agent de tirage", "Maintenance": "Responsable maintenance", "Informatique": "Responsable informatique",
             "Parc roulant": "Responsable parc roulant", "Services généraux": "Responsable services généraux", "Magasin": "Magasinier",
             "Accueil et sécurité": "Agent d'accueil", "Nettoyage": "Chef d'équipe nettoyage", "Archives": "Archiviste"}


def _doc(r, title, sections, kind="campus", footer=None):
    return r.doc({"kind": kind, "title": f"{title} — {r.client['name']}", "client": r.client["name"], "date": _today(), "ai": False,
                  "standard": STD, "footer": footer or "Document préparé par un agent Kapsi Campus, à valider par le responsable du processus.",
                  "sections": sections})


def agent_repartiteur(r) -> None:
    """Répartiteur : trie les nouvelles demandes, les affecte, fixe les délais, relance les retards."""
    cid = r.cid
    new = list_requests(cid, "Nouvelle", limit=1000)
    for q in new:
        prio = "Urgente" if re.search(r"urgent|panne|fuite|sécurité|examen", (q["title"] + json.dumps(q["details"], ensure_ascii=False)).lower()) else q["priority"]
        update_request(q["id"], {"status": "Planifiée", "assignee": ASSIGNEES.get(q["service"], "Responsable services généraux"), "priority": prio})
    r.log(f"{len(new)} nouvelle(s) demande(s) affectée(s) et planifiée(s).", "ok")
    openq = [q for q in list_requests(cid, limit=3000) if q["status"] in ("Planifiée", "En cours")]
    late = [q for q in openq if q["late"]]
    soon = [q for q in openq if not q["late"] and _d(q["needed_by"]) and _d(q["needed_by"]) < dt.datetime.now() + dt.timedelta(days=1)]
    wait = [q for q in list_requests(cid, "Réalisée", limit=1000) if _d(q["done_at"]) and _d(q["done_at"]) < dt.datetime.now() - dt.timedelta(days=3)]
    for q in late[:8]:
        r.log(f"En retard : {q['ticket']} · {q['type_label']} · {q['dept'] or q['requester']} · attendu le {q['needed_by'][:10]}", "warn")
    r.log(f"{len(late)} demande(s) en retard, {len(soon)} à livrer dans les 24 h, {len(wait)} réalisée(s) sans accusé de réception.", "warn" if late else "ok")
    rows = lambda L: [[q["ticket"], q["type_label"], q["dept"] or q["requester"], q["assignee"] or "", (q["needed_by"] or "")[:16], q["status"]] for q in L[:40]]
    cols = ["Ticket", "Demande", "Demandeur", "Affectée à", "Échéance", "Statut"]
    _doc(r, "Point des demandes du jour", [
        {"heading": "Synthèse", "bullets": [f"{len(new)} nouvelle(s) demande(s) affectée(s)", f"{len(late)} demande(s) en retard", f"{len(soon)} demande(s) à livrer dans les 24 heures",
                                            f"{len(wait)} demande(s) réalisée(s) en attente de l'accusé de réception du demandeur"]},
        {"heading": "Demandes en retard (priorité du jour)", "table": {"columns": cols, "rows": rows(late)}} if late else {"heading": "Demandes en retard", "paragraphs": ["Aucune."]},
        {"heading": "À livrer dans les 24 heures", "table": {"columns": cols, "rows": rows(soon)}} if soon else {"heading": "À livrer dans les 24 heures", "paragraphs": ["Aucune."]},
        {"heading": "Accusés de réception à relancer", "paragraphs": ["L'indicateur GSG-3 ne compte une demande comme satisfaite qu'après la signature du demandeur (procédure tirage, GSG-PR-06)."],
         "table": {"columns": cols, "rows": rows(wait)}} if wait else {"heading": "Accusés de réception à relancer", "paragraphs": ["Aucun."]}], kind="campus_daily")
    r.out["late"] = len(late)


def agent_maintenance(r) -> None:
    """Planificateur de maintenance : plannings préventifs PL-04/05/06 et analyse des fiches de vie."""
    cid = r.cid
    assets = list_assets(cid)
    start = dt.date.today()
    made = 0
    for a in assets:
        if a["state"] == "Réformé":
            continue
        plan, every = CATEGORIES[a["category"]][2], CATEGORIES[a["category"]][3]
        existing = {t["date"] for t in list_tasks(cid, plan, start.isoformat()) if t["asset_id"] == a["id"]}
        d = start + dt.timedelta(days=(a["id"] * 7) % min(every, 60))
        while d <= start + dt.timedelta(days=182):
            if d.weekday() == 6:
                d += dt.timedelta(days=1)
            if d.isoformat() not in existing:
                add_task(cid, {"plan": plan, "label": f"Maintenance préventive · {a['label'] or a['code']}", "location": a["location"],
                               "who": "Prestataire" if a["category"] in ("vehicule",) else "Équipe interne", "date": d.isoformat(), "asset_id": a["id"]})
                made += 1
            d += dt.timedelta(days=every)
    r.log(f"{made} intervention(s) préventive(s) planifiée(s) sur 6 mois pour {len(assets)} équipement(s).", "ok")
    for cat, (label, form, plan, every) in CATEGORIES.items():
        ts = [t for t in list_tasks(cid, plan, start.isoformat(), (start + dt.timedelta(days=182)).isoformat())]
        if not ts:
            continue
        _doc(r, f"{PLANS[plan][0]} ({PLANS[plan][1]})", [
            {"heading": "Périmètre", "paragraphs": [f"{label} : fréquence retenue tous les {every} jours. Planning généré à partir des fiches de vie ({form})."]},
            {"heading": "Planning sur 6 mois", "table": {"columns": ["Date", "Équipement", "Lieu", "Intervenant", "Réalisé"],
                                                       "rows": [[t["date"], t["label"].replace("Maintenance préventive · ", ""), t["location"], t["who"], "Oui" if t["done"] else ""] for t in ts[:80]]}}],
             kind="campus_plan")
    worst = sorted([a for a in assets if a["curatives_12m"] >= 3], key=lambda a: -a["curatives_12m"])
    for a in worst[:5]:
        r.log(f"Équipement à surveiller : {a['label']} ({a['location']}) · {a['curatives_12m']} pannes en 12 mois · {a['downtime_12m']:.0f} h d'arrêt.", "warn")
    _doc(r, "Analyse des fiches de vie des équipements", [
        {"heading": "Équipements les plus défaillants (12 derniers mois)", "paragraphs": ["Seuil d'alerte : 3 interventions curatives ou plus en 12 mois. Pour ces équipements, comparer le coût des réparations avec un remplacement et l'inscrire au budget (GAF-11)."],
         "table": {"columns": ["Équipement", "Lieu", "Catégorie", "Pannes", "Arrêt (h)", "Coût (TND)", "Proposition"],
                   "rows": [[a["label"], a["location"], CATEGORIES[a["category"]][0], a["curatives_12m"], f"{a['downtime_12m']:.0f}", f"{a['cost_12m']:.0f}",
                             "Remplacement à étudier" if a["curatives_12m"] >= 4 else "Renforcer le préventif"] for a in worst[:25]]}} if worst else
        {"heading": "Équipements les plus défaillants", "paragraphs": ["Aucun équipement n'atteint le seuil d'alerte."]}], kind="campus_assets")


def agent_tableau(r) -> None:
    """Tableau de bord GSG-TAB-02 : calcule les indicateurs, compare aux cibles, ouvre les actions."""
    k = compute(r.cid)
    ko = [i for i in k["indicators"] if i["ok"] is False]
    na = [i for i in k["indicators"] if i["value"] is None]
    existing = {(a["clause"], a["status"]) for a in store.list_actions(r.cid, STD)}
    opened = 0
    hints = {"GSG-1": "Absences non remplacées ou planning trop chargé : revoir la répartition des locaux par agent (GSG-PL-02).",
             "GSG-2": "Postes non tenus : vérifier les remplacements et la fiche de pointage.",
             "GSG-3": "Demandes satisfaites sans accusé de réception ou stock insuffisant : relancer la signature et revoir les seuils de stock.",
             "GSG-4": "Demandes déposées hors délai de 48 h ou machine en panne : rappeler la règle et suivre la fiche de vie du matériel d'impression.",
             "GSG-5": "Écarts d'inventaire : vérifier le classement et le registre des sorties d'archives.",
             "GSG-6": "Réclamations non affectées : désigner un responsable par service et un délai de réponse de 7 jours.",
             "GSG-7a": "Maintenances préventives non réalisées : bloquer un créneau fixe par laboratoire.",
             "GSG-7b": "Pannes récurrentes : analyser les fiches de vie et remplacer le matériel le plus défaillant."}
    for i in ko:
        if (i["code"], "Ouverte") in existing or (i["code"], "En cours") in existing:
            continue
        store.add_action(r.cid, {"standard": STD, "source": f"Indicateur {i['code']}", "clause": i["code"],
                                 "finding": f"{i['name']} : {i['value']} % pour une cible de {i['target']} % ({k['label']}).",
                                 "cause": hints.get(i["code"], "À analyser avec le pilote du processus."), "action": "Plan d'amélioration à définir et suivre au tableau de bord.",
                                 "owner": next((p[3] for p in PROCESSES if p[0] == i["process"]), "Pilote"), "due": _today(30), "status": "Ouverte"})
        opened += 1
    for i in ko:
        r.log(f"Sous la cible : {i['code']} {i['name']} = {i['value']} (cible {i['target']}).", "warn")
    r.log(f"{len(k['indicators']) - len(ko) - len(na)} indicateur(s) atteints, {len(ko)} sous la cible, {len(na)} sans donnée. {opened} action(s) ouverte(s).", "ok")
    fmt = lambda v, lb: "—" if v is None else (f"{v:g} j" if lb else f"{v:g} %")
    _doc(r, "Tableau de bord des processus (GSG-TAB-02)", [
        {"heading": "Période", "paragraphs": [f"{k['label']} (du {k['start']} au {k['end']}). Les indicateurs GSG sont calculés automatiquement à partir des registres de Kapsi Campus, avec les formules de la fiche processus GSG-PP."]},
        {"heading": "Indicateurs", "table": {"columns": ["Processus", "Code", "Indicateur", "Valeur", "Cible", "Statut", "Base de calcul"],
                                             "rows": [[i["process"], i["code"], i["name"], fmt(i["value"], i["lower_better"]), fmt(i["target"], i["lower_better"]),
                                                       "Atteint" if i["ok"] else "Sous la cible" if i["ok"] is False else "À mesurer", i["detail"]] for i in k["indicators"]]}},
        {"heading": "Actions ouvertes", "bullets": [f"{i['code']} : {hints.get(i['code'], 'à analyser')}" for i in ko] or ["Aucune : tous les indicateurs mesurés atteignent leur cible."]},
        {"heading": "Indicateurs à mesurer", "bullets": [f"{i['code']} · {i['name']} (source : {i['source']})" for i in na] or ["Aucun."]}], kind="campus_kpi")
    r.out["kpi"] = {"ok": len(k["indicators"]) - len(ko) - len(na), "ko": len(ko), "na": len(na)}


def agent_reclamations(r) -> None:
    """Réclamations : classe, fixe les délais, relance, détecte les sujets récurrents."""
    cs = list_complaints(r.cid, 2000)
    fixed = 0
    for c in cs:
        if c["status"] == "Ouverte" and (not c["service"] or c["service"] == "Services généraux"):
            svc = classify(c["subject"])
            if svc != c["service"]:
                update_complaint(c["id"], {"service": svc}); fixed += 1
    cs = list_complaints(r.cid, 2000)
    late = [c for c in cs if c["late"]]
    since = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    themes: dict[str, int] = {}
    for c in cs:
        if c["date"] >= since:
            themes[c["service"]] = themes.get(c["service"], 0) + 1
    recurrent = {k: v for k, v in themes.items() if v >= 3}
    for k, v in recurrent.items():
        if not any(a["source"] == "Réclamations récurrentes" and a["clause"] == k and a["status"] != "Clôturée" for a in store.list_actions(r.cid, STD)):
            store.add_action(r.cid, {"standard": STD, "source": "Réclamations récurrentes", "clause": k, "finding": f"{v} réclamations sur « {k} » en 90 jours.",
                                     "cause": "Cause commune à rechercher (5 pourquoi) avec le responsable du service.", "action": "Action corrective et information des apprenants.",
                                     "owner": ASSIGNEES.get(k, "Pilote GSG"), "due": _today(30), "status": "Ouverte"})
    r.log(f"{fixed} réclamation(s) reclassée(s). {len(late)} en retard. Sujets récurrents : {', '.join(f'{k} ({v})' for k, v in recurrent.items()) or 'aucun'}.", "warn" if late else "ok")
    _doc(r, "Registre de suivi des réclamations et suggestions", [
        {"heading": "Synthèse", "bullets": [f"{len(cs)} réclamation(s) enregistrée(s), {sum(c['status'] != 'Clôturée' for c in cs)} ouverte(s), {len(late)} en retard (délai de réponse : 7 jours)."] +
                                           [f"Sujet récurrent : {k}, {v} réclamations en 90 jours" for k, v in recurrent.items()]},
        {"heading": "Registre", "table": {"columns": ["N°", "Date", "Émetteur", "Service", "Objet", "Échéance", "Statut"],
                                           "rows": [[c["ticket"] or c["id"], c["date"][:10], c["source"], c["service"], c["subject"][:90], c["due"], c["status"]] for c in cs[:60]]}}], kind="campus_complaints")


def agent_satisfaction(r) -> None:
    """Satisfaction : questionnaires apprenants et personnel + analyse des accusés de réception."""
    rq = [q for q in list_requests(r.cid, limit=5000) if q["satisfied"] is not None]
    by: dict[str, list[int]] = {}
    for q in rq:
        by.setdefault(q["type_label"], []).append(q["satisfied"])
    rows = [[k, len(v), f"{round(100 * sum(v) / len(v))} %"] for k, v in sorted(by.items(), key=lambda x: -len(x[1]))]
    r.log(f"{len(rq)} accusé(s) de réception analysé(s) sur {len(by)} type(s) de service.", "ok")
    qs = ["Propreté des salles, laboratoires et sanitaires", "Sécurité et accueil", "Disponibilité du matériel informatique et du réseau",
          "Délais de tirage des documents", "Disponibilité des salles, vidéoprojecteurs et fournitures", "Traitement des réclamations", "Transport (parc roulant)"]
    for pop in ("apprenants", "personnel"):
        _doc(r, f"Questionnaire de satisfaction des {pop} sur les services généraux", [
            {"heading": "Consignes", "paragraphs": ["Questionnaire anonyme. Échelle : 1 = pas du tout satisfait, 4 = très satisfait. Durée : 3 minutes."]},
            {"heading": "Questions", "table": {"columns": ["N°", "Question", "1", "2", "3", "4"], "rows": [[n + 1, q, "", "", "", ""] for n, q in enumerate(qs)]}},
            {"heading": "Suggestions", "paragraphs": ["Votre principale suggestion d'amélioration : ………………………………………………"]}], kind="campus_survey")
    _doc(r, "Analyse de la satisfaction issue des accusés de réception", [
        {"heading": "Méthode", "paragraphs": ["Chaque demande réceptionnée par le demandeur porte un avis (satisfait ou non). Cette mesure continue complète l'enquête annuelle."]},
        {"heading": "Résultats par service", "table": {"columns": ["Service", "Avis", "Satisfaction"], "rows": rows}} if rows else {"heading": "Résultats", "paragraphs": ["Pas encore d'avis."]}], kind="campus_survey")


def agent_rapport(r) -> None:
    """Rapport annuel d'activités des services généraux, pour la revue de direction."""
    cid = r.cid
    y = str(dt.date.today().year)
    k = compute(cid)
    vol = _rows("SELECT type, COUNT(*) n, SUM(status IN ('Réalisée','Réceptionnée')) d FROM c_requests WHERE client_id=? AND substr(created_at,1,4)=? GROUP BY type ORDER BY n DESC", (cid, y))
    mail = _rows("SELECT direction, COUNT(*) n FROM c_mail WHERE client_id=? AND substr(date,1,4)=? GROUP BY direction", (cid, y))
    cp = _rows("SELECT COUNT(*) n, SUM(status='Clôturée') c FROM c_complaints WHERE client_id=? AND substr(date,1,4)=?", (cid, y))[0]
    iv = _rows("SELECT kind, COUNT(*) n, SUM(cost) c FROM c_interventions WHERE client_id=? AND substr(date,1,4)=? GROUP BY kind", (cid, y))
    acts = store.list_actions(cid, STD)
    _doc(r, f"Rapport annuel d'activités des services généraux {y}", [
        {"heading": "Objet", "paragraphs": ["Élément de sortie du processus GSG, présenté en revue de direction (ISO 21001, 9.3). Données issues des registres de Kapsi Campus."]},
        {"heading": "Volume d'activité", "table": {"columns": ["Service", "Demandes", "Réalisées"], "rows": [[TYPES.get(v["type"], (v["type"],))[0], v["n"], v["d"] or 0] for v in vol]}},
        {"heading": "Courrier et réclamations", "bullets": [f"Courrier {m['direction']} : {m['n']}" for m in mail] + [f"Réclamations : {cp['n']} dont {cp['c'] or 0} clôturées"]},
        {"heading": "Maintenance", "bullets": [f"{'Préventives' if i['kind'] == 'P' else 'Curatives'} : {i['n']} intervention(s), coût {i['c'] or 0:.0f} TND" for i in iv] or ["Aucune intervention enregistrée."]},
        {"heading": "Indicateurs du processus", "table": {"columns": ["Code", "Indicateur", "Valeur", "Cible"],
                                                         "rows": [[i["code"], i["name"], "—" if i["value"] is None else i["value"], i["target"]] for i in k["indicators"] if i["process"] == "GSG"]}},
        {"heading": "Actions d'amélioration", "bullets": [f"{a['clause']} · {a['finding']} ({a['status']})" for a in acts[:15]] or ["Aucune."]},
        {"heading": "Propositions pour l'année prochaine", "bullets": ["Fixer les cibles des indicateurs avec la direction.", "Inscrire au budget le remplacement des équipements signalés par l'agent Maintenance.",
                                                                       "Généraliser le guichet numérique aux apprenants (QR code dans chaque salle)."]}], kind="campus_report")
    r.log("Rapport annuel prêt pour la revue de direction.", "ok")


def agent_pilote_campus(r) -> None:
    """Pilote Campus : enchaîne tous les agents Campus."""
    for key in ("campus_repartiteur", "campus_maintenance", "campus_reclamations", "campus_satisfaction", "campus_tableau", "campus_rapport"):
        r.log(f"— {agents.AGENTS[key][0]} —", "step")
        agents.AGENTS[key][2](r)


CAMPUS_AGENTS = {
    "campus_pilote": ("Pilote Campus", "Enchaîne tous les agents Campus : demandes, maintenance, réclamations, satisfaction, indicateurs, rapport annuel.", agent_pilote_campus),
    "campus_repartiteur": ("Répartiteur des demandes", "Affecte chaque nouvelle demande au bon service, fixe l'échéance (48 h pour le tirage), relance les retards et les accusés de réception.", agent_repartiteur),
    "campus_maintenance": ("Planificateur de maintenance", "Génère les plannings préventifs (GSG-PL-04, 05, 06) et repère dans les fiches de vie les équipements à remplacer.", agent_maintenance),
    "campus_reclamations": ("Gestionnaire des réclamations", "Classe les réclamations par service, suit le délai de 7 jours et ouvre une action sur les sujets récurrents.", agent_reclamations),
    "campus_satisfaction": ("Analyste satisfaction", "Prépare les questionnaires apprenants et personnel et analyse les avis laissés à chaque réception.", agent_satisfaction),
    "campus_tableau": ("Tableau de bord", "Calcule les indicateurs de la fiche GSG-PP et des autres processus, compare aux cibles et ouvre les actions.", agent_tableau),
    "campus_rapport": ("Rapport annuel", "Rédige le rapport annuel d'activités des services généraux pour la revue de direction.", agent_rapport),
}
agents.AGENTS.update(CAMPUS_AGENTS)


# ------------------------------------------------------------------ démonstration
def seed_demo(cid: int, months: int = 7, seed: int = 21) -> None:
    """Remplit un établissement de démonstration : parc réel de l'ISI (fiche GSG-FR-06) et 7 mois d'activité simulée."""
    rnd = random.Random(seed)
    labs = [("A 104", "HP 290 G1 MT", 10), ("A 117", "HP 290 G1 MT", 10), ("A 120", "HP 290 G1 MT", 10), ("A 122", "Lenovo V50t 13IMB", 10),
            ("A 130", "Acer Veriton M4630G", 10), ("A 201", "HP 290 G1 MT", 10), ("A 202", "HP 290 G1 MT", 10), ("A 401", "Acer Veriton M4630G", 10),
            ("A 402", "Poste mixte", 21), ("B 104", "Lenovo V50t 13IMB", 11), ("B 204", "Lenovo V50t 13IMB", 10), ("B 305", "HP 290 G1 MT", 10),
            ("C 101", "Lenovo V50t 13IMB", 10), ("C 102", "HP 290 G1 MT", 14)]
    ids = {"informatique": [], "impression": [], "infrastructure": [], "vehicule": []}
    for loc, model, n in labs:
        ids["informatique"].append(add_asset(cid, {"category": "informatique", "code": f"INF-{loc.replace(' ', '')}", "location": f"Laboratoire {loc}", "label": f"Postes {model}", "qty": n}))
    ids["informatique"].append(add_asset(cid, {"category": "informatique", "code": "INF-ADM", "location": "Administration", "label": "Postes administratifs", "qty": 18}))
    ids["informatique"].append(add_asset(cid, {"category": "informatique", "code": "RES-01", "location": "Salle serveurs", "label": "Réseau, Wi-Fi et serveurs", "qty": 1}))
    for k, (loc, label) in enumerate([("Atelier de tirage", "Copieur grande capacité n°1"), ("Atelier de tirage", "Copieur grande capacité n°2"),
                                      ("Secrétariat général", "Imprimante multifonction"), ("Scolarité", "Imprimante multifonction"), ("Direction des études", "Imprimante laser")]):
        ids["impression"].append(add_asset(cid, {"category": "impression", "code": f"IMP-{k + 1:02d}", "location": loc, "label": label}))
    for k, (loc, label) in enumerate([("Bloc A", "Climatisation et éclairage"), ("Bloc B", "Climatisation et éclairage"), ("Bloc C", "Climatisation et éclairage"),
                                      ("Amphithéâtres", "Sonorisation et vidéoprojecteurs"), ("Sanitaires", "Plomberie"), ("Bâtiment", "Groupe électrogène et sécurité incendie")]):
        ids["infrastructure"].append(add_asset(cid, {"category": "infrastructure", "code": f"INFRA-{k + 1:02d}", "location": loc, "label": label}))
    ids["vehicule"].append(add_asset(cid, {"category": "vehicule", "code": "VEH-01", "location": "Parc", "label": "Dacia Logan MCV (essence, 5 CV)", "data": {"km": 88400}}))
    ids["vehicule"].append(add_asset(cid, {"category": "vehicule", "code": "VEH-02", "location": "Parc", "label": "Peugeot Partner (essence, 6 CV)", "state": "En panne"}))

    today = dt.date.today()
    start = today - dt.timedelta(days=30 * months)
    depts = ["Département Informatique", "Département Génie logiciel", "Département Réseaux", "Département Mathématiques", "Département Langues",
             "Scolarité", "Direction des études", "Bibliothèque", "Club robotique", "Secrétariat général"]
    weights = [("tirage", 34), ("informatique", 14), ("intervention", 12), ("video", 9), ("salle", 7), ("fourniture", 8), ("stylos", 6), ("cle", 4), ("vehicule", 3), ("nettoyage", 2), ("archive", 1)]
    pool = [t for t, w in weights for _ in range(w)]
    titles = {"tirage": ["Sujets d'examen", "Supports de TD", "Énoncés de TP", "Polycopié de cours", "Fiches d'évaluation"],
              "informatique": ["PC en panne", "Pas de connexion réseau", "Installation d'un logiciel", "Vidéoprojecteur non détecté", "Wi-Fi lent"],
              "intervention": ["Climatiseur en panne", "Néon défectueux", "Prise électrique", "Porte qui ferme mal", "Fuite au robinet", "Table cassée"],
              "video": ["Vidéoprojecteur pour soutenance", "Vidéoprojecteur pour séminaire"], "salle": ["Réservation amphi pour conférence", "Salle pour réunion de département"],
              "fourniture": ["Ramettes de papier", "Toners", "Classeurs et chemises"], "stylos": ["Stylos pour tableau blanc"], "cle": ["Clé du laboratoire", "Clé de la salle de réunion"],
              "vehicule": ["Déplacement à l'université", "Mission à Tunis"], "nettoyage": ["Nettoyage après événement"], "archive": ["Consultation de dossiers d'étudiants"]}
    d = start
    while d <= today:
        if d.weekday() < 6:
            exam = d.month in (1, 5, 6)
            for _ in range(rnd.randint(2, 5) + (3 if exam else 0)):
                t = rnd.choice(pool)
                created = dt.datetime.combine(d, dt.time(rnd.randint(8, 15), rnd.choice([0, 15, 30, 45])))
                q = add_request(cid, {"type": t, "requester": rnd.choice(["Enseignant", "Enseignante", "Agent administratif", "Chef de département"]),
                                      "dept": rnd.choice(depts), "title": rnd.choice(titles[t]), "qty": rnd.choice([1, 1, 2, 30, 60, 120]) if t == "tirage" else 1,
                                      "details": {"pages": rnd.randint(2, 12), "copies": rnd.choice([30, 45, 60, 120])} if t == "tirage" else {}},
                                now=created.strftime("%Y-%m-%d %H:%M"))
                age = (today - d).days
                if age < 1:
                    continue
                slow = rnd.random() < (0.16 if exam else 0.08) or (t == "informatique" and rnd.random() < 0.1)
                need = _d(q["needed_by"])
                done = need - dt.timedelta(hours=rnd.randint(1, 30)) if not slow else need + dt.timedelta(hours=rnd.randint(4, 72))
                if done.date() > today or (age < 4 and rnd.random() < 0.5):
                    update_request(q["id"], {"status": rnd.choice(["Planifiée", "En cours"]), "assignee": ASSIGNEES.get(q["service"])})
                    continue
                if rnd.random() < 0.02:
                    update_request(q["id"], {"status": "Refusée", "remark": "Hors délai de dépôt", "assignee": ASSIGNEES.get(q["service"])}, now=done.strftime("%Y-%m-%d %H:%M"))
                    continue
                update_request(q["id"], {"status": "Réalisée", "assignee": ASSIGNEES.get(q["service"])}, now=done.strftime("%Y-%m-%d %H:%M"))
                if rnd.random() < 0.95 and (done + dt.timedelta(days=1)).date() <= today:
                    update_request(q["id"], {"status": "Réceptionnée", "satisfied": rnd.random() > (0.25 if slow else 0.05)},
                                   now=(done + dt.timedelta(hours=rnd.randint(1, 30))).strftime("%Y-%m-%d %H:%M"))
                if t in ("informatique", "intervention") and rnd.random() < 0.6:
                    cat = "informatique" if t == "informatique" else "infrastructure"
                    aid = rnd.choice(ids[cat][:6] if cat == "informatique" and rnd.random() < 0.5 else ids[cat])
                    add_intervention(cid, {"asset_id": aid, "kind": "C", "nature": rnd.choice("RRCG"), "intervenant": rnd.choice("IIE"), "date": done.date().isoformat(),
                                           "description": q["title"], "cost": rnd.choice([0, 0, 40, 120, 350]), "downtime": rnd.choice([1, 2, 4, 8, 24]),
                                           "effective": rnd.random() > 0.12, "request_id": q["id"]})
            # plannings quotidiens : nettoyage (locaux), gardiennage (jour et nuit)
            for loc in ["Bloc A", "Bloc B", "Bloc C", "Sanitaires", "Amphithéâtres"]:
                add_task(cid, {"plan": "nettoyage", "label": f"Nettoyage {loc}", "location": loc, "who": "Équipe nettoyage", "date": d.isoformat(), "done": rnd.random() > 0.07})
        for poste in ("Gardiennage de jour", "Gardiennage de nuit"):
            add_task(cid, {"plan": "gardiennage", "label": poste, "location": "Établissement", "who": "Agents de sécurité", "date": d.isoformat(), "done": rnd.random() > 0.02})
        if d.weekday() == 0:
            for k in range(rnd.randint(8, 14)):
                add_mail(cid, {"direction": rnd.choice(["entrant", "entrant", "sortant", "interne"]), "date": (d + dt.timedelta(days=rnd.randint(0, 4))).isoformat(),
                               "correspondent": rnd.choice(["Université", "Ministère de l'Enseignement supérieur", "Entreprise partenaire", "Autre établissement", "Département"]),
                               "subject": rnd.choice(["Note de service", "Convention de stage", "Demande d'information", "Calendrier des examens", "Invitation", "Facture fournisseur"]),
                               "service": rnd.choice(["Direction", "Secrétariat général", "Scolarité", "Direction des études"]),
                               "status": "Traité" if (today - d).days > 10 else rnd.choice(["Enregistré", "Diffusé"])})
            for k in range(rnd.randint(1, 3)):
                cd = d + dt.timedelta(days=rnd.randint(0, 4))
                if cd > today:
                    continue
                subj = rnd.choice(["Les toilettes du bloc B ne sont pas propres", "Le Wi-Fi ne fonctionne pas au laboratoire A 104", "Climatisation en panne en salle B 204",
                                   "Retard de tirage des supports de TD", "Pas de vidéoprojecteur disponible", "Attestation d'inscription non délivrée",
                                   "Parking non sécurisé le soir", "PC défectueux au laboratoire C 102", "Poubelles non vidées dans l'amphi"])
                c = add_complaint(cid, {"date": cd.strftime("%Y-%m-%d %H:%M"), "source": rnd.choice(["Apprenant", "Apprenant", "Enseignant", "Personnel"]),
                                        "channel": rnd.choice(["Boîte à réclamations", "Mail", "Guichet numérique"]), "subject": subj})
                if (today - cd).days > 3 and rnd.random() < 0.85:
                    late = rnd.random() < 0.18
                    closed = cd + dt.timedelta(days=rnd.randint(8, 15) if late else rnd.randint(1, 6))
                    if closed <= today:
                        _exec("UPDATE c_complaints SET status='Clôturée', closed_at=?, satisfied=?, response=? WHERE id=?",
                              (closed.isoformat(), 1 if rnd.random() > 0.12 else 0, "Intervention réalisée et demandeur informé.", c["id"]))
        d += dt.timedelta(days=1)
    for k in range(rnd.randint(20, 40)):
        add_call(cid, {"date": (today - dt.timedelta(days=rnd.randint(0, 20))).strftime("%Y-%m-%d %H:%M"), "caller": rnd.choice(["Parent d'étudiant", "Entreprise", "Université", "Candidat"]),
                       "subject": rnd.choice(["Inscription", "Stage", "Emploi du temps", "Attestation", "Rendez-vous direction"]), "routed_to": rnd.choice(["Scolarité", "Direction", "Stages"]), "outcome": "Orienté"})
    # maintenance préventive passée (taux réalisé imparfait)
    for cat, aids in ids.items():
        plan, every = CATEGORIES[cat][2], CATEGORIES[cat][3]
        for aid in aids:
            dd = start + dt.timedelta(days=rnd.randint(0, min(every, 40)))
            while dd < today:
                tid = add_task(cid, {"plan": plan, "label": "Maintenance préventive", "location": "", "who": "Équipe interne", "date": dd.isoformat(), "asset_id": aid})
                if rnd.random() > (0.2 if cat == "informatique" else 0.1):
                    set_task(tid, True)
                dd += dt.timedelta(days=every)
    _exec("UPDATE c_tasks SET label = 'Maintenance préventive · ' || (SELECT label FROM c_assets WHERE id=c_tasks.asset_id), location=(SELECT location FROM c_assets WHERE id=c_tasks.asset_id) WHERE client_id=? AND asset_id IS NOT NULL", (cid,))
    add_archive(cid, {"date": (today - dt.timedelta(days=40)).isoformat(), "items": 1240, "nc": 31, "note": "Inventaire semestriel de l'archive"})
    sem = f"{'S1' if today.month <= 6 else 'S2'}-{today.year}"
    for code, v, note in [("PED-1", 96.5, "Cahiers de textes"), ("PED-2", 71, "Enquête d'évaluation des enseignements"), ("EXD-1", 12, "PV de délibération"),
                          ("GSA-1", 4, "Registre des attestations"), ("GRH-1", 64, "Plan de formation du personnel")]:
        set_measure(cid, code, "courante", v, note)
