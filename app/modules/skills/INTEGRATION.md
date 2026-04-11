# Contrats d'intégration — Module Skills

## ← Appel depuis `search` (RAG)

```python
# Avant chaque exécution de skill si avec_rag=true
chunks = await SearchOrchestrator(db).recherche_hybride(
    texte=prompt,
    filtres={"matiere": matiere, "niveau": niveau},
    top_k=6,
    source_module='skills'  # ← FLAG CRITIQUE: pas de logging search_logs
)