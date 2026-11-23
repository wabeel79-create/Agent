"""Savoir-faire du responsable qualité utilisé par les agents Kapsi-Q :
procédures types par norme et modules de formation. Contenus rédigés par SmartCell
(pas le texte des normes) ; chaque document produit reste un projet à valider."""
from __future__ import annotations

import datetime as dt

C = "Toutes"  # procédure commune à toutes les normes de la structure harmonisée

# (code, titre, normes, chapitres, objet, étapes, enregistrements, indicateur)
PROCEDURES = [
    ("PR-SYS-01", "Maîtrise des informations documentées", C, "7.5", "Créer, approuver, diffuser, modifier et conserver les documents et enregistrements.",
     ["Rédiger le document sur le modèle en vigueur (code, indice, cartouche Rédigé / Vérifié / Approuvé).",
      "Faire vérifier par le responsable du système et approuver par la direction.",
      "Mettre à jour la liste des documents en vigueur et diffuser la nouvelle version.",
      "Retirer les versions périmées des postes de travail ; archiver l'ancienne version identifiée « périmée ».",
      "Identifier les documents d'origine externe (normes, réglementation) et surveiller leurs mises à jour.",
      "Définir pour chaque enregistrement sa durée de conservation, son support et sa protection."],
     ["Liste des documents en vigueur", "Tableau de conservation des enregistrements"], "Pourcentage de documents à jour"),
    ("PR-SYS-02", "Audit interne", C, "9.2", "Vérifier à intervalles planifiés que le système est conforme et efficacement mis en œuvre.",
     ["Établir le programme annuel d'audit selon l'importance des processus, les risques et les résultats des audits précédents.",
      "Désigner des auditeurs formés (ISO 19011) et indépendants de l'activité auditée.",
      "Préparer le plan d'audit et la check-list ; informer les audités.",
      "Réaliser l'audit : réunion d'ouverture, entretiens, échantillonnage des preuves, réunion de clôture.",
      "Rédiger le rapport : constats (points forts, opportunités, non-conformités) appuyés sur des preuves.",
      "Ouvrir une fiche d'action corrective pour chaque non-conformité et vérifier son efficacité."],
     ["Programme d'audit", "Plans et rapports d'audit", "Fiches d'actions correctives"], "Taux de réalisation du programme d'audit"),
    ("PR-SYS-03", "Revue de direction", C, "9.3", "Évaluer périodiquement la pertinence, l'adéquation et l'efficacité du système.",
     ["Planifier la revue au moins une fois par an (et avant l'audit de certification).",
      "Collecter les données d'entrée : actions précédentes, enjeux, objectifs, performances, audits, NC, fournisseurs, ressources, risques.",
      "Tenir la réunion présidée par la direction avec les pilotes de processus.",
      "Décider des améliorations, des modifications du système et des ressources.",
      "Diffuser le procès-verbal et suivre les décisions dans le plan d'actions."],
     ["PV de revue de direction", "Plan d'actions"], "Taux de réalisation des décisions de revue"),
    ("PR-SYS-04", "Non-conformités et actions correctives", C, "10.2", "Traiter les non-conformités, en éliminer les causes et vérifier l'efficacité des actions.",
     ["Enregistrer la non-conformité (source, constat, preuve) dans le registre.",
      "Mettre en œuvre la correction immédiate et en maîtriser les conséquences.",
      "Analyser les causes (5 pourquoi, diagramme d'Ishikawa) avec les personnes concernées.",
      "Définir l'action corrective, son responsable et son délai.",
      "Vérifier l'efficacité après mise en œuvre ; clôturer ou relancer.",
      "Mettre à jour les risques et le système si nécessaire."],
     ["Registre des non-conformités", "Fiches d'actions correctives"], "Délai moyen de clôture ; taux d'actions efficaces"),
    ("PR-SYS-05", "Compétences, formation et sensibilisation", C, "7.2, 7.3", "Assurer que le personnel a les compétences requises et connaît le système.",
     ["Définir les compétences requises par fonction (fiches de fonction).",
      "Évaluer les compétences (matrice des compétences) et identifier les besoins.",
      "Établir le plan de formation annuel et le faire approuver.",
      "Réaliser les formations et sensibilisations ; conserver les feuilles d'émargement.",
      "Évaluer l'efficacité (évaluation à chaud, à froid, observation au poste)."],
     ["Matrice des compétences", "Plan de formation", "Attestations et émargements"], "Taux de réalisation du plan de formation"),
    ("PR-SYS-06", "Gestion des risques et opportunités", C, "6.1", "Identifier, évaluer et traiter les risques et opportunités du système.",
     ["Recenser les risques et opportunités par processus à partir du contexte et des parties intéressées.",
      "Les coter (gravité × probabilité) selon la grille approuvée.",
      "Décider du traitement des risques au-dessus du seuil ; planifier les opportunités retenues.",
      "Intégrer les actions dans les processus et suivre leur efficacité.",
      "Revoir le registre au moins une fois par an et à chaque changement important."],
     ["Registre des risques et opportunités"], "Pourcentage de risques critiques traités"),
    ("PR-SYS-07", "Veille et évaluation de la conformité réglementaire", "ISO 14001,ISO 45001,ISO 50001,ISO 22000,ISO 27001,ISO 42001", "6.1.3, 9.1.2",
     "Identifier les exigences légales applicables et évaluer périodiquement leur respect.",
     ["Recenser les textes applicables (JORT, codes, décrets, arrêtés, normes rendues obligatoires).",
      "Traduire chaque texte en exigences concrètes et désigner un responsable.",
      "Mettre à jour le registre chaque trimestre.",
      "Évaluer la conformité au moins une fois par an et enregistrer les preuves.",
      "Traiter les écarts comme des non-conformités."],
     ["Registre réglementaire", "Rapport d'évaluation de conformité"], "Taux de conformité réglementaire"),
    # ISO 9001
    ("PR-QUA-01", "Revue des exigences clients", "ISO 9001", "8.2", "S'assurer avant toute acceptation que les exigences du client peuvent être satisfaites.",
     ["Enregistrer la demande (devis, commande, appel d'offres).", "Vérifier les exigences : spécifications, délais, quantités, exigences légales.",
      "Résoudre les écarts avec le client avant acceptation.", "Confirmer la commande par écrit.", "Gérer les modifications de commande et en informer les personnes concernées."],
     ["Devis et commandes revus", "Fiches de revue de contrat"], "Taux de commandes revues avant acceptation"),
    ("PR-QUA-02", "Achats et évaluation des fournisseurs", "ISO 9001", "8.4", "Maîtriser les produits et services fournis par des prestataires externes.",
     ["Définir les critères de sélection et d'évaluation (qualité, délai, prix, réactivité).", "Sélectionner et agréer les fournisseurs ; tenir la liste des fournisseurs agréés.",
      "Émettre des commandes claires.", "Contrôler à réception.", "Évaluer les fournisseurs chaque année et engager les plans de progrès."],
     ["Liste des fournisseurs agréés", "Évaluations fournisseurs", "PV de réception"], "Note moyenne des fournisseurs"),
    ("PR-QUA-03", "Maîtrise de la production et de la prestation", "ISO 9001", "8.5, 8.6, 8.7", "Réaliser les produits et services dans des conditions maîtrisées.",
     ["Disposer des modes opératoires et critères d'acceptation au poste.", "Utiliser des équipements maintenus et des instruments étalonnés.",
      "Assurer l'identification et la traçabilité.", "Libérer les produits après contrôle.", "Isoler et traiter les produits non conformes."],
     ["Fiches de suivi", "PV de contrôle", "Fiches de non-conformité produit"], "Taux de non-conformité produit"),
    ("PR-QUA-04", "Satisfaction client et réclamations", "ISO 9001", "9.1.2", "Mesurer la satisfaction et traiter les réclamations.",
     ["Enregistrer chaque réclamation et en accuser réception.", "Analyser et répondre au client dans le délai défini.",
      "Ouvrir une action corrective si nécessaire.", "Mener une enquête de satisfaction au moins une fois par an.", "Analyser les résultats en revue de direction."],
     ["Registre des réclamations", "Résultats d'enquête"], "Indice de satisfaction ; délai de réponse"),
    # ISO 14001
    ("PR-ENV-01", "Analyse environnementale", "ISO 14001", "6.1.2", "Identifier les aspects environnementaux et déterminer les aspects significatifs.",
     ["Lister les activités, produits et services, y compris en conditions anormales et d'urgence.", "Identifier aspects et impacts dans une perspective de cycle de vie.",
      "Coter selon les critères approuvés (gravité, fréquence, maîtrise, exigences légales).", "Retenir les aspects significatifs et définir leur maîtrise.", "Revoir l'analyse chaque année et à chaque changement."],
     ["Analyse environnementale"], "Nombre d'aspects significatifs maîtrisés"),
    ("PR-ENV-02", "Gestion des déchets", "ISO 14001", "8.1", "Trier, stocker et éliminer les déchets conformément à la réglementation.",
     ["Identifier les types de déchets et leurs filières.", "Mettre en place le tri à la source et l'étiquetage.", "Stocker les déchets dangereux dans une zone de rétention.",
      "Confier les déchets à des collecteurs autorisés.", "Conserver les bordereaux de suivi."], ["Registre des déchets", "Bordereaux"], "Taux de valorisation des déchets"),
    ("PR-ENV-03", "Situations d'urgence environnementales", "ISO 14001", "8.2", "Préparer et tester la réponse aux situations d'urgence.",
     ["Identifier les scénarios (déversement, incendie, fuite).", "Définir les moyens et les consignes.", "Former les équipes d'intervention.", "Réaliser un exercice par an et en tirer les enseignements."],
     ["Plan d'urgence", "Comptes rendus d'exercices"], "Nombre d'exercices réalisés"),
    # ISO 45001
    ("PR-SST-01", "Identification des dangers et évaluation des risques", "ISO 45001", "6.1.2", "Évaluer les risques professionnels et définir les mesures de prévention.",
     ["Découper l'entreprise en unités de travail.", "Identifier les dangers, y compris activités non routinières et sous-traitants.",
      "Coter les risques (gravité × probabilité).", "Définir les mesures selon la hiérarchie : élimination, substitution, protection collective, organisation, EPI.",
      "Mettre à jour le DUER chaque année et après tout accident ou changement."], ["DUER", "Plan de prévention"], "Pourcentage de risques élevés traités"),
    ("PR-SST-02", "Accidents, incidents et presqu'accidents", "ISO 45001", "10.2", "Déclarer, analyser et prévenir les accidents.",
     ["Porter secours et sécuriser la zone.", "Déclarer l'événement dans les 24 h.", "Analyser les causes (arbre des causes) avec les travailleurs.",
      "Définir les actions et suivre leur efficacité.", "Suivre les taux de fréquence et de gravité."], ["Registre des accidents", "Analyses d'accidents"], "Taux de fréquence"),
    ("PR-SST-03", "Consultation et participation des travailleurs", "ISO 45001", "5.4", "Associer les travailleurs aux décisions de santé et sécurité.",
     ["Désigner les représentants et réunir le comité SST.", "Consulter sur les dangers, les mesures et les changements.", "Faire participer aux analyses d'accidents.", "Communiquer les décisions."],
     ["PV du comité SST"], "Nombre de réunions tenues"),
    # ISO 27001
    ("PR-SI-01", "Gestion des incidents de sécurité de l'information", "ISO 27001", "A.5.24 – A.5.28", "Détecter, traiter et tirer les leçons des incidents.",
     ["Signaler tout événement suspect au référent sécurité.", "Qualifier et prioriser l'incident.", "Contenir, éradiquer, restaurer.", "Conserver les preuves.", "Analyser les causes et améliorer les mesures."],
     ["Registre des incidents"], "Délai moyen de traitement"),
    ("PR-SI-02", "Contrôle d'accès et gestion des droits", "ISO 27001", "A.5.15 – A.5.18, A.8.2", "Accorder les accès au juste besoin et les revoir.",
     ["Créer les comptes sur demande validée par le responsable.", "Appliquer le moindre privilège.", "Imposer des mots de passe robustes et l'authentification forte pour les accès sensibles.",
      "Revoir les droits chaque semestre.", "Supprimer les accès au départ du collaborateur."], ["Demandes d'accès", "Revues des droits"], "Pourcentage de comptes revus"),
    ("PR-SI-03", "Sauvegarde et restauration", "ISO 27001", "A.8.13", "Garantir la disponibilité des données.",
     ["Définir le périmètre, la fréquence et la rétention.", "Appliquer la règle 3-2-1 (dont une copie hors site).", "Chiffrer les sauvegardes externes.", "Tester une restauration chaque trimestre."],
     ["Journal des sauvegardes", "PV de tests de restauration"], "Taux de restaurations réussies"),
    # ISO 22000
    ("PR-SDA-01", "Analyse des dangers et plan HACCP", "ISO 22000", "8.5", "Maîtriser les dangers liés à la sécurité des denrées.",
     ["Constituer l'équipe HACCP.", "Décrire les produits et établir les diagrammes de fabrication vérifiés sur site.", "Analyser les dangers biologiques, chimiques, physiques et allergènes.",
      "Déterminer les CCP et PRPo, leurs limites et leur surveillance.", "Définir les corrections et actions correctives.", "Vérifier et valider le plan chaque année."],
     ["Étude HACCP", "Fiches de surveillance des CCP"], "Nombre de dépassements de limites critiques"),
    ("PR-SDA-02", "Nettoyage et désinfection", "ISO 22000", "8.2", "Assurer l'hygiène des locaux et équipements (PRP).",
     ["Établir le plan de nettoyage (quoi, qui, quand, comment, produits).", "Former le personnel.", "Enregistrer la réalisation.", "Vérifier l'efficacité (contrôles visuels, prélèvements)."],
     ["Plan de nettoyage", "Fiches d'enregistrement"], "Conformité des prélèvements"),
    ("PR-SDA-03", "Traçabilité, retrait et rappel", "ISO 22000", "8.3, 8.9", "Retrouver un lot et retirer rapidement un produit dangereux.",
     ["Identifier les lots de matières et de produits finis.", "Relier lots entrants, production et clients.", "Tester la traçabilité deux fois par an.", "En cas d'alerte : bloquer, informer, retirer ou rappeler, notifier les autorités."],
     ["Registres de lots", "Tests de traçabilité", "Simulations de rappel"], "Temps de traçabilité d'un lot"),
    # ISO 21001
    ("PR-EDU-01", "Admission des apprenants", "ISO 21001", "8.5", "Admettre les apprenants selon des critères équitables et publiés.",
     ["Publier les prérequis et critères.", "Recevoir et vérifier les dossiers.", "Décider selon la grille et informer les candidats.", "Accueillir et informer les admis."],
     ["Dossiers d'admission", "Décisions"], "Délai de réponse aux candidats"),
    ("PR-EDU-02", "Évaluation des apprentissages", "ISO 21001", "8.5", "Évaluer les apprenants de manière juste et transparente.",
     ["Définir les modalités et critères dans la fiche programme.", "Informer les apprenants avant l'évaluation.", "Corriger selon les grilles.", "Délibérer et communiquer les résultats.", "Traiter les recours."],
     ["Grilles", "PV de délibération"], "Taux de réussite ; nombre de recours"),
    # ISO 50001
    ("PR-NRJ-01", "Revue énergétique et usages significatifs", "ISO 50001", "6.3 – 6.5", "Analyser les consommations et identifier les usages énergétiques significatifs.",
     ["Collecter 12 mois de consommations par source.", "Identifier les usages et leur part.", "Retenir les usages significatifs et leurs variables pertinentes.", "Définir les IPÉ et la situation de référence.", "Identifier et prioriser les opportunités."],
     ["Revue énergétique", "Fiches IPÉ"], "Évolution des IPÉ"),
    # ISO 42001
    ("PR-IA-01", "Évaluation d'impact des systèmes d'IA", "ISO 42001", "6.1.4", "Évaluer les effets des systèmes d'IA sur les personnes et la société.",
     ["Inventorier les systèmes d'IA et leurs usages.", "Identifier les personnes concernées et les risques (biais, sécurité, transparence).", "Évaluer et décider des mesures.", "Revoir à chaque évolution du système."],
     ["Inventaire des systèmes d'IA", "Évaluations d'impact"], "Pourcentage de systèmes évalués"),
]

