# Contrats d'intégration — Module Epreuves

## ← Appel depuis `search` (RAG)

```python
# Lecture chunks pour contexte RAG
chunks = db.query(DocumentChunk).filter(
    DocumentChunk.doc_id == doc_id,
    DocumentChunk.is_embedded == True
).order_by(DocumentChunk.chunk_idx).limit(10).all()

# Après recherche réussie : incrément usage
from app.modules.epreuves.jobs.tasks import increment_document_stat_task
increment_document_stat_task.delay(doc_id=chunk.doc_id, stat_field="nb_tentatives_ia")
```

## ← Appel depuis `skills`

```python
# Lecture métadonnées et texte pour contexte skill
from app.modules.epreuves.services.document_service import DocumentService
doc = await DocumentService(db).recuperer_par_id(doc_id)
contexte = {
    "titre": doc.nom_affiche,
    "matiere": doc.matiere,
    "texte": doc.texte_extrait[:2000] if doc.texte_extrait else ""
}

# Après génération : incrément usage IA
increment_document_stat_task.delay(doc_id=doc_id, stat_field="nb_tentatives_ia")
```

## → Appel vers `users.LearningProfileService`

```python
# Après téléchargement ou vue significative
await LearningProfileService(db).enregistrer_activite(
    user_id=user_id,
    activity_type="view_epreuve" if source == "view" else "download_epreuve",
    item_id=str(doc_id),
    item_name=doc.nom_affiche,
    matiere=doc.matiere,
    source_module="epreuves"
)
```

## 📡 Endpoints exposés

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `GET` | `/api/v1/epreuves/` | Liste documents avec filtres | Public |
| `GET` | `/api/v1/epreuves/{id}` | Détail document | Optionnel |
| `GET` | `/api/v1/epreuves/{id}/download` | Télécharger PDF | ✅ Access+ |
| `GET` | `/api/v1/epreuves/trending` | Documents populaires | Public |
| `GET` | `/api/v1/epreuves/recommandes` | Recommandations perso | ✅ |
| `GET` | `/api/v1/epreuves/filtres` | Filtres disponibles | Public |
| `GET` | `/api/v1/epreuves/{id}/stats` | Stats document | Public |
| `POST` | `/api/v1/epreuves/upload` | Upload document | ✅ Admin |
| `GET/POST/DELETE` | `/api/v1/epreuves/playlists/*` | CRUD playlists | ✅ |
| `GET` | `/api/v1/admin/epreuves/stats` | Stats globales | ✅ Admin |
| `POST` | `/api/v1/admin/epreuves/ingest/{id}` | Lancer ingestion | ✅ Admin |
| `POST` | `/api/v1/admin/epreuves/invalidate-cache` | Invalider cache filtres | ✅ Admin |
| `GET` | `/api/v1/admin/epreuves/pending-ingestion` | Documents en attente | ✅ Admin |
