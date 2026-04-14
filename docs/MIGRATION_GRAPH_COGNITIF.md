# Migration Graph Cognitive — Plan d'exécution (TERMINÉ)

> **Stack** : PostgreSQL (graphe) + Vespa (vectoriel) + Celery (batch)
> **Principe** : 2 couches — graphe *global* (programme) + graphe *personnel* (lacunes)
> **Phase** : Dev — on supprime ce qu'il faut
> **Statut** : ✅ Phases 1-7 terminées, Phase 0 en attente

---

## Résumé de l'état actuel

| Phase | Statut | Fichiers |
|-------|--------|----------|
| **0** | ⏳ En attente (après validation) | `user_learning_profile.py` — suppression colonnes |
| **1** | ✅ Terminé | `concept_graph.py` + migration SQL |
| **1b** | ✅ Terminé | 64 arêtes globales seedées |
| **2** | ✅ Terminé | Migration des quiz_sessions + JSONB existants |
| **3** | ✅ Terminé | `ConceptGraphService` (12 méthodes) |
| **4** | ✅ Terminé | `extract_concepts_from_chat_task` Celery |
| **5** | ⏪ Sauté (Vespa déjà présent) | — |
| **6** | ✅ Terminé | 6 services refactorisés |
| **7** | ✅ Terminé | 3 endpoints cognitifs |

---

## Phase 0 — Nettoyage (ce qu'on vire)

| Suppression | Raison | Remplacement |
|---|---|---|
| `UserLearningProfile.lacunes` (JSONB) | Structure plate, pas de relations | `concept_graph` table |
| `UserLearningProfile.forces` (JSONB) | Même problème | `concept_graph` avec relation `MAITRISE` |
| `UserLearningProfile.score_par_matiere` (JSONB) | Redondant avec les tentatives | Calculé depuis `MemoryItemAttempt` |
| `UserLearningProfile.historique_recherches` (JSONB FIFO 100) | Pas exploité relationnellement | `search_logs` existe déjà — on lie au graphe |
| `UserLearningProfile.intentions_recentes` (JSONB FIFO 20) | Pas exploité | Supprimé |
| `UserLearningProfile.skills_utilises` (JSONB) | Pas exploité | Supprimé |
| `UserLearningProfile.sujets_vus` (JSONB) | Redondant avec `DocumentView` | Supprimé |
| `QuizSession.lacunes_detectees` (JSONB) | Données mortes, jamais agrégées | Migrées vers `concept_graph` |

**Ce qu'on garde de `UserLearningProfile`** :
- `matieres_frequentes` — utile pour les stats simples
- `interets` — utile pour l'onboarding
- `heures_actives`, `jours_actifs` — utiles pour le coaching
- `last_wisdom_id`, `dernier_rapport_at` — metadata fine

---

## Phase 1 — Schéma `concept_graph` (1 jour)

### 1.1 Table principale

```sql
CREATE TABLE concept_graph (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,  -- NULL = global
    source      TEXT NOT NULL,        -- "derivees", "mecanique", "adn"
    target      TEXT NOT NULL,        -- "integrales", "forces", "genetique"
    relation    TEXT NOT NULL,        -- PRE_REQUIS_DE, A_ECHOUE_SUR, MAITRISE, EN_COURS, LIEN_FAIBLE
    confidence  FLOAT DEFAULT 1.0,    -- 0.0-1.0, confiance dans le lien
    source_type TEXT NOT NULL,        -- 'manual', 'quiz', 'chat', 'inference', 'migration'
    matiere     TEXT,                 -- "Mathematiques", "Physique", "SVT"
    context     TEXT,                 -- "Quiz session 42", "Chat message 153"
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Index critiques pour les traversées de graphe
CREATE INDEX idx_cg_user_source ON concept_graph (user_id, source);
CREATE INDEX idx_cg_user_target ON concept_graph (user_id, target);
CREATE INDEX idx_cg_relation    ON concept_graph (user_id, relation);
CREATE INDEX idx_cg_source_type ON concept_graph (user_id, source_type);
CREATE INDEX idx_cg_matiere     ON concept_graph (user_id, matiere);

-- Index pour le graphe global (user_id IS NULL)
CREATE INDEX idx_cg_global ON concept_graph (source, target) WHERE user_id IS NULL;
CREATE INDEX idx_cg_global_relation ON concept_graph (source, relation) WHERE user_id IS NULL;

-- Contrainte : pas de doublon
CREATE UNIQUE INDEX idx_cg_unique_edge ON concept_graph (
    COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::UUID),
    source, target, relation
);
```

