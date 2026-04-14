# 🎓 KafkaLearn Backend

Backend API pour la plateforme **KafkaLearn** — moteur de recherche sémantique hybride, **graphe cognitif** et agent d'apprentissage intelligent pour les épreuves scolaires camerounaises.

> Plus de 2000 épreuves indexées, analysées et restituées via une architecture moderne et modulaire.

---

## ✨ Fonctionnalités

- **Recherche Hybride (Vespa + Meilisearch)** : Combine recherche vectorielle (ANN) et lexicale (BM25).
- **🧠 Graphe Cognitif** : Deux couches — globale (programme camerounais) + personnelle (lacunes, maîtrises, prérequis). Déduplication sémantique automatique.
- **🤖 Coach IA** : Recommandations personnalisées combinant graphe cognitif + 4 couches de signaux (temporel, comportemental, cognitif, contextuel).
- **📊 Feedback Explicite** : L'utilisateur évalue le contenu → le profil se met à jour immédiatement.
- **📅 Planning Intelligent** : Interleaving (mélange des matières) + répétition espacée (SM-2).
- **💬 Extraction LLM Automatique** : Documents → notions + prérequis → graphe global. Chat → enrichissement profil personnel.
- **Agent Skills IA** : Fiches de révision, Quiz interactifs, Solvers, Corrigés.
- **Paiements NotchPay**, **Notifications FCM**, **Tâches Async Celery**.

---

## 🏗️ Architecture

```
app/
├── core/                   # Configuration & Services transversaux
├── modules/
│   ├── search/             # Moteur RAG (Retriever, Reranker, Responder)
│   ├── skills/             # Agent IA (Fiche, Quiz, Solver, Chat)
│   ├── memory/             # 🧠 Graphe cognitif + Extraction LLM + SM-2
│   │   ├── models/         # concept_graph (graphe), memory_items, etc.
│   │   ├── services/       # ConceptGraphService, NotionDeduplicator
│   │   ├── routes/         # cognitive-report, graph_extraction
│   │   ├── seed/           # prerequisites_cm.py (64 arêtes globales)
│   │   └── jobs/           # Celery: extract_global_graph, cleanup
│   ├── users/              # Auth, Profil, 🧠 Coach IA, 💬 Feedback
│   │   ├── models/         # User, UserLearningProfile, UserLearningSignals
│   │   ├── services/       # CoachService, Feedback handler
│   │   └── routes/         # coach/, feedback/, profile/
│   ├── epreuves/           # Documents & recommandations
│   ├── library/            # Assets pédagogiques
│   ├── calendar/           # Planning & sessions
│   ├── payment/            # NotchPay
│   ├── notifications/      # FCM
│   └── ...
└── main.py                 # Point d'entrée FastAPI
```

---

## 🧠 Graphe Cognitif — Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    concept_graph (PostgreSQL)                    │
│                                                                 │
│  🌍 Couche GLOBALE (user_id = NULL)                             │
│  64+ arêtes PRE_REQUIS_DE — programme camerounais               │
│  arithmétique → équations → fonctions → limites → dérivées      │
│                                                                 │
│  👤 Couche PERSONNELLE (user_id = UUID)                         │
│  A_ECHOUE_SUR / MAITRISE / EN_COURS par utilisateur             │
│                                                                 │
│  + canonical_name : déduplication sémantique                    │
│  + confidence : confiance dans le lien (0.0-1.0)                │
└─────────────────────────────────────────────────────────────────┘
```

**Extraction automatique** :
- **Documents** → LLM détecte notions + prérequis → déduplication sémantique → graphe global
- **Chat/Quiz** → LLM détecte concepts → enrichit le graphe personnel

---

## 📊 4 Couches de Signaux

| Couche | Contenu | Exemple |
|--------|---------|---------|
| **Temporel** | Habitudes horaires, streak, régularité | `preferred_hours: {"20": 5, "21": 8}` |
| **Comportemental** | Profil pratique/théorique, préférences | `profile_type: "practical"`, `retry_after_failure: true` |
| **Cognitif** | Blocages profonds vs superficiels, vélocité | `deep_blockages: {"derivees": {weeks_stuck: 3}}` |
| **Contextuel** | Mode urgence, autodidacte, contraintes | `urgency_mode: true`, `days_until_exam: 5` |

---

## 🚀 Démarrage Rapide

### 1. Prérequis

- **Docker & Docker Compose** : PostgreSQL, Redis, Vespa, Meilisearch
- **Make** : `sudo apt install make` (généralement déjà installé)
- **Fichier `.env`** : copier `.env.example` et remplir les clés API

```bash
cp .env.example .env
```

### 2. Installation & Lancement (1 commande)

```bash
# 1. Cloner le repo
git clone https://github.com/FranckALPHA/Kafkalearn-backend.git
cd Kafkalearn-backend

