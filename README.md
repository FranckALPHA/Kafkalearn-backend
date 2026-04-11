# 🇨🇲 RAG Épreuves Cameroun (Backend v2.3.1)

Moteur de recherche sémantique hybride et Agent d'Apprentissage (Skills) pour les épreuves scolaires camerounaises.
Plus de 2000 épreuves indexées, analysées et restituées via une architecture moderne et modulaire.

---

## 🌟 Nouvelles Fonctionnalités (v2.3.1)

- **Architecture Modulaire** : Refonte complète orientée "Domaines" (Users, Payment, Search, Ingest, School, Skills).
- **Gestion Moderne avec `uv`** : Remplacement de `pip` par `uv` pour une gestion de projet ultra-rapide et déterministe (`pyproject.toml`).
- **Recherche Hybride (Vespa)** : Combine recherche vectorielle (ANN) et lexicale (BM25).
- **Agent Skills IA (Gemini)** : Fiches de révision, Quiz, Solvers, Corrigés, Graphes mathématiques.
- **Système de Parrainage** : Module `referral` intégré pour récompenser les invitations.
- **Sessions Redis** : Gestion des quotas IA et historique de session (TTL 1h).
- **Paiements NotchPay** : Intégration de la passerelle de paiement pour les abonnements (Premium/Access).

---

## 🏗️ Architecture du Projet

Le projet est organisé en services transversaux (`core`) et modules métiers (`modules`) :

```text
app/
├── core/                   # Services transversaux & Configuration
│   ├── database.py         # SQLAlchemy & Modèles globaux
│   ├── redis.py            # Store Redis (Sessions & Quotas)
│   ├── security.py         # JWT & Chiffrement
│   ├── infra/              # Clients Vespa & Meilisearch
│   └── extract/            # Pipeline d'extraction PDF/OCR
├── modules/
│   ├── users/              # Authentification & Gestion Profils
│   ├── search/             # Moteur RAG (Retriever, Reranker, Responder)
│   ├── skills/             # Agent IA (Fiche, Quiz, Solver, etc.)
│   ├── notifications/      # Notifications (FCM, topics, devices)
│   ├── payment/            # Gestion des Plans & Abonnements
│   ├── referral/           # Système de Parrainage
│   ├── ingest/             # Indexation & Workers Kaggle
│   └── school/             # Gestion des Établissements
└── main.py                 # Point d'entrée FastAPI
```

---

## 🚀 Démarrage Rapide

### 1. Prérequis
- **uv** : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** : Pour PostgreSQL, Redis et Vespa.
- **.env** : Définir au minimum `JWT_SECRET_KEY` pour conserver des tokens valides entre redémarrages.
- **Notifications (FCM)** : renseigner `FIREBASE_SERVICE_ACCOUNT_PATH` (voir `.env.example`).
- **Fastembed** : optionnel, `FASTEMBED_CACHE_DIR=./.cache/fastembed` pour stabiliser le cache modèles.
- **OpenRouter** : optionnel, définir `OPENROUTER_API_KEY_1..4` et `OPENROUTER_MODEL`.

### 2. Installation & Lancement
```bash
# 1. Cloner et entrer dans le dossier
cd "Rag epreuve"

# 2. Synchroniser l'environnement (uv gère tout)
uv sync

# 3. Lancer les bases de données
docker compose up -d

# 4. Déployer le schéma Vespa (si nécessaire)
uv run python deploy_vespa.py

# 5. Appliquer les migrations SQL
uv run alembic upgrade head

# 6. Démarrer le serveur
uv run uvicorn app.main:app --port 9990 --reload

# Optionnel (dev uniquement): auto-create tables au démarrage
AUTO_CREATE_DB=1 uv run uvicorn app.main:app --port 9990 --reload
```

### 2bis. Démarrage via Makefile
```bash
cd backend
make help
make docker-up
make deploy-vespa
make migrate
make dev
```

### 3. Maintenance (Refresh Tokens)
```bash
# Purger les refresh tokens expirés
uv run python scripts/cleanup_refresh_tokens.py
```