### 1.2 Types de relations

| Relation | Couche | Direction | Sémantique |
|---|---|---|---|
| `PRE_REQUIS_DE` | Globale | source → target | "Pour comprendre target, il faut maîtriser source" |
| `A_ECHOUE_SUR` | Personnelle | user → source | L'utilisateur a échoué sur ce concept |
| `MAITRISE` | Personnelle | user → source | L'utilisateur maîtrise ce concept (score > 75%) |
| `EN_COURS` | Personnelle | user → source | L'utilisateur travaille actuellement ce concept |
| `LIEN_FAIBLE` | Personnelle | source → target | Lien faible détecté par le LLM (confiance < 0.7) |

### 1.3 Seed manuel — graphe de prérequis du programme camerounais

**Fichier** : `app/modules/memory/seed/prerequisites_cm.py`

```python
# Prérequis globaux — programme camerounais
GLOBAL_EDGES = [
    # Mathématiques
    ("arithmetique", "equations", "PRE_REQUIS_DE", "Mathematiques"),
    ("equations", "fonctions", "PRE_REQUIS_DE", "Mathematiques"),
    ("fonctions", "limites", "PRE_REQUIS_DE", "Mathematiques"),
    ("limites", "derivees", "PRE_REQUIS_DE", "Mathematiques"),
    ("derivees", "integrales", "PRE_REQUIS_DE", "Mathematiques"),
    ("derivees", "etude_fonctions", "PRE_REQUIS_DE", "Mathematiques"),

    # Physique
    ("forces", "mouvement", "PRE_REQUIS_DE", "Physique"),
    ("mouvement", "energie_cinetique", "PRE_REQUIS_DE", "Physique"),
    ("energie_cinetique", "travail_mecanique", "PRE_REQUIS_DE", "Physique"),

    # SVT
    ("cellule", "adn", "PRE_REQUIS_DE", "SVT"),
    ("adn", "genetique", "PRE_REQUIS_DE", "SVT"),
    ("genetique", "evolution", "PRE_REQUIS_DE", "SVT"),

    # Chimie
    ("atome", "liaison_chimique", "PRE_REQUIS_DE", "Chimie"),
    ("liaison_chimique", "reactions", "PRE_REQUIS_DE", "Chimie"),
]
```

**Commande de seed** :
```bash
uv run python -m app.modules.memory.seed.prerequisites_cm
```

---

## Phase 2 — Migration des données existantes (1 jour)

### 2.1 Script de migration `QuizSession.lacunes_detectees` → `concept_graph`

**Fichier** : `app/modules/memory/migration/migrate_lacunes_to_graph.py`

```python
"""Migre les lacunes existantes des quiz_sessions vers concept_graph."""

from app.core.database import SessionLocal
from app.modules.skills.models import QuizSession

def migrate():
    db = SessionLocal()
    quizzes = db.query(QuizSession).filter(
        QuizSession.lacunes_detectees.isnot(None),
        QuizSession.score_percent < 50,
    ).all()

    for q in quizzes:
        for lacune in q.lacunes_detectees:
            notion = lacune.get("notion")
            if notion and q.matiere:
                # Upsert : A_ECHOUE_SUR
                db.execute("""
                    INSERT INTO concept_graph (user_id, source, target, relation, confidence, source_type, matiere, context)
                    VALUES (:uid, :concept, :concept, 'A_ECHOUE_SUR', :conf, 'migration', :matiere, :ctx)
                    ON CONFLICT DO NOTHING
                """, {
                    "uid": str(q.user_id),
                    "concept": notion,
                    "conf": min(lacune.get("erreurs", 1) * 0.2, 1.0),
                    "matiere": q.matiere,
                    "ctx": f"QuizSession {q.id}",
                })

        # Si score >= 75% → MAITRISE
        if q.score_percent >= 75 and q.matiere:
            db.execute("""
                INSERT INTO concept_graph (user_id, source, target, relation, confidence, source_type, matiere, context)
                VALUES (:uid, :concept, :concept, 'MAITRISE', :conf, 'migration', :matiere, :ctx)
                ON CONFLICT DO NOTHING
            """, {
                "uid": str(q.user_id),
                "concept": q.matiere,
                "conf": q.score_percent / 100,
                "matiere": q.matiere,
                "ctx": f"QuizSession {q.id}",
            })

    db.commit()
    print(f"Migré {len(quizzes)} quiz sessions")
```

