# Notes de version

## 2.3.0 — 27 novembre 2026 · Pilotes IA
- **Un pilote IA par processus** (10) : Stratégie, Amélioration, Pédagogie, Stages, Examens, Scolarité, Compétences, Services généraux, Vie universitaire, Finances (Campus → Pilotes IA).
- Chacun a une mission, une liste de surveillance, une routine et des règles d'escalade ; il calcule la **santé du processus** (0-100), envoie ses **alertes au pilote humain nommé** et ouvre une action sur chaque indicateur sous la cible (sans doublon).
- **Mandat limité** : lire, relancer, ouvrir une action, préparer, alerter. Jamais : changer un statut saisi par une personne, clôturer une action ou une NC, valider un document, modifier une cible.
- **Passage automatique** chaque jour ou chaque lundi à 7 h, tant que le poste hôte est allumé.
- Le pilote humain de chaque processus se nomme à l'écran (ISO 21001, 5.3).

## 2.2.0 — 26 novembre 2026 · SMOE complet (ISO 21001)
- **Les 9 autres processus du SMOE** sont opérationnels (Campus → Processus SMOE) : DIR Pilotage et stratégie, PAC Amélioration continue, PED-04 Pédagogie, GSP-05 Stages et PFE, EXD-06 Examens et délibérations, GSA-07 Scolarité, GRH-08 Ressources humaines, GVU-10 Vie universitaire, GAF-11 Finances et achats.
- Pour chacun : fiche (finalité, pilote, entrées, sorties, activités, exigences ISO 21001), registres avec statuts et délais, indicateurs **calculés automatiquement** sur les registres (35 indicateurs au total avec les 8 du GSG).
- **Guichet étendu** : attestations et relevés de notes, conventions de stage, réclamations sur les notes, demandes d'activité de club, avec suivi par ticket.
- **4 nouveaux agents** : Pilote SMOE, Rédacteur des fiches processus, Revue des processus (actions ouvertes sur les écarts), Revue de direction (éléments d'entrée ISO 21001, 9.3.2).
- Registres, codes de formulaires et cibles des processus autres que GSG : **proposés, à valider par les pilotes** (le dossier de l'ISI ne décrivait que le GSG).

## 2.1.0 — 26 novembre 2026 · Kapsi Campus (ISO 21001)
- **Menu Campus** : gestion opérationnelle d'un établissement d'enseignement, construite sur le processus Services généraux (GSG) de l'ISI.
- **Guichet numérique** (`/guichet`, QR code + code d'accès) : tirage (48 h minimum imposées), intervention, informatique, véhicule, salle, vidéoprojecteur, fournitures, stylos, clé, nettoyage, archives, réclamations ; ticket de suivi et accusé de réception avec avis.
- **Demandes** en colonnes par statut, **équipements** avec fiches de vie (pannes, arrêts, coûts), **plannings** GSG-PL-01 à 06, **courrier** (RG-01 à 03) et **appels** (RG-04), **réclamations** (délai 7 jours), **inventaires d'archive**.
- **19 indicateurs** sur 10 processus : les 8 indicateurs GSG calculés automatiquement avec les formules de la fiche GSG-PP ; les autres saisis par les pilotes ; cibles modifiables.
- **7 agents Campus** : Pilote Campus, Répartiteur des demandes, Planificateur de maintenance, Gestionnaire des réclamations, Analyste satisfaction, Tableau de bord (GSG-TAB-02), Rapport annuel.
- Démo : l'université NovaTech reçoit 7 mois d'activité simulée ; bouton « Charger la démonstration » pour tout établissement.

## 2.0.0 — 23 novembre 2026
- **Arbre des agents** : vue « arbre de compétences » par client et par norme (verrouillé, disponible, acquis, maîtrisé), lancement d'un agent au clic ; le nœud Certification reste réservé à l'organisme accrédité.
- **Carte ISO gratuite** (`docs/marketing/carte_iso.html`) : page publique de 6 questions pour attirer des prospects.
- **Agents** : Chef de mission, Analyste des preuves, Responsable qualité, Formateur, Auditeur interne, Actions correctives, Pilote du système, Pré-certification.
- **Documents et Drive** : indexation plein texte des dossiers du poste hôte (Word, Excel, PowerPoint, PDF), recherche, sorties Word rangées par client et par norme.
- **Procédures types** par norme (système commun + 9001, 14001, 45001, 27001, 22000, 21001, 50001, 42001) et 12 modules de formation.
- **Actions correctives** et **formations** suivies par client ; **validation** des documents (statut, validateur, date).
- **Indice de préparation à la certification** avec alertes.
- Audit de type « interne » ; tableau de bord enrichi (documents à valider, actions ouvertes).
- **Démo : 28 entreprises** (14 nouvelles : pharmacie, cimenterie, laiterie, aéronautique, BTP, eau minérale, port, université, cartonnerie, centre d'appels, photovoltaïque, tannerie, minoterie, assurance), avec le travail des agents déjà effectué (documents produits et en partie validés, actions, formations, indice de préparation de 23 à 77/100). Chargement : `charger_demo.bat`.
- Nouvelle dépendance : `pypdf`. Base de données migrée automatiquement.
