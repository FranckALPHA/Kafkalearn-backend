import logging

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.user_documents.models import UserDocument, UserDocumentChunk
from app.modules.user_documents.services.base import UserDocumentsBaseService
from app.modules.user_documents.utils import TextCleaner

logger = logging.getLogger(__name__)


class UserDocumentRAGService(UserDocumentsBaseService):
    async def obtenir_contexte_pour_skill(
        self,
        user_id,
        document_id: int,
        query: str,
        top_k: int = 5,
    ) -> dict:
        """Get RAG context for a skill query against a user document.

        Steps:
        1. Check ownership and RAG readiness
        2. Increment utilisation counter
        3. If vectorized, return vectoriel mode chunks (placeholder)
        4. Else return textuel mode with truncated text
        """
        doc = (
            self.db.query(UserDocument)
            .filter(
                UserDocument.id == document_id,
                UserDocument.user_id == user_id,
            )
            .first()
        )
        if not doc:
            return {"error": "DOCUMENT_NOT_FOUND", "peut_utiliser": False}

        readiness = self.peut_utiliser_pour_rag(document_id, user_id)
        if not readiness["peut_utiliser"]:
            return {
                "peut_utiliser": False,
                "raison": readiness["raison"],
                "mode": readiness["mode"],
                "contexte": [],
            }

        # Increment usage counter
        doc.nb_utilisations_rag = (doc.nb_utilisations_rag or 0) + 1
        from datetime import datetime, timezone
        doc.derniere_utilisation_at = datetime.now(timezone.utc)
        self.db.commit()

        # Return context based on vectorization status
        if doc.is_vectorized and doc.vectorization_status == "complete":
            return self._obtenir_contexte_vectoriel(doc, query, top_k)
        else:
            return self._obtenir_contexte_textuel(doc, query)

    def peut_utiliser_pour_rag(self, document_id: int, user_id) -> dict:
        """Check if a document can be used for RAG.

        Returns {peut_utiliser, mode, raison}.
        """
        doc = (
            self.db.query(UserDocument)
            .filter(
                UserDocument.id == document_id,
                UserDocument.user_id == user_id,
            )
            .first()
        )
        if not doc:
            return {"peut_utiliser": False, "mode": None, "raison": "DOCUMENT_NOT_FOUND"}

        if doc.extraction_status != "success":
            return {
                "peut_utiliser": False,
                "mode": None,
                "raison": f"Extraction non terminee: {doc.extraction_status}",
            }

        if doc.is_vectorized and doc.vectorization_status == "complete":
            return {
                "peut_utiliser": True,
                "mode": "vectoriel",
                "raison": "Document vectorise et pret pour la recherche semantique",
            }

        if doc.extracted_text:
            return {
                "peut_utiliser": True,
                "mode": "textuel",
                "raison": "Document extrait mais pas encore vectorise",
            }

        return {
            "peut_utiliser": False,
            "mode": None,
            "raison": "Document non pret pour le RAG",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _obtenir_contexte_vectoriel(
        self,
        doc: UserDocument,
        query: str,
        top_k: int,
    ) -> dict:
        """Return context from vectorized chunks.

        NOTE: This is a placeholder. The actual implementation should query
        Vespa or another vector database for semantic similarity.
        """
        # Fallback: fetch top-k chunks from DB (no semantic ranking)
        chunks = (
            self.db.query(UserDocumentChunk)
            .filter(
                UserDocumentChunk.document_id == doc.id,
                UserDocumentChunk.is_embedded == True,  # noqa: E712
            )
            .order_by(UserDocumentChunk.chunk_idx)
            .limit(top_k)
            .all()
        )

        if not chunks:
            # No embedded chunks yet; fall back to textual mode
            return self._obtenir_contexte_textuel(doc, query)

        return {
            "peut_utiliser": True,
            "mode": "vectoriel",
            "document_id": doc.id,
            "query": query,
            "contexte": [c.serialize_for_rag() for c in chunks],
            "nb_chunks_returnes": len(chunks),
        }

    def _obtenir_contexte_textuel(self, doc: UserDocument, query: str) -> dict:
        """Return context from raw extracted text (truncated)."""
        if not doc.extracted_text:
            return {
                "peut_utiliser": False,
                "mode": "textuel",
                "raison": "Aucun texte extrait disponible",
                "contexte": [],
            }

        truncated = TextCleaner.truncate_for_prompt(doc.extracted_text, max_chars=3000)

        return {
            "peut_utiliser": True,
            "mode": "textuel",
            "document_id": doc.id,
            "titre": doc.titre,
            "query": query,
            "contexte": truncated,
            "nb_pages": doc.nb_pages,
        }
