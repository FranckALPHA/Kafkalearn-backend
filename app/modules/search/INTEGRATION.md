# Contrats d'intégration — Module Search

Ce document décrit les contrats d'appel entre le module `search` et les autres modules.

---

## → Appel vers `users.LearningProfileService`

```python
# Après chaque recherche réussie (background task Celery)
from app.modules.users.services.learning_profile_service import LearningProfileService

LearningProfileService(db).ajouter_recherche(
    user_id: str,
    requete: str,
    intention: Literal['explication', 'entrainement', 'general'],
    matiere: Optional[str],
    notion: Optional[str]  # extraite par NLP si possible
)
```

**Effet** : Enrichit `historique_recherches`, `matieres_frequentes`, détecte lacunes potentielles.

**Quand** : Via la tâche Celery `search.tasks.enrich_profile_after_search` (non bloquant).

---

## → Appel vers `users.ReferralService`

```python
# Si première recherche d'un filleul (parrainé)
from app.modules.users.services.referral_service import ReferralService

if user.referred_by_id and db.query(SearchLog).filter_by(user_id=user.id).count() == 1:
    ReferralService(db).marquer_filleul_actif(user_id=str(user.id))
```

**Effet** : Débloque les bonus de parrainage pour le parrain.

**Quand** : À implémenter dans le service d'onboarding ou lors de la première recherche.

---

## ← Appel depuis `skills` ou autres modules

```python
# Recherche interne pour construire un contexte RAG
# NE CRÉE PAS de search_logs (flag source_module='skills')
from app.modules.search.services.retriever_service import RetrieverService

result = await RetrieverService(db).recherche_hybride(
    texte=query,
    filtres=filtres,
    source_module='skills'  # ← important: pas de logging utilisateur
)
```

**Différence** : 
- Pas de création de `search_logs`
- Pas d'enrichissement de profil
- Pas de consommation de quota IA

---

## ← Appel depuis `ingest` (indexation)

```python
# Après indexation d'un nouveau document
from app.modules.search.services.meilisearch_service import MeilisearchService
from app.modules.search.services.filter_cache_service import FilterCacheService

# Indexer dans Meilisearch
MeilisearchService(db).index_document({
    "document_id": "doc_123",
    "titre": "Épreuve Math 2024",
    "contenu": "...",
    "matiere": "Mathématiques",
    "niveau": "Terminale",
    "annee": 2024,
})

# Invalider le cache des filtres
FilterCacheService(db, redis).invalidate_single_filter("matieres")
```

**Effet** : Le document est searchable et les filtres UI sont mis à jour.

---

## → Appel vers `notifications.NotificationService`

```python
# Si lacune détectée 3x sur la même notion sans résolution
from app.modules.notifications.services.notification_service import NotificationService

if lacune_recurrence_count >= 3:
    await NotificationService(db).send_to_user(
        user_id=user_id,
        title="On a détecté une lacune 🎯",
        body=f"Tu bloques sur {notion} en {matiere}. Lance une fiche de révision !",
        data={"type": "lacune_detectee", "matiere": matiere, "notion": notion}
    )
```

**Quand** : À implémenter dans une tâche Celery d'analyse des lacunes (cron).

---

## → Appel vers `payment.QuotaService`

```python
# Vérification quota avant génération IA (déjà dans SearchOrchestrator)
from app.modules.search.utils.quota_manager import QuotaManager

quota_manager = QuotaManager(redis)
quota_ok = await quota_manager.check_and_consume(
    user_id=str(user.id),
    plan=user.plan_effectif
)
```

**Effet** : Consomme 1 unité de quota IA si disponible.

---

## 📡 Endpoints exposés

### Pour le frontend

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `POST` | `/api/v1/search/rechercher` | Recherche hybride avec IA | ✅ |
| `POST` | `/api/v1/search/lite` | Recherche textuelle rapide | ✅ |
| `GET` | `/api/v1/search/suggestions` | Suggestions personnalisées | ✅ |
| `POST` | `/api/v1/search/{id}/feedback` | Feedback sur recherche | ✅ |
| `GET` | `/api/v1/search/historique` | Historique utilisateur | ✅ |
| `DELETE` | `/api/v1/search/historique` | Supprimer historique | ✅ |

### Pour le SuperAdmin

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `GET` | `/api/v1/admin/search/analytics` | Stats globales | ✅ Admin |
| `GET` | `/api/v1/admin/search/popular-queries` | Requêtes populaires | ✅ Admin |

---

## 🔧 Configuration requise

### Variables d'environnement

```env
# Vespa (recherche vectorielle)
VESPA_URL=http://localhost:18080
VESPA_CONFIG_URL=http://localhost:19071

# Meilisearch (recherche textuelle)
MEILI_URL=http://localhost:17700
MEILI_MASTER_KEY=kafkalearn_master_key

# Redis (cache, rate limiting, sessions)
REDIS_URL=redis://localhost:16379/0
```

### Index Meilisearch requis

L'index `epreuves` doit être créé avec les paramètres suivants :

```python
client.index("epreuves").update_settings({
    "searchableAttributes": ["titre", "contenu", "matiere", "niveau"],
    "filterableAttributes": ["matiere", "niveau", "annee", "serie"],
    "sortableAttributes": ["annee", "matiere"],
    "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
})
```

### Vespa

Le schéma Vespa doit être déployé via `deploy_vespa.py` (à la racine du projet).

---

## ⚠️ Points d'attention

1. **UUID vs String** : Les `user_id` sont des UUID dans la BDD. Toujours convertir avec `UUID(user_id)` avant les requêtes.
2. **Rate Limiting** : Le rate limiter est basé sur IP + endpoint. Configurer les seuils selon le trafic attendu.
3. **Celery Tasks** : Les tâches background ne doivent pas bloquer la réponse HTTP. Toujours utiliser `.delay()`.
4. **Quotas IA** : Vérifier le quota **avant** de lancer la recherche hybride si `avec_ia=True`.
5. **Cache Filtres** : TTL de 2h par défaut. Invalider manuellement après indexation de nouveaux documents.

---

## 🧪 Tests recommandés

```python
# Test recherche hybride
async def test_recherche_hybride():
    response = await client.post("/api/v1/search/rechercher", json={
        "texte": "dérivée d'une fonction",
        "avec_ia": True,
        "top_k": 5,
    })
    assert response.status_code == 200
    assert "chunks" in response.json()

# Test rate limiting
async def test_rate_limit_search():
    for _ in range(15):
        response = await client.post("/api/v1/search/rechercher", json={...})
    assert response.status_code == 429

# Test feedback
async def test_feedback():
    response = await client.post(f"/api/v1/search/1/feedback", json={
        "rating": 5,
        "commentaire": "Super réponse !"
    })
    assert response.status_code == 200
```

---

**Dernière mise à jour** : 2026-04-11  
**Mainteneur** : Équipe KafkaLearn