# (code, module, normes, public, durée, objectifs)
TRAININGS = [
    ("F-01", "Sensibilisation au système de management", C, "Tout le personnel", "2 h",
     ["Connaître la politique et les objectifs", "Comprendre sa contribution", "Savoir signaler un écart"]),
    ("F-02", "Pilotes de processus : piloter et mesurer", C, "Pilotes de processus", "4 h",
     ["Animer son processus", "Suivre ses indicateurs", "Traiter risques et actions"]),
    ("F-03", "Auditeurs internes (ISO 19011)", C, "Futurs auditeurs internes", "2 jours",
     ["Planifier un audit", "Conduire les entretiens et échantillonner", "Rédiger des constats factuels"]),
    ("F-04", "Non-conformités et actions correctives", C, "Encadrement", "3 h",
     ["Analyser les causes (5 pourquoi, Ishikawa)", "Définir des actions efficaces", "Vérifier l'efficacité"]),
    ("F-05", "Culture qualité et comportement éthique (ISO 9001:2026)", "ISO 9001", "Direction et encadrement", "2 h",
     ["Comprendre les évolutions 2026", "Incarner la culture qualité", "Promouvoir l'éthique"]),
    ("F-06", "Gestes environnementaux et tri des déchets", "ISO 14001", "Tout le personnel", "1 h 30",
     ["Connaître les aspects significatifs", "Trier correctement", "Réagir en cas de déversement"]),
    ("F-07", "Sécurité au poste, EPI et évacuation", "ISO 45001", "Opérateurs", "2 h",
     ["Connaître les risques de son poste", "Porter les EPI", "Évacuer en sécurité"]),
    ("F-08", "Cybersécurité et hameçonnage", "ISO 27001", "Tout le personnel", "1 h 30",
     ["Reconnaître un hameçonnage", "Protéger ses accès", "Signaler un incident"]),
    ("F-09", "Bonnes pratiques d'hygiène et HACCP", "ISO 22000", "Personnel de production", "3 h",
     ["Appliquer les BPH", "Surveiller les CCP", "Réagir en cas de dépassement"]),
    ("F-10", "Pédagogie centrée sur l'apprenant", "ISO 21001", "Formateurs et enseignants", "3 h",
     ["Concevoir une séquence", "Évaluer équitablement", "Recueillir la satisfaction"]),
    ("F-11", "Énergie : usages significatifs et bons réflexes", "ISO 50001", "Exploitation et maintenance", "2 h",
     ["Connaître les UES", "Suivre les IPÉ", "Réduire les consommations"]),
    ("F-12", "IA responsable", "ISO 42001", "Équipes produit et données", "3 h",
     ["Évaluer les risques et impacts", "Documenter un système d'IA", "Superviser les décisions"]),
]


