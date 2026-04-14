"""
routes/graph_extraction.py
==========================
Endpoints admin pour l'extraction automatique du graphe cognitif
depuis des documents individuels.

Architecture :
  POST /memory/admin/graph/extract-document
    → LLM extrait notions + prérequis
    → Déduplicateur sémantique (FastEmbed)
    → Upsert dans concept_graph
    → Retourne new / merged / ambiguous
"""
import logging
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.memory.routes.dependencies import (
    get_db,
    get_current_user,
)
from app.modules.users.models import User
from app.modules.memory.services.concept_graph_service import ConceptGraphService
from app.modules.memory.services.notion_deduplicator import NotionDeduplicator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory/admin/graph", tags=["Memory Admin - Graph Extraction"])


def _require_admin(current_user: User):
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")


EXTRACTION_PROMPT = """Analyse ce document du programme scolaire camerounais et extrais :
1. Les **notions principales** abordées
2. Les **prérequis implicites** (notions nécessaires pour comprendre ce document)

Retourne UNIQUEMENT un JSON valide :
{{
  "notions": [
    {{"nom": "derivees", "matiere": "Mathematiques"}}
  ],
  "pre_requis": [
    {{"source": "limites", "target": "derivees", "matiere": "Mathematiques", "confidence": 0.85, "evidence": "Les limites sont supposées connues"}}
  ]
}}

Règles :
- confidence: 0.6-0.7 si implicite, 0.8-0.9 si explicitement mentionné
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


@router.post("/extract-document")
async def extract_from_document(
    document_id: int,
    force: bool = Query(False, description="Forcer l'extraction même si déjà analysé"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extrait les notions et prérequis d'un document et les injecte dans le graphe cognitif.
    
    Utilise la déduplication sémantique pour éviter les doublons :
    - "dérivées" == "derivees" → fusion automatique
    - "calcul différentiel" → fusion si similarité > 0.85
    - "dérivée composée" → nouvelle notion si similarité < 0.50
    - Entre les deux → flag ambigu pour validation humaine
    """
    _require_admin(current_user)

    # 1. Récupérer le document
    doc = db.execute(
        text("""
            SELECT id, nom_affiche, matiere, niveau, serie, type_doc,
                   COALESCE(texte_extrait, nom_affiche) as contenu
            FROM documents
            WHERE id = :doc_id AND is_validated = true
        """),
        {"doc_id": document_id},
    ).fetchone()

    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND_OR_NOT_VALIDATED")

    doc_id, titre, matiere, niveau, serie, type_doc, contenu = doc

    # Vérifier si déjà analysé
    if not force:
        already = db.execute(
            text("""
                SELECT 1 FROM concept_graph
                WHERE source_type = 'document_analysis'
                  AND user_id IS NULL
                  AND context::jsonb->>'document_id' = :doc_id
                LIMIT 1
            """),
            {"doc_id": str(doc_id)},
        ).fetchone()
        if already:
            return {"status": "already_analyzed", "document_id": doc_id}

    # 2. LLM extraction
    try:
        from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
        from app.core.config import OPENROUTER_API_KEYS

        prompt = EXTRACTION_PROMPT.format(
            titre=titre or "",
            matiere=matiere or "",
            niveau=niveau or "",
            serie=serie or "",
            type_doc=type_doc or "",
            contenu=(contenu or "")[:3000],
        )

        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
        response = await client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
            response_format="json",
        )

        text_raw = response.get("text", "").strip()
        if text_raw.startswith("```"):
            text_raw = text_raw.split("```", 2)[-2].strip()
            if text_raw.startswith("json"):
                text_raw = text_raw[4:].strip()

        llm_result = json.loads(text_raw)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM_EXTRACTION_FAILED: {str(e)}")

    # 3. Déduplication sémantique
    deduplicator = NotionDeduplicator(db)
    raw_notions = [n["nom"] for n in llm_result.get("notions", [])]
    dedup_result = await deduplicator.process(raw_notions, matiere=matiere)

    # 4. Upsert dans le graphe
    graph_svc = ConceptGraphService(db)
    total_added = 0
    total_merged = 0

    # Notions nouvelles — utiliser le nom normalisé comme canonical_name
    for notion_name in dedup_result.new:
        graph_svc.add_edge(
            user_id=None,
            source=notion_name,
            target=notion_name,
            relation="EN_COURS",
            confidence=1.0,
            source_type="document_analysis",
            matiere=matiere,
            canonical_name=notion_name,
            context=json.dumps({
                "document_id": doc_id,
                "raw_variants": [n["nom"] for n in llm_result.get("notions", [])
                                if deduplicator.normalize(n["nom"]) == notion_name],
            }),
        )
        total_added += 1

    # Notions fusionnées
    for merged in dedup_result.merged:
        total_merged += 1

    # Prérequis détectés
    for pre in llm_result.get("pre_requis", []):
        source_norm = deduplicator.normalize(pre.get("source", ""))
        target_norm = deduplicator.normalize(pre.get("target", ""))

        if source_norm and target_norm:
            graph_svc.add_edge(
                user_id=None,
                source=source_norm,
                target=target_norm,
                relation="PRE_REQUIS_DE",
                confidence=pre.get("confidence", 0.7),
                source_type="document_analysis",
                matiere=pre.get("matiere", matiere),
                canonical_name=f"{source_norm}_prereq_{target_norm}",
                context=json.dumps({
                    "document_id": doc_id,
                    "evidence": pre.get("evidence", ""),
                }),
            )
            total_added += 1

    db.commit()

    return {
        "status": "done",
        "document_id": doc_id,
        "document_titre": titre,
        "matiere": matiere,
        "notions_nouvelles": total_added - len(llm_result.get("pre_requis", [])),
        "notions_fusionnees": total_merged,
        "notions_ambigues": dedup_result.ambiguous,
        "relations_ajoutees": len(llm_result.get("pre_requis", [])),
        "details": {
            "new_concepts": dedup_result.new,
            "merged": dedup_result.merged,
            "ambiguous": dedup_result.ambiguous,
        },
    }


