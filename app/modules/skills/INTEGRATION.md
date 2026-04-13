# Contrats d'intégration — Module Skills

Ce document décrit les contrats d'appel entre le module `skills` et les autres modules.

---

## ← Appel depuis `search` (RAG)

```python
# Avant chaque exécution de skill si avec_rag=true
from app.modules.search.services.search_orchestrator import SearchOrchestrator

chunks = await SearchOrchestrator(db).recherche_hybride(
    texte=prompt,
    filtres={"matiere": matiere, "niveau": niveau},
    top_k=6,
    source_module='skills'  # ← FLAG CRITIQUE: pas de logging search_logs
)
```

**Différence** : `source_module='skills'` désactive la création de `search_logs` et l'enrichissement de profil via search.

---

## → Appel vers `users.LearningProfileService`

```python
# Après chaque exécution de skill (background task Celery)
from app.modules.users.services.learning_profile_service import LearningProfileService

LearningProfileService(db).enregistrer_skill_usage(
    user_id=user_id,
    skill_type=skill_type,  # "quiz", "fiche", etc.
    matiere=matiere,
    succes=result.success
)

# Après correction de quiz avec score
if skill_type == "quiz" and score is not None:
    LearningProfileService(db).enregistrer_score_quiz(
        user_id=user_id,
        matiere=matiere,
        score=score,
    )
```

**Effet** : Mise à jour de `skills_utilises`, `score_par_matiere`, détection lacunes.

**Quand** : Via les tâches Celery `skills.tasks.enrich_profile_after_skill`.

---

## → Appel vers `notifications.NotificationService` ✅ IMPLÉMENTÉ

```python
# Quand une génération PDF longue est terminée (dans generate_fiche_pdf_task)
from app.modules.notifications.services.notification_service import NotificationService

NotificationService(notif_db).send_to_user(
    user_id=user_id,
    title="📄 Ta fiche est prête !",
    body=f"{titre} est disponible dans ta bibliothèque.",
    data={
        "type": "skill_ready",
        "file_url": file_url,
        "skill_type": skill_type
    }
)
```

**Où** : Dans `skills/jobs/tasks.py` → `generate_fiche_pdf_task`  
**Quand** : Après génération PDF réussie.

---

## 📡 Endpoints exposés

### Pour le frontend

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `POST` | `/api/v1/skills/run` | Exécuter un skill | ✅ |
| `POST` | `/api/v1/skills/quiz/{id}/soumettre` | Soumettre réponses quiz | ✅ |
| `GET` | `/api/v1/skills/liste` | Catalogue des skills | ✅ |
| `POST` | `/api/v1/skills/detecter` | Détecter intention | ✅ |
| `GET` | `/api/v1/skills/chat/sessions` | Liste sessions chat | ✅ |
| `POST` | `/api/v1/skills/chat/sessions` | Créer session | ✅ |
| `GET` | `/api/v1/skills/chat/sessions/{id}` | Détails session | ✅ |
| `GET` | `/api/v1/skills/chat/sessions/{id}/messages` | Messages session | ✅ |
| `PUT` | `/api/v1/skills/chat/sessions/{id}/title` | Renommer session | ✅ |
| `POST` | `/api/v1/skills/chat/sessions/{id}/pin` | Épingler session | ✅ |
| `POST` | `/api/v1/skills/chat/sessions/{id}/archive` | Archiver session | ✅ |
| `DELETE` | `/api/v1/skills/chat/sessions/{id}` | Supprimer session | ✅ |

### Pour le SuperAdmin

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `GET` | `/api/v1/admin/skills/analytics` | Stats globales | ✅ Admin |
| `GET` | `/api/v1/admin/skills/top-skills` | Skills populaires | ✅ Admin |
| `GET` | `/api/v1/admin/skills/top-matieres` | Matières pratiquées | ✅ Admin |

---

## ⚠️ Points d'attention

1. **Idempotency** : Toutes les requêtes `/run` sont dédupliquées via Redis (TTL 60s).
2. **Rate Limiting** : 10 req/min pour `/run`, 30 req/min pour le chat.
3. **RAG** : Le flag `source_module='skills'` est critique pour ne pas polluer les analytics search.
4. **Quotas** : Vérifier le quota IA avant l'exécution si le skill consomme des tokens.
5. **UUID** : Les `session_id` sont des UUID. Toujours convertir avec `UUID(session_id)`.

---

**Dernière mise à jour** : 2026-04-11  
**Mainteneur** : Équipe KafkaLearn