### 2.2 Nettoyage de `UserLearningProfile`

```python
"""Nettoie les champs JSONB obsolètes après migration."""

from app.core.database import SessionLocal
from app.modules.users.models import UserLearningProfile

def cleanup_profiles():
    db = SessionLocal()
    profiles = db.query(UserLearningProfile).all()
    for p in profiles:
        p.lacunes = None
        p.forces = None
        p.score_par_matiere = None
        p.intentions_recentes = None
        p.skills_utilises = None
        p.sujets_vus = None
    db.commit()
```

---

## Phase 3 — Services graphe (2 jours)

### 3.1 `ConceptGraphService` — opérations CRUD

**Fichier** : `app/modules/memory/services/concept_graph_service.py`

```python
class ConceptGraphService:
    """Opérations sur le graphe cognitif."""

    def add_edge(self, user_id: str, source: str, target: str, relation: str,
                 confidence: float = 1.0, source_type: str = "chat",
                 matiere: str = None, context: str = None):
        """Ajoute ou met à jour une arête."""

    def get_pre_requis(self, concept: str, user_id: str = None) -> List[str]:
        """Retourne les prérequis d'un concept (global + personnel)."""

    def get_concepts_maitrises(self, user_id: str) -> List[str]:
        """Retourne les concepts maîtrisés par l'utilisateur."""

    def get_concepts_lacunes(self, user_id: str) -> Dict[str, List[str]]:
        """Retourne les lacunes par matière."""

    def get_parcours_recommande(self, user_id: str, concept_cible: str) -> List[str]:
        """Retourne le chemin d'apprentissage optimal vers un concept."""
```

### 3.2 Traversée de graphe — CTE récursif PostgreSQL

```sql
-- Trouver le chemin d'apprentissage vers un concept cible
WITH RECURSIVE pre_requis_chain AS (
    -- Base : le concept cible lui-même
    SELECT source, target, relation, matiere, 0 as depth
    FROM concept_graph
    WHERE user_id IS NULL
      AND target = :concept_cible
      AND relation = 'PRE_REQUIS_DE'

    UNION ALL

    -- Récursion : remonter la chaîne de prérequis
    SELECT cg.source, cg.target, cg.relation, cg.matiere, prc.depth + 1
    FROM concept_graph cg
    JOIN pre_requis_chain prc ON cg.target = prc.source
    WHERE cg.user_id IS NULL
      AND cg.relation = 'PRE_REQUIS_DE'
      AND prc.depth < 10  -- sécurité anti-boucle
)
SELECT DISTINCT source as concept, matiere, depth
FROM pre_requis_chain
ORDER BY depth DESC;
```

### 3.3 Service de recommandation graphe

**Fichier** : `app/modules/epreuves/services/graph_recommendation_service.py`

```python
class GraphRecommendationService:
    """Recommandation basée sur le graphe cognitif."""

    def recommander_parcours(self, user_id: str, limit: int = 10) -> List[dict]:
        """
        Algorithme :
        1. Trouver les lacunes (A_ECHOUE_SUR)
        2. Pour chaque lacune, remonter les prérequis manquants
        3. Proposer les documents les plus bas dans la chaîne (prérequis de base)
        4. Pondérer par la confiance du lien
        """

    def recommander_progression(self, user_id: str, matiere: str) -> List[dict]:
        """
        Propose la prochaine étape logique dans une matière :
        - Concepts maîtrisés → trouver ce qu'ils débloquent → filtrer ce qui est déjà maîtrisé
        """
```

---

## Phase 4 — Extracteur LLM batch (1 jour)

### 4.1 Celery task d'extraction

**Fichier** : `app/modules/memory/jobs/tasks.py`

