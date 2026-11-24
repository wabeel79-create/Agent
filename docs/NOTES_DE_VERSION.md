# Notes de version

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
