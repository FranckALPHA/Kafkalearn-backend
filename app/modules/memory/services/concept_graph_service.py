"""
services/concept_graph_service.py
=================================
Service principal pour le graphe cognitif.
Opérations CRUD + traversées de graphe via CTE récursifs PostgreSQL.

Remplace progressivement les accès directs à UserLearningProfile.lacunes/forces.
"""
import logging
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.models.concept_graph import RELATION_TYPES

logger = logging.getLogger(__name__)


class ConceptGraphService(MemoryBaseService):
    """Service pour le graphe cognitif : concepts, relations, prérequis."""

    # ─────────────────────────────────────────────────────────────
    # CRUD de base
    # ─────────────────────────────────────────────────────────────

    def add_edge(
        self,
        user_id: Optional[str],
        source: str,
        target: str,
        relation: str,
        confidence: float = 1.0,
        source_type: str = "chat",
        matiere: Optional[str] = None,
        context: Optional[str] = None,
        canonical_name: Optional[str] = None,
    ) -> bool:
        """Ajoute ou met à jour une arête du graphe.

        Args:
            user_id: UUID ou None pour une arête globale.
            source: Concept source.
            target: Concept target.
            relation: Type de relation (PRE_REQUIS_DE, A_ECHOUE_SUR, etc.)
            confidence: Confiance dans le lien (0.0-1.0).
            source_type: Origine (manual, quiz, chat, document_analysis, etc.)
            matiere: Matière associée.
            context: Contexte JSON (ex: {"document_id": 42}).
            canonical_name: Nom canonique pour la déduplication (ex: "derivees").

        Returns:
            True si une nouvelle arête a été créée, False si mise à jour.
        """
        if relation not in RELATION_TYPES:
            raise ValueError(f"Relation invalide: {relation}. Choisir parmi {RELATION_TYPES}")

        confidence = max(0.0, min(1.0, confidence))
        user_uuid = UUID(user_id) if user_id else None
        canon = canonical_name or source

        # Upsert via INSERT ... ON CONFLICT DO UPDATE
        self.db.execute(
            text("""
                INSERT INTO concept_graph (
                    id, user_id, source, target, relation,
                    confidence, source_type, matiere, context, canonical_name,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :user_id, :source, :target, :relation,
                    :confidence, :source_type, :matiere, :context, :canonical_name,
                    NOW(), NOW()
                )
                ON CONFLICT (user_id, source, target, relation)
                DO UPDATE SET
                    confidence = GREATEST(concept_graph.confidence, EXCLUDED.confidence),
                    updated_at = NOW(),
                    context = EXCLUDED.context,
                    canonical_name = COALESCE(EXCLUDED.canonical_name, concept_graph.canonical_name)
            """),
            {
                "user_id": user_uuid,
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": confidence,
                "source_type": source_type,
                "matiere": matiere,
                "context": context,
                "canonical_name": canon,
            },
        )
        self.db.commit()
        return True

    def remove_edge(self, user_id: Optional[str], source: str, target: str, relation: str) -> int:
        """Supprime une arête du graphe.

        Returns:
            Nombre d'arêtes supprimées.
        """
        user_uuid = UUID(user_id) if user_id else None
        result = self.db.execute(
            text("""
                DELETE FROM concept_graph
                WHERE user_id IS NOT DISTINCT FROM :user_id
                  AND source = :source
                  AND target = :target
                  AND relation = :relation
            """),
            {"user_id": user_uuid, "source": source, "target": target, "relation": relation},
        )
        self.db.commit()
        return result.rowcount

    def get_edges(
        self,
        user_id: Optional[str] = None,
        relation: Optional[str] = None,
        matiere: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Récupère les arêtes du graphe avec filtres.

        Si user_id est None, retourne les arêtes globales.
        """
        user_uuid = UUID(user_id) if user_id else None
        conditions = ["user_id IS NOT DISTINCT FROM :user_id"]
        params = {"user_id": user_uuid, "limit": limit}

        if relation:
            conditions.append("relation = :relation")
            params["relation"] = relation
        if matiere:
            conditions.append("matiere = :matiere")
            params["matiere"] = matiere
        if min_confidence > 0:
            conditions.append("confidence >= :min_confidence")
            params["min_confidence"] = min_confidence

        where_clause = " AND ".join(conditions)

        rows = self.db.execute(
            text(f"""
                SELECT id, user_id, source, target, relation,
                       confidence, source_type, matiere, context,
                       created_at, updated_at
                FROM concept_graph
                WHERE {where_clause}
                ORDER BY confidence DESC, created_at DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

        return [dict(row._mapping) for row in rows]

    # ─────────────────────────────────────────────────────────────
    # Requêtes personnelles (lacunes, maîtrises)
    # ─────────────────────────────────────────────────────────────

    def get_concepts_lacunes(self, user_id: str, matiere: Optional[str] = None) -> Dict[str, List[str]]:
        """Retourne les lacunes de l'utilisateur, groupées par matière.

        Format : {"Mathematiques": ["derivees", "integrales"], "Physique": ["mecanique"]}
        """
        user_uuid = UUID(user_id)
        base_query = """
            SELECT matiere, source
            FROM concept_graph
            WHERE user_id = :user_id
              AND relation = 'A_ECHOUE_SUR'
        """
        params = {"user_id": user_uuid}

        if matiere:
            base_query += " AND matiere = :matiere"
            params["matiere"] = matiere

        rows = self.db.execute(text(base_query), params).fetchall()

        result: Dict[str, List[str]] = {}
        for mat, concept in rows:
            if mat:
                result.setdefault(mat, []).append(concept)

        return result

    def get_concepts_maitrises(self, user_id: str) -> Dict[str, float]:
        """Retourne les concepts maîtrisés par l'utilisateur avec leur score.

        Format : {"SVT": 0.9, "Francais": 0.85}
        """
        user_uuid = UUID(user_id)
        rows = self.db.execute(
            text("""
                SELECT source, confidence
                FROM concept_graph
                WHERE user_id = :user_id
                  AND relation = 'MAITRISE'
                ORDER BY confidence DESC
            """),
            {"user_id": user_uuid},
        ).fetchall()

        return {row[0]: row[1] for row in rows}

    def get_concepts_en_cours(self, user_id: str) -> List[str]:
        """Retourne les concepts que l'utilisateur travaille actuellement."""
        user_uuid = UUID(user_id)
        rows = self.db.execute(
            text("""
                SELECT DISTINCT source
                FROM concept_graph
                WHERE user_id = :user_id
                  AND relation = 'EN_COURS'
                ORDER BY source
            """),
            {"user_id": user_uuid},
        ).fetchall()

        return [row[0] for row in rows]

    def get_all_concepts_personnels(self, user_id: str) -> Set[str]:
        """Retourne tous les concepts personnels de l'utilisateur (toutes relations)."""
        user_uuid = UUID(user_id)
        rows = self.db.execute(
            text("""
                SELECT DISTINCT source FROM concept_graph WHERE user_id = :user_id
                UNION
                SELECT DISTINCT target FROM concept_graph WHERE user_id = :user_id
            """),
            {"user_id": user_uuid},
        ).fetchall()

        return {row[0] for row in rows}

    # ─────────────────────────────────────────────────────────────
    # Traversées de graphe (CTE récursifs)
    # ─────────────────────────────────────────────────────────────

    def get_pre_requis(self, concept: str, user_id: Optional[str] = None, max_depth: int = 10) -> List[Dict[str, Any]]:
        """Retourne la chaîne de prérequis pour atteindre un concept.

        Remonte récursivement les PRE_REQUIS_DE depuis le concept cible.
        Combine graphe global + graphe personnel si user_id fourni.

        Args:
            concept: Concept cible (ex: "integrales").
            user_id: UUID de l'utilisateur (optionnel). Si fourni, filtre les
                     prérequis déjà maîtrisés.
            max_depth: Profondeur maximale de récursion (sécurité anti-boucle).

        Returns:
            Liste de dicts : [{"concept": "derivees", "matiere": "Mathematiques", "depth": 0}, ...]
            Trié par depth croissant (prérequis les plus bas en premier).
        """
        # Concepts déjà maîtrisés par l'utilisateur (à exclure des prérequis)
        mastered = set()
        if user_id:
            mastered = set(self.get_concepts_maitrises(user_id).keys())

        # CTE récursif : remonter la chaîne de prérequis
        query = """
            WITH RECURSIVE pre_requis_chain AS (
                -- Base : les prérequis directs du concept cible
                SELECT source, matiere, 0 AS depth
                FROM concept_graph
                WHERE user_id IS NULL
                  AND target = :concept
                  AND relation = 'PRE_REQUIS_DE'

                UNION ALL

                -- Récursion : remonter la chaîne
                SELECT cg.source, cg.matiere, prc.depth + 1
                FROM concept_graph cg
                JOIN pre_requis_chain prc ON cg.target = prc.source
                WHERE cg.user_id IS NULL
                  AND cg.relation = 'PRE_REQUIS_DE'
                  AND prc.depth < :max_depth
            )
            SELECT DISTINCT source AS concept, matiere, depth
            FROM pre_requis_chain
            ORDER BY depth DESC, source
        """

        rows = self.db.execute(
            text(query),
            {"concept": concept, "max_depth": max_depth},
        ).fetchall()

        result = []
        for row in rows:
            concept_name = row[0]
            if concept_name not in mastered:
                result.append({
                    "concept": concept_name,
                    "matiere": row[1],
                    "depth": row[2],
                })

        return result

    def get_parcours_recommande(
        self, user_id: str, concept_cible: str, max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Calcule le parcours d'apprentissage optimal vers un concept cible.

        Algorithme :
        1. Trouver tous les prérequis du concept cible (CTE récursif)
        2. Exclure les concepts déjà maîtrisés
        3. Ordonner par profondeur (prérequis de base d'abord)
        4. Ajouter les lacunes détectées comme priorité

        Returns:
            Liste ordonnée de concepts à travailler.
        """
        # 1. Prérequis du concept cible
        prerequis = self.get_pre_requis(concept_cible, user_id, max_depth)

        # 2. Lacunes de l'utilisateur
        lacunes = self.get_concepts_lacunes(user_id)
        lacune_concepts = set()
        for notions in lacunes.values():
            lacune_concepts.update(notions)

        # 3. Combiner : prérequis + lacunes, ordonnés
        parcours_map: Dict[str, Dict[str, Any]] = {}

        # Ajouter les prérequis (priorité par profondeur)
        for i, prereq in enumerate(prerequis):
            concept = prereq["concept"]
            priority = prereq["depth"]  # Plus profond = plus urgent
            if concept not in parcours_map:
                parcours_map[concept] = {
                    "concept": concept,
                    "matiere": prereq["matiere"],
                    "priority": priority,
                    "est_lacune": concept in lacune_concepts,
                    "est_prerequis": True,
                }
            else:
                # Si déjà présent, marquer comme lacune aussi
                if concept in lacune_concepts:
                    parcours_map[concept]["est_lacune"] = True

        # Ajouter les lacunes qui ne sont pas des prérequis
        for matiere, notions in lacunes.items():
            for notion in notions:
                if notion not in parcours_map:
                    parcours_map[notion] = {
                        "concept": notion,
                        "matiere": matiere,
                        "priority": 999,  # Après les prérequis
                        "est_lacune": True,
                        "est_prerequis": False,
                    }

        # Trier : lacunes d'abord, puis par priority
        parcours = sorted(
            parcours_map.values(),
            key=lambda x: (not x["est_lacune"], x["priority"]),
        )

        return parcours

    def get_concepts_debloques(self, user_id: str, matiere: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retourne les concepts que l'utilisateur peut maintenant aborder.

        Un concept est "déblocable" si tous ses prérequis sont maîtrisés
        et qu'il n'est pas encore maîtrisé lui-même.
        """
        user_uuid = UUID(user_id)
        mastered = set(self.get_concepts_maitrises(user_id).keys())
        personnels = self.get_all_concepts_personnels(user_id)

        query = """
            SELECT DISTINCT cg.target, cg.matiere
            FROM concept_graph cg
            WHERE cg.user_id IS NULL
              AND cg.relation = 'PRE_REQUIS_DE'
        """
        params: Dict[str, Any] = {}

        if matiere:
            query += " AND cg.matiere = :matiere"
            params["matiere"] = matiere

        rows = self.db.execute(text(query), params).fetchall()

        # Pour chaque target, vérifier que TOUS les prérequis sont maîtrisés
        result = []
        checked_targets: Set[str] = set()

        for target, mat in rows:
            if target in checked_targets or target in mastered:
                continue

            # Vérifier que tous les prérequis de ce target sont maîtrisés
            prereqs = self.db.execute(
                text("""
                    SELECT source FROM concept_graph
                    WHERE user_id IS NULL
                      AND target = :target
                      AND relation = 'PRE_REQUIS_DE'
                """),
                {"target": target},
            ).fetchall()

            prereq_concepts = {row[0] for row in prereqs}
            all_mastered = prereq_concepts.issubset(mastered) and len(prereq_concepts) > 0

            if all_mastered:
                result.append({
                    "concept": target,
                    "matiere": mat,
                    "prerequis_satisfaits": list(prereq_concepts),
                })
                checked_targets.add(target)

        return result

    # ─────────────────────────────────────────────────────────────
    # Statistiques
    # ─────────────────────────────────────────────────────────────

    def get_statistiques_personnelles(self, user_id: str) -> Dict[str, Any]:
        """Statistiques cognitives personnelles."""
        user_uuid = UUID(user_id)

        rows = self.db.execute(
            text("""
                SELECT relation, COUNT(DISTINCT source) as nb_concepts
                FROM concept_graph
                WHERE user_id = :user_id
                GROUP BY relation
            """),
            {"user_id": user_uuid},
        ).fetchall()

        stats = {row[0]: row[1] for row in rows}

        # Matière la plus travaillée
        top_matiere = self.db.execute(
            text("""
                SELECT matiere, COUNT(DISTINCT source) as nb
                FROM concept_graph
                WHERE user_id = :user_id
                  AND matiere IS NOT NULL
                GROUP BY matiere
                ORDER BY nb DESC
                LIMIT 1
            """),
            {"user_id": user_uuid},
        ).fetchone()

        return {
            "nb_lacunes": stats.get("A_ECHOUE_SUR", 0),
            "nb_maitrises": stats.get("MAITRISE", 0),
            "nb_en_cours": stats.get("EN_COURS", 0),
            "total_concepts": sum(stats.values()),
            "matiere_principale": top_matiere[0] if top_matiere else None,
        }
