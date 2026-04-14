"""
seed/global_graph_extractor.py
==============================
Extracteur global du graphe cognitif — analyse les documents existants
pour découvrir automatiquement les notions et leurs prérequis.

Remplace le seed manuel par une détection LLM automatique.

Usage :
    uv run python -m app.modules.memory.seed.global_graph_extractor [--force] [--batch-size 50]
"""
import logging
import json
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Prompt template pour l'extraction de prérequis depuis un document
EXTRACTION_PROMPT = """Tu es un expert en analyse de programmes scolaires camerounais.
Analyse ce document d'épreuve/cours et extrais :
1. Les **notions principales** abordées (avec profondeur 1-5)
2. Les **prérequis implicites** (notions nécessaires pour comprendre ce document)

Retourne UNIQUEMENT un JSON valide :
{
  "notions": [
    {"nom": "derivees", "profondeur": 4, "matiere": "Mathematiques"}
  ],
  "pre_requis": [
    {"source": "limites", "target": "derivees", "confidence": 0.85, "evidence": "Les limites sont supposées connues pour introduire les dérivées"}
  ]
}

Règles :
- profondeur: 1 (très basique) → 5 (avancé/terminale)
- confidence: 0.6-0.7 si déduit du contexte, 0.8-0.9 si mentionné explicitement
- source = notion prérequise, target = notion du document
- Ne retourne que des relations pertinentes pour le programme camerounais

Document :
Titre: {titre}
Matière: {matiere}
Niveau: {niveau}
Série: {serie}
Type: {type_doc}
Contenu: {contenu}
"""


def extract_from_document(doc_data: Dict[str, Any], llm_client) -> Dict[str, Any]:
    """Extrait notions et prérequis d'un seul document via LLM."""
    prompt = EXTRACTION_PROMPT.format(
        titre=doc_data.get("titre", ""),
        matiere=doc_data.get("matiere", ""),
        niveau=doc_data.get("niveau", ""),
        serie=doc_data.get("serie", ""),
        type_doc=doc_data.get("type_doc", ""),
        contenu=doc_data.get("contenu", "")[:3000],  # Limiter le contexte
    )

    response = llm_client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1500,
        response_format="json",
    )

    text = response.get("text", "").strip()
    # Nettoyer les balises markdown
    if text.startswith("```"):
        text = text.split("```", 2)[-2].strip()
        if text.startswith("json"):
            text = text[4:].strip()

    result = json.loads(text)
    return result


def run(force: bool = False, batch_size: int = 50):
    """
    Analyse les documents et construit le graphe cognitif global.

    Args:
        force: Si True, supprime les arêtes globales existantes avant de reseed.
        batch_size: Nombre de documents à traiter par batch.
    """
    from app.core.config import DATABASE_URL
    from app.modules.memory.services.concept_graph_service import ConceptGraphService
    from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
    from app.core.config import OPENROUTER_API_KEYS
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        if force:
            cur.execute("DELETE FROM concept_graph WHERE user_id IS NULL AND source_type = 'document_analysis'")
            deleted = cur.rowcount
            conn.commit()
            logger.info(f"Supprimé {deleted} arêtes globales existantes")
            print(f"🗑️  Supprimé {deleted} arêtes globales existantes")

        # Récupérer les documents à analyser
        cur.execute("""
            SELECT id, nom_affiche, matiere, niveau, serie, type_doc,
                   COALESCE(texte_extrait, nom_affiche) as contenu
            FROM documents
            WHERE is_validated = true
            ORDER BY id
            LIMIT %s
        """, (batch_size,))
        docs = cur.fetchall()

        if not docs:
            print("⚠️  Aucun document validé trouvé dans la base")
            return

        print(f"📚 {len(docs)} documents à analyser...")

        # Initialiser le client LLM
        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)

        total_notions = 0
        total_pre_requis = 0
        total_docs_analyzed = 0
        errors = 0

        for doc in docs:
            doc_id, titre, matiere, niveau, serie, type_doc, contenu = doc

            # Vérifier si déjà analysé
            cur.execute(
                "SELECT 1 FROM concept_graph WHERE source_type = 'document_analysis' "
                "AND user_id IS NULL AND context->>'document_id' = %s LIMIT 1",
                (str(doc_id),)
            )
            if cur.fetchone():
                continue

            doc_data = {
                "titre": titre or "",
                "matiere": matiere or "",
                "niveau": niveau or "",
                "serie": serie or "",
                "type_doc": type_doc or "",
                "contenu": contenu or "",
            }

            try:
                result = extract_from_document(doc_data, client)

                # Insérer les notions
                for notion in result.get("notions", []):
                    cur.execute("""
                        INSERT INTO concept_graph (id, user_id, source, target, relation,
                            confidence, source_type, matiere, context, created_at, updated_at)
                        VALUES (gen_random_uuid(), NULL, %s, %s, 'EN_COURS', 1.0, 'document_analysis', %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, source, target, relation) DO NOTHING
                    """, (
                        notion["nom"], notion["nom"],
                        notion.get("matiere", matiere),
                        json.dumps({"document_id": doc_id, "profondeur": notion.get("profondeur"), "titre": titre}),
                    ))
                    total_notions += 1

                # Insérer les prérequis
                for pre in result.get("pre_requis", []):
                    cur.execute("""
                        INSERT INTO concept_graph (id, user_id, source, target, relation,
                            confidence, source_type, matiere, context, created_at, updated_at)
                        VALUES (gen_random_uuid(), NULL, %s, %s, 'PRE_REQUIS_DE', %s, 'document_analysis', %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, source, target, relation) DO NOTHING
                    """, (
                        pre["source"], pre["target"],
                        pre.get("confidence", 0.7),
                        pre.get("matiere", matiere),
                        json.dumps({
                            "document_id": doc_id,
                            "evidence": pre.get("evidence", ""),
                            "titre": titre,
                        }),
                    ))
                    total_pre_requis += 1

                total_docs_analyzed += 1
                conn.commit()
                print(f"  ✅ {titre[:40]}: {len(result.get('notions', []))} notions, {len(result.get('pre_requis', []))} prérequis")

            except Exception as e:
                errors += 1
                logger.error(f"Erreur analyse document {doc_id}: {e}")
                continue

        print(f"\n📊 Résumé:")
        print(f"   Documents analysés : {total_docs_analyzed}")
        print(f"   Notions extraites  : {total_notions}")
        print(f"   Prérequis détectés : {total_pre_requis}")
        print(f"   Erreurs            : {errors}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur globale : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    batch_size = 50
    for arg in sys.argv:
        if arg.startswith("--batch-size="):
            batch_size = int(arg.split("=")[1])
    run(force=force, batch_size=batch_size)