def _applies(scope: str, std: str) -> bool:
    return scope == C or std in scope.split(",")


def procedures_for(std: str) -> list[tuple]:
    return [p for p in PROCEDURES if _applies(p[2], std)]


def trainings_for(std: str) -> list[tuple]:
    return [t for t in TRAININGS if _applies(t[2], std)]


def procedure_doc(client: dict, std: str, proc: tuple, intro: str | None = None) -> dict:
    code, title, _, clauses, purpose, steps, records, kpi = proc
    name = client.get("name", "")
    return {
        "kind": "procedure", "standard": std, "client": name, "date": dt.date.today().isoformat(), "ai": bool(intro),
        "title": f"{code} — {title} ({name})",
        "footer": "Procédure rédigée par l'agent Responsable qualité de Kapsi-Q — à valider par le responsable du système avant diffusion.",
        "sections": [
            {"heading": "Cartouche", "table": {"columns": ["Code", "Indice", "Rédigé par", "Vérifié par", "Approuvé par"], "rows": [[code, "0", "Agent Kapsi-Q", "", ""]]}},
            {"heading": "1. Objet", "paragraphs": [intro or purpose]},
            {"heading": "2. Domaine d'application", "paragraphs": [f"{name} — {client.get('activities') or client.get('sector') or 'ensemble des activités'}."]},
            {"heading": "3. Références", "bullets": [f"{std}, chapitre(s) {clauses}", "Manuel / domaine d'application du système"]},
            {"heading": "4. Responsabilités", "table": {"columns": ["Rôle", "Responsabilité"], "rows": [
                ["Direction", "Approuve la procédure et fournit les ressources"], ["Responsable du système", "Tient la procédure à jour et en vérifie l'application"],
                ["Pilotes de processus", "Appliquent la procédure dans leur périmètre"]]}},
            {"heading": "5. Déroulement", "table": {"columns": ["N°", "Étape", "Responsable"], "rows": [[str(i + 1), s, "À préciser"] for i, s in enumerate(steps)]}},
            {"heading": "6. Enregistrements", "bullets": records},
            {"heading": "7. Indicateur de suivi", "paragraphs": [kpi]},
        ],
    }