Exemple cron (toutes les nuits à 02:15) :
```cron
15 2 * * * cd /chemin/vers/Rag\ epreuve/backend && /usr/bin/env uv run python scripts/cleanup_refresh_tokens.py >> /var/log/rag_refresh_cleanup.log 2>&1
```

### 4. Maintenance (Memory hebdomadaire)
```bash
# Déclencher la régénération hebdo des packs memory
MEMORY_CRON_SECRET=change_me uv run python scripts/run_memory_weekly_regen.py --base-url http://localhost:9990
```

Exemple cron (dimanche à 03:30) :
```cron
30 3 * * 0 cd /chemin/vers/Rag\ epreuve/backend && MEMORY_CRON_SECRET=change_me /usr/bin/env uv run python scripts/run_memory_weekly_regen.py --base-url http://localhost:9990 >> /var/log/rag_memory_weekly.log 2>&1
```

### 5. Maintenance (Ingest metadata queue)
```bash
# Rejouer la file d'attente des docs avec métadonnées invalides
INGEST_CRON_SECRET=change_me uv run python scripts/run_ingest_metadata_reprocess.py --base-url http://localhost:9990 --max-items 100
```

Exemple cron (toutes les 30 minutes) :
```cron
*/30 * * * * cd /chemin/vers/Rag\ epreuve/backend && INGEST_CRON_SECRET=change_me /usr/bin/env uv run python scripts/run_ingest_metadata_reprocess.py --base-url http://localhost:9990 --max-items 100 >> /var/log/rag_ingest_metadata_queue.log 2>&1
```

Rotation de logs (`logrotate`) :
```bash
# Installer le template (adapter user/group et chemin si besoin)
sudo cp deploy/logrotate/memory_weekly.logrotate.conf /etc/logrotate.d/rag_memory_weekly

# Variante portable serveur (log dans /var/log)
# sudo cp deploy/logrotate/memory_weekly.logrotate.generic.conf /etc/logrotate.d/rag_memory_weekly

# Vérification (dry-run)
sudo logrotate -d /etc/logrotate.d/rag_memory_weekly

# Forcer une rotation de test
sudo logrotate -f /etc/logrotate.d/rag_memory_weekly
```

---

## 📡 Endpoints Principaux

Tous les endpoints sont exposés sous le préfixe `/api/v1`.

| Action | Methode | Endpoint | Description |
|---|---|---|---|
| **Recherche** | `POST` | `/api/v1/search/rechercher` | Recherche sémantique hybride |
| **Recherche Lite** | `POST` | `/api/v1/search/lite` | Recherche textuelle rapide (Meilisearch, sans IA) |
| **IA Skills** | `POST` | `/api/v1/skills/run` | Lancement d'un agent IA (Fiche, Quiz...) |
| **Quiz Correction** | `POST` | `/api/v1/skills/quiz/corriger` | Corrige les réponses quiz et met à jour le profil cognitif |
| **Auth** | `POST` | `/api/v1/users/auth/login` | Connexion & Génération Token |
| **Indexation** | `POST` | `/api/v1/ingest/indexer` | Drag & Drop d'épreuves PDF |
| **Indexation Async** | `POST` | `/api/v1/ingest/indexer-async` | Indexation en tâche de fond |
| **Indexation Report** | `GET` | `/api/v1/ingest/indexer-report/{job_id}` | Suivi d'une indexation async |
| **Scan Dossier** | `POST` | `/api/v1/ingest/scan-folder` | Lance un scan en arrière-plan |
| **Rapport Scan** | `GET` | `/api/v1/ingest/scan-report/{scan_id}` | Suivi d'avancement/résultat d'un scan |
| **Ingest Cron Queue** | `POST` | `/api/v1/ingest/cron/reprocess-metadata-queue` | Rejoue la file d'attente métadonnées (protégée par `X-Cron-Secret`) |
| **Memory Cron** | `POST` | `/api/v1/memory/cron/weekly-regeneration` | Régénération hebdomadaire automatique (protégée par `X-Cron-Secret`) |
| **Memory Statut** | `GET` | `/api/v1/memory/packs/{pack_id}` | Vérifie compteurs attendus/générés/manquants |
| **Memory Items** | `GET` | `/api/v1/memory/packs/{pack_id}/items` | Liste les objets générés du pack |
| **Memory Score** | `POST` | `/api/v1/memory/packs/{pack_id}/attempts` | Corrige les réponses (QCM/cloze/...) et enrichit le profil cognitif |
| **École Admin**| `GET`  | `/api/v1/school/dashboard` | Vue d'ensemble école |
| **École IA**   | `GET`  | `/api/v1/school/stats` | Consommation IA globale |
| **École Pay**  | `POST` | `/api/v1/school/renouveler`| Paiement / Renouvellement |
| **Notifications** | `POST` | `/api/v1/notifications/register` | Enregistre un device + topics |
| **Notifications** | `POST` | `/api/v1/notifications/send` | Envoi à un user |
| **Notifications** | `POST` | `/api/v1/notifications/topic` | Envoi à un topic |
| **Notifications** | `GET` | `/api/v1/notifications/me/history` | Historique utilisateur |