```python
@celery_app.task(name="memory.tasks.extract_concepts_from_chat", queue="heavy", bind=True, max_retries=2)
def extract_concepts_from_chat_task(self, message_id: int, user_id: str, user_message: str, llm_response: str):
    """Extrait entités et relations d'un échange chat → enrichit le graphe."""
    db = SessionLocal()
    try:
        # Prompt d'extraction
        prompt = f"""
Extrais les concepts éducatifs et leurs relations de cet échange.
Retourne UNIQUEMENT un JSON:

[
  {{"concept": "derivees", "matiere": "Mathematiques", "type": "notion"}},
  {{"source": "derivees", "target": "integrales", "relation": "PRE_REQUIS_DE", "confidence": 0.9}}
]

Message utilisateur: {user_message}
Réponse IA: {llm_response}
"""
        # Appel LLM (OpenRouter)
        llm_client = LLMClient()
        response = await llm_client.generate(...)
        edges = parse_json(response)

        # Insérer dans concept_graph
        svc = ConceptGraphService(db)
        for edge in edges:
            if "source" in edge:
                svc.add_edge(
                    user_id=user_id,
                    source=edge["source"],
                    target=edge["target"],
                    relation=edge.get("relation", "LIEN_FAIBLE"),
                    confidence=edge.get("confidence", 0.5),
                    source_type="chat",
                    matiere=edge.get("matiere"),
                    context=f"Chat message {message_id}",
                )
            else:
                # Simple concept mentionné → EN_COURS
                svc.add_edge(
                    user_id=user_id,
                    source=edge["concept"],
                    target=edge["concept"],
                    relation="EN_COURS",
                    confidence=0.3,
                    source_type="chat",
                    matiere=edge.get("matiere"),
                    context=f"Chat message {message_id}",
                )

        db.commit()
    except Exception as e:
        logger.error(f"Extraction concepts failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()
```

### 4.2 Intégration dans le flow chat existant

**Fichier** : `app/modules/skills/routes/skills.py` (modification)

```python
@router.post("/chat", ...)
async def run_skill_chat(..., background_tasks: BackgroundTasks):
    # ... exécution du skill existante ...

    # Background: extraction des concepts (asynchrone, ne bloque pas la réponse)
    background_tasks.add_task(
        _queue_concept_extraction,
        message_id=result.message_id,
        user_id=str(current_user.id),
        user_message=payload.prompt,
        llm_response=result.content,
    )

    return result
```

### 4.3 Optimisation : cache des concepts extraits

Pour éviter d'extraire les mêmes concepts à chaque message :

```python
# Redis cache: memory:extracted_concepts:{user_id}:{concept}
# TTL: 7 jours
# Si le concept a déjà été extrait récemment → skip l'appel LLM
```

---

## Phase 5 — Intégration Vespa vectoriel (1 jour)

### 5.1 Indexer les chunks de chat dans Vespa

**Fichier** : `app/modules/memory/services/chat_vector_indexer.py`

```python
class ChatVectorIndexer:
    """Indexe les échanges chat dans Vespa pour recherche sémantique sur la mémoire."""

    async def index_message(self, user_id: str, message_id: int, content: str):
        """Indexe un message avec embedding dans Vespa."""
        embedding = await self._embed(content)
        await vespa_client.feed(
            doc_id=f"chat_{user_id}_{message_id}",
            fields={
                "user_id": user_id,
                "content": content,
                "embedding": embedding,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

    async def search_memory(self, user_id: str, query: str, top_k: int = 5) -> List[dict]:
        """Recherche sémantique dans la mémoire personnelle."""
        q_embedding = await self._embed(query)
        results = await vespa_client.query(
            yql=f"""
                SELECT * FROM sources memory_chat
                WHERE user_id = '{user_id}'
                  AND ({target: memory_embedding}nearestNeighbor(embedding, query_embedding))
                LIMIT {top_k}
            """,
            ranking="memory_similarity",
            input_query_embedding=q_embedding,
        )
        return results
```

### 5.2 Schema Vespa

**Fichier** : `app/modules/memory/vespa/memory_chat.sd`

```vespa
schema memory_chat {
    document memory_chat {
        field user_id type string { indexing: attribute | summary }
        field content type string { indexing: summary }
        field embedding type tensor<float>(x[384]) {
            indexing: attribute | index
            attribute {
                distance-metric: angular
            }
        }
        field created_at type string { indexing: attribute }
    }

    rank-profile memory_similarity {
        first-phase {
            expression: closeness(field, embedding)
        }
    }
}
```

---

## Phase 6 — Refonte des services existants (2 jours)

### 6.1 `SearchSuggestionService` → utilise le graphe

```python
# AVANT (dans search_suggestion_service.py)
profile.lacunes  # JSONB dict

# APRÈS
svc = ConceptGraphService(self.db)
lacunes = svc.get_concepts_lacunes(user_id)
# → {"Mathematiques": ["derivees", "integrales"], "Physique": ["mecanique"]}

# Suggestions basées sur les prérequis manquants
parcours = svc.get_parcours_recommande(user_id, "integrales")
# → ["arithmetique", "equations", "fonctions", "limites", "derivees"]
```