# 2. Tout installer et lancer le serveur
make run
```

`make run` fait automatiquement :
- ✅ Installe `uv` si absent
- ✅ Installe les dépendances Python (`uv sync`)
- ✅ Télécharge le modèle FastEmbed (BAAI/bge-small-en-v1.5)
- ✅ Installe Tesseract OCR + données françaises
- ✅ Installe Poppler (pdf2image)
- ✅ Installe libmagic (détection MIME)
- ✅ Lance le serveur sur `http://0.0.0.0:9880`

### 3. Commandes Make disponibles

```bash
make run          # Setup complet + lancement du serveur
make setup        # Installation des dépendances uniquement
make server       # Lancement du serveur seul
make docker       # Démarrage de l'infrastructure Docker
make docker-down  # Arrêt de l'infrastructure Docker
make test         # Tests rapides des dépendances
make clean        # Nettoyage des caches Python
make clean-venv   # Suppression du venv (relancer avec make setup)
make help         # Affiche l'aide complète
```

### 4. Infrastructure Docker

```bash
# Démarrer la base de données et les moteurs de recherche
make docker

# Vérifier que tout tourne
docker compose ps

# Voir les logs
make docker-logs
```

### 5. Migrations (premier lancement)

```bash
# Créer les tables du graphe cognitif et des signaux
uv run python -m app.modules.memory.migration.create_concept_graph
uv run python -m app.modules.memory.seed.prerequisites_cm
uv run python -m app.modules.memory.migration.migrate_lacunes_to_graph
uv run python -m app.modules.users.migration.create_user_learning_signals
uv run python -m app.modules.users.migration.create_user_feedback
uv run python -m app.modules.ingest.migration.create_ingest_step_logs
```

### 6. Ingestion locale de documents

```bash
# Scanner un dossier de PDF (natifs ou scannés avec OCR)
curl -X POST 'http://127.0.0.1:9880/api/v1/ingest/local-folder' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"folder_path": "/home/user/documents/cours", "force": false}'
```

---

## 📡 Endpoints Principaux

### Recherche & Skills
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/search/rechercher` | Recherche sémantique hybride |
| `POST` | `/api/v1/skills/run` | Lancement d'un agent IA |
| `POST` | `/api/v1/skills/quiz/{id}/soumettre` | Correction quiz + enrichissement graphe |

### 🧠 Graphe Cognitif & Coach IA
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/memory/cognitive-report` | Rapport cognitif complet (lacunes + parcours) |
| `GET` | `/api/v1/memory/cognitive-report/{concept}/prerequis` | Chaîne de prérequis d'un concept |
| `POST` | `/api/v1/memory/admin/graph/extract-document` | Extraire notions d'un doc → graphe |
| `GET` | `/api/v1/users/coach/recommendation` | **Recommandation Coach IA** (QUOI + COMMENT) |
| `GET` | `/api/v1/users/coach/study-plan?days=7` | **Planning intelligent** (interleaving + SM-2) |
| `GET` | `/api/v1/users/coach/signals` | Voir ses 4 couches de signaux |
| `POST` | `/api/v1/users/feedback/?feedback_type=...` | **Feedback explicite** |

---

## 🐳 Infrastructure Docker

| Service | Port | Description |
|---|---|---|
| **PostgreSQL** | `15432` | Base principale (pgvector + concept_graph) |
| **Redis** | `16379` | Cache, sessions, broker Celery |
| **Vespa** | `18080` / `19071` | Moteur de recherche vectoriel |
| **Meilisearch** | `17700` | Moteur de recherche textuelle |

> **Note** : L'application tourne en local (`uvicorn`). Seul l'infrastructure externe est dans Docker.

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
| Graphe Cognitif | PostgreSQL (CTE récursifs) |
| Déduplication | FastEmbed + cosine similarity |
| LLM | OpenRouter (multi-clés, fallback) |
| Embeddings | FastEmbed (BAAI/bge-small-en-v1.5) |
| Répétition Espacée | Algorithme SM-2 |
| Tâches Async | Celery + Redis |
| Paiement | NotchPay |
| Notifications | Firebase Admin SDK |
| Gestionnaire | uv |

---

**Développé avec ❤️ pour l'éducation au Cameroun 🇨🇲**