---

## 🧠 Flux Quiz Interactif (Frontend)

1. Générer le quiz
```http
POST /api/v1/skills/run
```
```json
{
  "skill": "quiz",
  "prompt": "quiz sur la Révolution française",
  "params": {"nb_questions": 10, "matiere": "Histoire", "niveau": "Terminale"}
}
```

2. Soumettre les réponses utilisateur pour correction + profil cognitif
```http
POST /api/v1/skills/quiz/corriger
```

### 🔎 Exemples Recherche

Recherche hybride (avec IA) :
```http
POST /api/v1/search/rechercher
```
```json
{
  "query": "derivee d une fonction",
  "top_k": 5
}
```

Recherche textuelle rapide (Meilisearch) :
```http
POST /api/v1/search/lite
```
```json
{
  "query": "probatoire math 2022",
  "matiere": "Mathématiques",
  "niveau": "1ere",
  "serie": "C",
  "annee": 2022,
  "limite": 10
}
```
```json
{
  "quiz_data": {
    "matiere": "Histoire",
    "niveau": "Terminale",
    "questions": [
      {"numero": 1, "reponse_correcte": "A", "options": ["A) ...", "B) ..."], "explication": "..."},
      {"numero": 2, "reponse_correcte": "C", "options": ["A) ...", "B) ...", "C) ..."], "explication": "..."}
    ]
  },
  "answers": [
    {"question_numero": 1, "user_answer": "A"},
    {"question_numero": 2, "user_answer": "B"}
  ],
  "duration_seconds": 180,
  "show_correction": true
}
```

Réponse:
- score global (`score_percent`)
- détails question-par-question (`details`)
- signal faible (`weak_signal`)
- mise à jour auto du profil cognitif utilisateur connecté

---

## 🚧 Roadmap
- [x] Refonte architecturale modulaire.
- [x] Migration vers `uv`.
- [x] Intégration réelle des paiements NotchPay.
- [x] API Dashboard admin pour la gestion des écoles.
- [ ] Interface graphique (Web UI) pour le dashboard.
- [ ] Tests unitaires automatisés par module.

---

**Développé avec ❤️ pour l'éducation au Cameroun**

## ⚙️ Lissage des requêtes LLM

Pour éviter d'envoyer trop de requêtes simultanées au fournisseur LLM :
- `LLM_MAX_CONCURRENT_REQUESTS` : nombre max d'appels LLM en parallèle (défaut: `2`)
- `LLM_MIN_INTERVAL_MS` : délai minimal entre 2 appels LLM (défaut: `250` ms)

Routage LLM par tâche (optionnel) :
- `LLM_PROVIDER_DEFAULT` : provider par défaut (`mistral|deepseek|gemini`)
- `LLM_PROVIDER_METADATA` : extraction de métadonnées ingest
- `LLM_PROVIDER_MEMORY` : génération objets memory
- `LLM_PROVIDER_SEARCH` : réponse RAG
- `LLM_PROVIDER_PROFILE_REPORT` : rapport cognitif
- `LLM_PROVIDER_INTENT` / `LLM_PROVIDER_PARAM_EXTRACT` : routage et extraction paramètres
- `LLM_PROVIDER_SKILL_*` : provider dédié par skill (`QUIZ`, `FICHE`, etc.)
