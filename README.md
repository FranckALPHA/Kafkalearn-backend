# 🎓 KafkaLearn Backend

Backend API pour la plateforme **KafkaLearn** — moteur de recherche sémantique hybride et agent d'apprentissage intelligent pour les épreuves scolaires camerounaises.

> Plus de 2000 épreuves indexées, analysées et restituées via une architecture moderne et modulaire.

---

## ✨ Fonctionnalités

- **Recherche Hybride (Vespa + Meilisearch)** : Combine recherche vectorielle (ANN) et lexicale (BM25) pour des résultats pertinents.
- **Agent Skills IA (Gemini / Mistral)** : Fiches de révision, Quiz interactifs, Solvers, Corrigés, Graphes mathématiques.
- **Architecture Modulaire** : Organisation par domaines — Search, Skills, Users, Payment, Notifications, Ingest.
- **Gestion de Projet avec `uv`** : Gestion de dépendances ultra-rapide et déterministe (`pyproject.toml`).
- **Sessions Redis** : Gestion des quotas IA et historique de session (TTL configurable).
- **Paiements NotchPay** : Passerelle de paiement pour les abonnements (Premium/Access).
- **Notifications FCM** : Notifications push via Firebase Cloud Messaging.
- **Tâches Async Celery** : Workers séparés pour tâches lourdes (LLM, PDF) et emails.

---

## 🏗️ Architecture

```
app/
├── core/                   # Services transversaux & Configuration
│   ├── config.py           # Settings & variables d'environnement
│   ├── database.py         # SQLAlchemy & Modèles globaux
│   ├── api_errors.py       # Gestion centralisée des erreurs
│   └── database_init.py    # Initialisation de la BDD
│
├── modules/
│   ├── search/             # Moteur RAG (Retriever, Reranker, Responder)
│   │   ├── services/       # Orchestrator, Retriever, Reranker, Analytics
│   │   ├── routes/         # Endpoints recherche & admin
│   │   ├── models/         # Modèles SQL (logs, suggestions)
│   │   ├── schemas/        # Schémas Pydantic (requêtes/réponses)
│   │   ├── utils/          # Vespa client, Quota manager, Constants
│   │   └── jobs/           # Tâches Celery liées à la recherche
│   │
│   ├── skills/             # Agent IA (Fiche, Quiz, Solver, etc.)
│   │   ├── services/       # Skills, Chat, Quiz Correction, Analytics
│   │   ├── routes/         # Endpoints skills & chat
│   │   ├── models/         # Sessions, Messages, Logs
│   │   ├── schemas/        # Requêtes & réponses
│   │   └── jobs/           # Celery app, tâches & crons
│   │
│   ├── users/              # Authentification & Gestion Profils
│   ├── payment/            # Plans & Abonnements NotchPay
│   ├── notifications/      # Notifications FCM (topics, devices)
│   ├── ingest/             # Indexation & Workers
│   └── school/             # Gestion des Établissements
│
└── main.py                 # Point d'entrée FastAPI
```

---

## 🚀 Démarrage Rapide

### 1. Prérequis

- **uv** : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker & Docker Compose** : PostgreSQL, Redis, Vespa, Meilisearch, Celery
- **Fichier `.env`** : copier `.env.example` et remplir les valeurs

```bash
cp .env.example .env
```

### 2. Installation & Lancement

```bash
# 1. Cloner le repo
git clone https://github.com/FranckALPHA/Kafkalearn-backend.git
cd Kafkalearn-backend

# 2. Synchroniser l'environnement
uv sync

# 3. Lancer l'infrastructure (Postgres, Redis, Vespa, Meilisearch, Celery)
docker compose up -d

# 4. Déployer le schéma Vespa (si nécessaire)
uv run python deploy_vespa.py

# 5. Appliquer les migrations SQL
uv run alembic upgrade head

# 6. Démarrer le serveur API
uv run uvicorn app.main:app --port 9990 --reload
```