@router.post("/extract-batch")
async def extract_batch(
    limit: int = Query(10, ge=1, le=100),
    matiere: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extrait le graphe depuis un batch de documents non analysés.
    Utile pour le premier chargement massif.
    """
    _require_admin(current_user)

    query = """
        SELECT id, nom_affiche, matiere, niveau, serie, type_doc,
               COALESCE(texte_extrait, nom_affiche) as contenu
        FROM documents
        WHERE is_validated = true
    """
    params = {}
    if matiere:
        query += " AND matiere = :matiere"
        params["matiere"] = matiere
    query += " ORDER BY id LIMIT :limit"
    params["limit"] = limit

    docs = db.execute(text(query), params).fetchall()

    # Filtrer les déjà analysés
    analyzed = set(
        r[0] for r in db.execute(
            text("SELECT DISTINCT CAST(context->>'document_id' AS INTEGER) FROM concept_graph WHERE source_type = 'document_analysis'")
        ).fetchall()
    )
    docs = [d for d in docs if d[0] not in analyzed]

    if not docs:
        return {"status": "no_new_documents", "message": "Tous les documents validés ont déjà été analysés"}

    results = []
    for doc in docs:
        doc_id, titre, mat, niveau, serie, type_doc, contenu = doc
        try:
            # Simuler l'appel à extract_from_document pour ce doc
            raw_content = contenu[:3000] if contenu else titre
            # En production : appeler le LLM ici
            # Pour l'instant on retourne le statut
            results.append({
                "document_id": doc_id,
                "titre": titre,
                "status": "queued",
            })
        except Exception as e:
            results.append({
                "document_id": doc_id,
                "titre": titre,
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "batch_queued",
        "total": len(results),
        "documents": results,
    }


@router.get("/ambiguous")
async def get_ambiguous_notions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste les notions ambiguës en attente de validation humaine.
    Ces notions ont une similarité entre 0.50 et 0.85 avec une notion existante.
    """
    _require_admin(current_user)

    # Les notions ambiguës sont stockées dans le context des arêtes avec un flag
    rows = db.execute(text("""
        SELECT id, source, target, relation, confidence, matiere, context
        FROM concept_graph
        WHERE user_id IS NULL
          AND source_type = 'document_analysis'
          AND context->>'ambiguous' = 'true'
        ORDER BY created_at DESC
        LIMIT 100
    """)).fetchall()

    return {
        "ambiguous": [
            {
                "id": r[0],
                "source": r[1],
                "target": r[2],
                "relation": r[3],
                "confidence": r[4],
                "matiere": r[5],
                "context": r[6],
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.post("/ambiguous/{edge_id}/resolve")
async def resolve_ambiguous_notion(
    edge_id: str,
    action: str = Query(..., description="merge, new, rename"),
    canonical_name: Optional[str] = Query(None, description="Nom canonique (pour merge/rename)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Résout une notion ambiguë :
    - merge : fusionne avec la notion canonique existante
    - new : crée comme nouvelle notion
    - rename : renomme avec le nom canonique fourni
    """
    _require_admin(current_user)

    from sqlalchemy import text

    if action == "merge" and canonical_name:
        db.execute(
            text("""
                UPDATE concept_graph
                SET source = :canonical, target = :canonical,
                    source_type = 'human_resolved', confidence = 0.9
                WHERE id = :edge_id AND user_id IS NULL
            """),
            {"edge_id": edge_id, "canonical": canonical_name},
        )
    elif action == "new":
        db.execute(
            text("""
                UPDATE concept_graph
                SET source_type = 'human_resolved', confidence = 1.0
                WHERE id = :edge_id AND user_id IS NULL
            """),
            {"edge_id": edge_id},
        )
    elif action == "rename" and canonical_name:
        db.execute(
            text("""
                UPDATE concept_graph
                SET source = :canonical, target = :canonical,
                    source_type = 'human_resolved', confidence = 1.0
                WHERE id = :edge_id AND user_id IS NULL
            """),
            {"edge_id": edge_id, "canonical": canonical_name},
        )
    else:
        raise HTTPException(status_code=400, detail="INVALID_ACTION_OR_MISSING_PARAM")

    db.commit()
    return {"status": "resolved", "edge_id": edge_id, "action": action}