### 6.2 `RecommendationEngine` (epreuves) → utilise le graphe

```python
# AVANT
profile.lacunes → recommander_par_lacunes()

# APRÈS
graph_svc = ConceptGraphService(self.db)
lacunes = graph_svc.get_concepts_lacunes(user_id)
parcours = graph_svc.get_parcours_recommande(user_id, lacunes)
# Pour chaque concept du parcours → trouver les documents associés
```

### 6.3 `SkillRecommenderService` → utilise le graphe

```python
# AVANT
if matiere in profile.lacunes:
    return {"skill": "fiche"}

# APRÈS
lacunes = graph_svc.get_concepts_lacunes(user_id)
if matiere in lacunes:
    prerequis_manquants = graph_svc.get_pre_requis(matiere, user_id)
    if prerequis_manquants:
        return {
            "skill": "fiche",
            "raison": f"Tu as des lacunes en {matiere}. Commence par revoir: {', '.join(prerequis_manquants[:3])}"
        }
```

### 6.4 `AssetRecommendationService` (library) → utilise le graphe

```python
# AVANT
user.matiere_faible → lacunes

# APRÈS
lacunes = graph_svc.get_concepts_lacunes(user_id)
# Recherche d'assets par concept (notion) dans le graphe
```

### 6.5 Supprimer les services devenus obsolètes

| Service | Action | Raison |
|---|---|---|
| `LearningProfileService.enregistrer_score_quiz()` | Remplacer par `ConceptGraphService` | Les scores → arêtes MAITRISE/A_ECHOUE_SUR |
| `LearningProfileService.analyser_lacunes_retroactif()` | Remplacer par script de migration | Déjà fait en Phase 2 |
| `AssetRecommendationService._get_user_profile()` | Remplacer par `ConceptGraphService` | Lit `user.matiere_faible` → obsolète |

---

## Phase 7 — Nouvel endpoint "Rapport Cognitif" (1 jour)

**Fichier** : `app/modules/memory/routes/cognitive_report.py`

```python
@router.get("/cognitive-report")
async def get_cognitive_report(user: User = Depends(get_current_user)):
    """
    Rapport cognitif complet :
    - Graphe personnel (lacunes + maîtrises)
    - Parcours recommandé
    - Progression dans chaque matière
    - Concepts à réviser aujourd'hui (SM-2)
    """
    graph_svc = ConceptGraphService(db)

    lacunes = graph_svc.get_concepts_lacunes(user_id)
    maitrises = graph_svc.get_concepts_maitrises(user_id)

    # Pour chaque lacune, calculer le parcours
    parcours = {}
    for matiere, concepts in lacunes.items():
        for concept in concepts:
            prerequis = graph_svc.get_pre_requis(concept)
            parcours[concept] = prerequis

    return {
        "lacunes": lacunes,
        "maitrises": maitrises,
        "parcours_recommande": parcours,
        "prochaines_revisions": await scheduler.obtenir_sections_a_revoir(user_id),
        "statistiques": await stats_svc.calculer_stats_utilisateur(user_id),
    }
```

---

## Ordre d'exécution résumé

| # | Phase | Durée | Bloquant pour |
|---|---|---|---|
| 0 | Nettoyage (supprimer JSONB obsolètes) | 0.5j | — |
| 1 | Schéma `concept_graph` + index | 1j | Tout |
| 1b | Seed manuel prérequis programme | 0.5j | Recommandation |
| 2 | Migration données existantes | 1j | Graph RAG |
| 3 | Services graphe (CRUD + CTE) | 2j | Tout |
| 4 | Extracteur LLM batch (Celery) | 1j | Enrichissement auto |
| 5 | Vespa vectoriel chat memory | 1j | Recherche mémoire |
| 6 | Refonte services existants | 2j | — |
| 7 | Endpoint rapport cognitif | 1j | UX |

**Total** : ~10 jours de dev

---

## Risques & Mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| CTE récursif trop lent sur gros graphe | Moyen | Limiter `depth < 10`, index sur (source, target) |
| Extracteur LLM trop cher | Élevé | Batch Celery, cache Redis, sampling (1 message / 5) |
| Migration casse les données existantes | Élevé | Script idempotent, backup DB avant, test sur staging |
| `concept_graph` devient trop gros | Moyen | Archiver les edges > 90 jours avec `confidence < 0.3` |