def training_pack(client: dict, std: str, mod: tuple, quiz_rows: list) -> dict:
    code, title, _, audience, duration, goals = mod
    seq = [["Accueil, objectifs, tour de table", "10 min"], ["Apports : " + goals[0], "25 %"], ["Apports : " + goals[1], "25 %"],
           ["Mise en pratique sur un cas de l'entreprise", "30 %"], ["Quiz d'évaluation et synthèse", "15 min"]]
    return {
        "kind": "training_pack", "standard": std, "client": client.get("name", ""), "date": dt.date.today().isoformat(), "ai": False,
        "title": f"{code} — {title} ({client.get('name', '')})",
        "footer": "Support préparé par l'agent Formateur de Kapsi-Q — à adapter et valider par le formateur.",
        "sections": [
            {"heading": "Fiche de la formation", "table": {"columns": ["Élément", "Valeur"], "rows": [["Public", audience], ["Durée", duration], ["Référentiel", std], ["Formateur", ""]]}},
            {"heading": "Objectifs pédagogiques", "bullets": goals},
            {"heading": "Déroulé", "table": {"columns": ["Séquence", "Durée"], "rows": seq}},
            {"heading": "Quiz d'évaluation", "table": {"columns": ["Question", "Propositions", "Réponse"], "rows": quiz_rows}},
            {"heading": "Feuille d'émargement", "table": {"columns": ["Nom et prénom", "Fonction", "Signature"], "rows": [["", "", ""] for _ in range(10)]}},
            {"heading": "Évaluation à chaud (1 à 5)", "table": {"columns": ["Critère", "Note"], "rows": [["Atteinte des objectifs", ""], ["Clarté", ""], ["Utilité pour le poste", ""], ["Animation", ""]]}},
        ],
    }
