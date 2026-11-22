# Kapsi-Q

**Plateforme de mise en place des systèmes de management ISO et d'audit tierce partie**, par **SmartCell Technologies** (Soukra, Ariana).
Installée sur le serveur du cabinet de conseil : les données clients restent chez lui, et la plateforme fonctionne sans Internet.

## Normes couvertes (v0.2)

ISO 9001 · ISO 14001 · ISO 45001 · ISO 21001 · ISO 27001 (avec annexe A et Déclaration d'applicabilité) · ISO 50001 · ISO 22000 · ISO 42001 (IA).
Toutes partagent la structure harmonisée (chapitres 4 à 10) plus leurs exigences spécifiques. **Pour ajouter une norme**, ajoutez une entrée dans `app/knowledge/standards.json`, sans modifier de code.

## Modules

| Module | Contenu |
|---|---|
| **Tableau de bord** | Indicateurs du cabinet, projets par norme, constats d'audit, avancement de chaque projet (graphiques) |
| **Mise en place** (par client et par norme) | Diagnostic d'écarts avec radar de conformité en temps réel · feuille de route en 9 phases (du diagnostic à la certification) · livrables |
| **Livrables** | Politique · cartographie des processus · registre des risques / aspects environnementaux / DUER / risques SI / HACCP · objectifs et indicateurs · procédure documentaire · programme d'audit interne · check-list d'audit · PV de revue de direction · quiz de formation · DdA 27001 (93 mesures) · transition ISO 9001:2026 · matrice système intégré |
| **Audit tierce partie** | Étape 1, étape 2, surveillance, renouvellement, audit à blanc · audits intégrés multi-normes · plan d'audit avec durée indicative (IAF MD5) · grille de cotation PF / C / OA / NC mineure / NC majeure · questions et preuves à échantillonner · décision proposée automatiquement · rapport d'audit avec fiches de NC et plan d'actions correctives |
| **Rédacteur IA** | Rédige procédures, instructions, manuels, supports de formation… pour un client et une norme |
| **Assistant** | Questions-réponses sur les exigences de toutes les normes |

Chaque document s'affiche dans la plateforme et s'exporte en **Word (.docx)** ou en PDF (impression).

## Démarrage rapide

**Windows :** double-cliquer sur `demarrer_windows.bat`. Le script installe les dépendances, charge des clients de démonstration fictifs et ouvre le navigateur.

**Manuel :**
```bash
python -m pip install -r requirements.txt
python -m app.demo            # facultatif : données de démonstration
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Puis ouvrir http://localhost:8000. Sur iPhone (même Wi-Fi) : `http://IP-DU-PC:8000` → Partager → « Sur l'écran d'accueil ».

## Intelligence artificielle (Réglages → Moteur d'IA)

| Fournisseur | Coût | Confidentialité |
|---|---|---|
| Aucun (par défaut) | Gratuit | Générateurs Kapsi-Q, 100 % local |
| **Ollama** (Llama 3, DeepSeek-R1, Qwen) | Gratuit | **100 % local**, recommandé chez le client |
| Groq (Llama) | Offre gratuite limitée | Données envoyées en ligne |
| OpenRouter (modèles `:free`) | Gratuit, limité | Données envoyées en ligne |
| DeepSeek API | Payant, bas coût | Données envoyées en ligne |
| Kapsi (module Python) | — | Local |

Ollama : installer depuis ollama.com, puis `ollama pull llama3.1:8b` (ou `deepseek-r1:8b`). Choisir « Ollama » dans Réglages et cliquer sur **Tester la connexion**.
Les noms de modèles gratuits changent souvent chez les fournisseurs en ligne : ils sont modifiables dans Réglages.
Si le modèle ne répond pas, Kapsi-Q revient automatiquement aux générateurs, donc la démo ne bloque jamais.

## Installation serveur (Docker)

```bash
cp .env.example .env
docker compose up -d                       # plateforme
docker compose --profile ia up -d          # + Ollama sur GPU NVIDIA
docker compose exec ollama ollama pull llama3.1:8b
```
Dans Réglages, choisir Ollama avec l'URL `http://ollama:11434`.

## Sécurité

- Base SQLite locale (`data/`, ou volume Docker `/data`), clés API jamais renvoyées au navigateur.
- Jeton d'accès optionnel (`KAPSI_TOKEN`).
- Pour un accès hors du bureau : VPN ou reverse proxy HTTPS ; ne pas exposer le port 8000 directement sur Internet.

## Avertissements

- La base contient des **résumés rédigés par SmartCell**, pas le texte des normes ISO, protégé par le droit d'auteur.
- Durées d'audit **indicatives** : l'organisme certificateur fixe la durée officielle.
- Éléments ISO 9001:2026 à vérifier contre le texte publié. Tous les livrables sont des projets à valider par le consultant.

## Développement

```bash
python -m pip install -r requirements-dev.txt && python -m pytest -q
```
API documentée : http://localhost:8000/api/docs