### 3. Mode développement (auto-création BDD)

```bash
AUTO_CREATE_DB=1 uv run uvicorn app.main:app --port 9990 --reload
```

---

## 📡 Endpoints Principaux

Tous les endpoints sont exposés sous le préfixe `/api/v1`.

| Action | Méthode | Endpoint | Description |
|---|---|---|---|
| **Recherche** | `POST` | `/api/v1/search/rechercher` | Recherche sémantique hybride |
| **Recherche Lite** | `POST` | `/api/v1/search/lite` | Recherche textuelle rapide (Meilisearch) |
| **IA Skills** | `POST` | `/api/v1/skills/run` | Lancement d'un agent IA (Fiche, Quiz...) |
| **Quiz Correction** | `POST` | `/api/v1/skills/quiz/corriger` | Corrige les réponses quiz + profil cognitif |
| **Chat Skills** | `POST` | `/api/v1/skills/chat` | Session conversationnelle avec un skill |
| **Auth** | `POST` | `/api/v1/users/auth/login` | Connexion & génération de token |
| **Notifications** | `POST` | `/api/v1/notifications/register` | Enregistre un device + topics |
| **Notifications** | `GET` | `/api/v1/notifications/me/history` | Historique notifications utilisateur |

---

## 🧠 Exemples d'Utilisation

### Recherche Hybride

```bash
POST /api/v1/search/rechercher
```

```json
{
  "query": "dérivée d'une fonction",
  "top_k": 5
}
```

### Lancer un Quiz

```bash
POST /api/v1/skills/run
```

```json
{
  "skill": "quiz",
  "prompt": "quiz sur la Révolution française",
  "params": {
    "nb_questions": 10,
    "matiere": "Histoire",
    "niveau": "Terminale"
  }
}
```

---

## ⚙️ Configuration LLM

Pour éviter la surcharge des appels LLM :

| Variable | Description | Défaut |
|---|---|---|
| `LLM_MAX_CONCURRENT_REQUESTS` | Max appels LLM en parallèle | `2` |
| `LLM_MIN_INTERVAL_MS` | Délai minimal entre 2 appels (ms) | `250` |

### Providers supportés

- **Mistral** (`mistral-small-latest`)
- **Gemini** (`gemini-2.0-flash-lite`)
- **DeepSeek** (`deepseek-chat`)
- **OpenRouter** (multi-clés avec fallback)

---

## 🐳 Infrastructure Docker

| Service | Port | Description |
|---|---|---|
| **PostgreSQL** | `15432` | Base de données principale (pgvector) |
| **Redis** | `16379` | Cache, sessions, broker Celery |
| **Vespa** | `18080` / `19071` | Moteur de recherche vectoriel |
| **Meilisearch** | `17700` | Moteur de recherche textuelle |
| **Celery Worker** | — | Tâches par défaut |
| **Celery Heavy** | — | Tâches LLM & PDF |
| **Celery Emails** | — | Envoi d'emails |
| **Celery Beat** | — | Planification de tâches |

---

## 🧪 Stack Technique

| Composant | Technologie |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| BDD | PostgreSQL + pgvector |
| Cache / Broker | Redis 7 |
| Search Vectoriel | Vespa |
| Search Textuel | Meilisearch |
| Tâches Async | Celery + Redis |
| LLM | Mistral / Gemini / DeepSeek / OpenRouter |
| Embeddings | FastEmbed |
| Notifications | Firebase Admin SDK |
| Paiement | NotchPay |
| Gestionnaire | uv |

---

## 🚧 Roadmap

- [x] Refonte architecturale modulaire
- [x] Migration vers `uv`
- [x] Intégration des paiements NotchPay
- [x] Notifications FCM
- [ ] Tests unitaires & d'intégration
- [ ] Interface Dashboard Web
- [ ] Documentation OpenAPI complète
- [ ] CI/CD automatisé

---

**Développé avec ❤️ pour l'éducation au Cameroun**
