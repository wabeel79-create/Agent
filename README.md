# Kapsi ISO

Assistant ISO **privé** pour cabinets de conseil, par **SmartCell Technologies** (Soukra, Ariana).
Installé sur le serveur du cabinet : aucune donnée client ne sort, aucune connexion Internet nécessaire.

## Fonctions (v0.1)

| Livrable | Description |
|---|---|
| Politique qualité | Projet personnalisé au client, prêt à signer |
| Cartographie des processus | Processus management / réalisation / support, construits depuis les activités du client |
| Procédure maîtrise documentaire (§7.5) | Procédure complète avec responsabilités |
| Check-list d'audit interne | Questions et preuves attendues, chapitres 4 à 10 |
| **Analyse d'écarts** | Saisie C / P / NC / NA par exigence → taux de conformité + plan d'actions |
| **Transition ISO 9001:2015 → 2026** | Écarts et plan d'actions pour les clients déjà certifiés |
| Matrice système intégré | Correspondance ISO 9001 / 14001 / 45001 / 50001 |
| Quiz de formation | QCM de sensibilisation pour les sessions de formation |
| Assistant ISO | Questions-réponses sur les exigences |

Tous les livrables s'affichent dans l'application et s'exportent en **Word (.docx)** à l'en-tête du cabinet.

## Démarrage rapide (démo sur PC)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Ouvrir http://localhost:8000 . Sur iPhone (même Wi-Fi) : `http://IP-DU-PC:8000` dans Safari → Partager → « Sur l'écran d'accueil ».

## Installation chez le client (serveur)

```bash
cp .env.example .env          # renseigner KAPSI_CABINET et KAPSI_TOKEN
docker compose up -d          # mode hors ligne (générateurs)
docker compose --profile ia up -d && docker compose exec ollama ollama pull qwen2.5:7b   # avec IA locale (GPU NVIDIA)
```

Puis mettre `KAPSI_BACKEND=ollama` dans `.env` et `docker compose up -d` à nouveau.

## Moteurs IA

| `KAPSI_BACKEND` | Fonctionnement |
|---|---|
| `none` (défaut) | Générateurs déterministes : fiables, instantanés, sans GPU |
| `ollama` | Modèle local via Ollama, enrichit les textes et l'assistant |
| `kapsi` | Modèle Kapsi : module Python (`KAPSI_MODEL_MODULE`) exposant `generate(prompt) -> str` |

Si le modèle ne répond pas, l'application revient automatiquement aux générateurs.

## Sécurité

- Données dans SQLite (`/data`, volume Docker), sur le serveur du cabinet.
- Jeton d'accès optionnel (`KAPSI_TOKEN`), à saisir dans ⚙ Réglages.
- Pour un accès hors du bureau : passer par un VPN ou un reverse proxy HTTPS ; ne pas exposer le port 8000 directement sur Internet.

## Avertissement normatif

La base de connaissances contient des **résumés rédigés par SmartCell**, pas le texte des normes ISO, protégé par le droit d'auteur.
Les éléments ISO 9001:2026 sont à vérifier contre le texte officiel. Tous les livrables sont des projets à valider par le consultant.

## Tests

```bash
pip install -r requirements-dev.txt && pytest -q
```

API documentée : http://localhost:8000/api/docs
