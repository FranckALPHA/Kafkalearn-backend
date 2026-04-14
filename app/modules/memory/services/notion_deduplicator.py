"""
services/notion_deduplicator.py
===============================
Déduplication sémantique des notions extraites par le LLM.
Résout : "dérivées" == "derivees" == "calcul différentiel" → canonical: "derivees"

Architecture :
  1. Normalisation (lowercase, accents, trim, slug)
  2. Embedding (FastEmbed local)
  3. Similarité cosinus contre les notions existantes
  4. Classification :
     - score >= 0.85 → FUSION (même notion, variante orthographique/synonyme)
     - score < 0.50  → NOUVELLE notion
     - entre les deux → AMBIGUË (validation humaine)
"""
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationResult:
    """Résultat de la déduplication."""
    new: List[str] = field(default_factory=list)           # Nouvelles notions
    merged: List[Dict[str, Any]] = field(default_factory=list)  # Fusions avec existantes
    ambiguous: List[Dict[str, Any]] = field(default_factory=list)  # À valider
    relations: List[Dict[str, Any]] = field(default_factory=list)  # Relations extraites


MERGE_THRESHOLD = 0.85
NEW_THRESHOLD = 0.50


class NotionDeduplicator:
    """Déduplicateur sémantique de notions cognitives."""

    def __init__(self, db, embedding_model=None):
        self.db = db
        self._embedding_model = embedding_model

    # ─────────────────────────────────────────────────────────────
    # Normalisation
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def normalize(text: str) -> str:
        """Normalise une notion : lowercase, sans accents, slug-like."""
        if not text:
            return ""
        # Lowercase
        text = text.lower().strip()
        # Supprimer les accents
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        # Remplacer espaces par underscores, garder alphanumérique
        text = "".join(c if c.isalnum() or c == "_" else "_" for c in text)
        # Nettoyer les underscores multiples
        while "__" in text:
            text = text.replace("__", "_")
        text = text.strip("_")
        return text

    # ─────────────────────────────────────────────────────────────
    # Embedding
    # ─────────────────────────────────────────────────────────────

    def _get_model(self):
        """Lazy-load du modèle d'embedding."""
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
                self._embedding_model = TextEmbedding(
                    model_name="BAAI/bge-small-en-v1.5"
                )
            except ImportError:
                logger.warning("FastEmbed non disponible, fallback sur similarité texte")
                self._embedding_model = "text_fallback"
        return self._embedding_model

    def _embed(self, text: str) -> List[float]:
        """Calcule l'embedding d'un texte."""
        model = self._get_model()
        if model == "text_fallback":
            # Fallback : hash simple (moins précis mais fonctionne sans modèle)
            import hashlib
            h = hashlib.sha256(text.encode()).hexdigest()
            return [int(h[i:i+2], 16) / 255.0 for i in range(0, 64, 2)]

        embeddings = list(model.embed([text]))
        return embeddings[0].tolist()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calcule la similarité cosinus entre deux vecteurs."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    # ─────────────────────────────────────────────────────────────
    # Chargement des notions existantes
    # ─────────────────────────────────────────────────────────────

    def _load_existing_notions(self, matiere: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Charge toutes les notions existantes du graphe global (user_id IS NULL).
        Utilise canonical_name si disponible, sinon source.
        Retourne : {canonical_name: {"matiere": ..., "embedding": ..., "count": ...}}
        """
        from sqlalchemy import text

        query = """
            SELECT DISTINCT COALESCE(canonical_name, source) as canonical, matiere
            FROM concept_graph
            WHERE user_id IS NULL
              AND relation IN ('PRE_REQUIS_DE', 'EN_COURS')
        """
        params = {}
        if matiere:
            query += " AND matiere = :matiere"
            params["matiere"] = matiere

        rows = self.db.execute(text(query), params).fetchall()

        notions = {}
        for canonical, mat in rows:
            canon_norm = self.normalize(canonical)
            if canon_norm not in notions:
                notions[canon_norm] = {
                    "matiere": mat,
                    "embedding": None,
                    "count": 0,
                    "display_name": canonical,
                }
            notions[canon_norm]["count"] += 1

        return notions

    # ─────────────────────────────────────────────────────────────
    # Process principal
    # ─────────────────────────────────────────────────────────────

    async def process(
        self,
        raw_notions: List[str],
        matiere: Optional[str] = None,
        existing_notions: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> DeduplicationResult:
        """
        Déduplique une liste de notions brutes extraites par le LLM
        contre le graphe cognitif existant.

        Args:
            raw_notions: Notions brutes du LLM (ex: ["dérivées", "calcul différentiel"])
            matiere: Matière pour filtrer les notions existantes
            existing_notions: Cache des notions existantes (optionnel, pour les batchs)

        Returns:
            DeduplicationResult avec new, merged, ambiguous, relations
        """
        if existing_notions is None:
            existing_notions = self._load_existing_notions(matiere)

        result = DeduplicationResult()

        for raw_notion in raw_notions:
            normalized = self.normalize(raw_notion)
            if not normalized:
                continue

            # Correspondance exacte
            if normalized in existing_notions:
                result.merged.append({
                    "raw": raw_notion,
                    "canonical": normalized,
                    "score": 1.0,
                    "type": "exact_match",
                })
                continue

            # Embedding et similarité
            notion_emb = self._embed(raw_notion)
            best_match, best_score = self._find_best_match(notion_emb, existing_notions)

            if best_score >= MERGE_THRESHOLD:
                result.merged.append({
                    "raw": raw_notion,
                    "canonical": best_match,
                    "score": round(best_score, 3),
                    "type": "semantic_merge",
                })
            elif best_score < NEW_THRESHOLD:
                result.new.append(normalized)
                # Ajouter au cache pour les prochaines itérations
                existing_notions[normalized] = {
                    "matiere": matiere,
                    "embedding": notion_emb,
                    "count": 1,
                }
            else:
                result.ambiguous.append({
                    "raw": raw_notion,
                    "normalized": normalized,
                    "closest": best_match,
                    "score": round(best_score, 3),
                })

        return result

    def _find_best_match(
        self,
        query_emb: List[float],
        existing: Dict[str, Dict[str, Any]],
    ) -> Tuple[Optional[str], float]:
        """Trouve la notion existante la plus similaire."""
        best_match, best_score = None, 0.0

        for name, data in existing.items():
            emb = data.get("embedding")
            if emb is None:
                # Calculer et cacher
                emb = self._embed(name.replace("_", " "))
                existing[name]["embedding"] = emb

            score = self._cosine_similarity(query_emb, emb)
            if score > best_score:
                best_match, best_score = name, score

        return best_match, best_score
