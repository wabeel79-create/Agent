# Kapsi-Q 2.0 — Guide des agents

## 1. Préparer l'accès aux documents
1. Sur le poste qui fait tourner Kapsi-Q, ouvrez **Réglages → Documents et Drive**.
2. Ajoutez les dossiers du client (lecture seule), par exemple `D:\\Clients\\Société X`.
3. **Google Drive** : installez « Google Drive pour ordinateur », connectez le compte, puis ajoutez le dossier, par exemple `G:\\Mon Drive\\Clients`.
4. Ajoutez un dossier **en écriture** pour les sorties (les agents y créent `Kapsi-Q\\<client>\\<norme>`).
5. Cliquez **Indexer maintenant**. Formats lus : Word, Excel, PowerPoint, PDF (texte), TXT, CSV, MD.

Seul le poste hôte peut modifier ces dossiers (protection contre un accès depuis le réseau).

## 2. Les agents
| Agent | Rôle | Ce qu'il produit |
|---|---|---|
| Chef de mission | Enchaîne tous les agents | Tout ce qui suit + indice de préparation |
| Analyste des preuves | Rapproche chaque exigence des documents trouvés | Cartographie des preuves, propositions de cotation |
| Responsable qualité | Construit le système documentaire | Politique, cartographie, registres, objectifs, procédures, PV de revue |
| Formateur | Plan de formation | Supports, quiz, feuilles d'émargement, sessions planifiées |
| Auditeur interne | Audit interne complet | Programme, plan, grille cotée, rapport, NC |
| Actions correctives | Traite les NC | Causes (5 pourquoi), actions, responsables, échéances |
| Pilote du système | Suivi jusqu'à la certification | Tableau de pilotage, alertes, prochaines étapes |
| Pré-certification | Simulation étapes 1 et 2 | Rapport d'audit à blanc, points bloquants |

## 3. Valider
Chaque document produit porte le statut **À valider**. Ouvrez-le, relisez, cliquez **Valider ce document** et saisissez le nom et la fonction du validateur. Pour l'audit interne, relisez la grille proposée dans le module Audits avant de la valider.

## 4. Limites (à dire au client)
- Le certificat est délivré uniquement par un organisme certificateur accrédité (ISO/IEC 17021-1).
- Un audit interne doit être conduit sous la responsabilité d'un auditeur compétent et impartial (ISO 19011) : l'agent prépare, l'humain valide.
- Les propositions de cotation reposent sur la présence de documents, pas sur leur application terrain : les entretiens et visites restent nécessaires.
