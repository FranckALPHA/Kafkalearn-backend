"""
document_ingest_service.py
===========================
Pipeline d'ingestion : extraction, chunking, embedding, indexation.
"""
import logging
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document, DocumentChunk
from app.modules.epreuves.utils.meilisearch_client import MeiliClient

logger = logging.getLogger(__name__)


class DocumentIngestService(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.meili = MeiliClient(self.redis)

    # ── Extraction ────────────────────────────────────────────────

    def extract_text_from_pdf(self, chemin: str) -> Optional[str]:
        """Extrait le texte d'un PDF.
        Placeholder : retourne le texte_extrait du document si disponible.
        Une implémentation réelle utiliserait PyPDF2 / pdfplumber.
        """
        # Try to find the document and return existing extracted text
        doc = (
            self.db.query(Document)
            .filter(Document.chemin_final == chemin)
            .first()
        )
        if doc and doc.texte_extrait:
            return doc.texte_extrait

        # Placeholder: attempt basic text extraction if a library is available
        try:
            import pdfplumber
            with pdfplumber.open(chemin) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text if text.strip() else None
        except ImportError:
            logger.debug("pdfplumber not installed, using placeholder")
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")

        return None

    # ── Chunking ──────────────────────────────────────────────────

    def chunk_text(
        self,
        texte: str,
        max_tokens: int = 512,
    ) -> List[Dict[str, Any]]:
        """Découpe le texte en chunks par paragraphes / sauts de ligne."""
        if not texte:
            return []

        # Split by double newlines (paragraphs) first, then single newlines
        paragraphs = texte.split("\n\n")
        chunks = []
        current_chunk = ""
        chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds max_tokens, save current and start new
            para_tokens = self._estimate_tokens(para)
            current_tokens = self._estimate_tokens(current_chunk)

            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append({
                    "texte_chunk": current_chunk.strip(),
                    "chunk_idx": chunk_idx,
                    "nb_tokens_estime": current_tokens,
                })
                chunk_idx += 1
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                "texte_chunk": current_chunk.strip(),
                "chunk_idx": chunk_idx,
                "nb_tokens_estime": self._estimate_tokens(current_chunk),
            })

        # If a single paragraph is too large, split by single newlines
        final_chunks = []
        for chunk in chunks:
            if chunk["nb_tokens_estime"] > max_tokens * 2:
                lines = chunk["texte_chunk"].split("\n")
                sub_text = ""
                for line in lines:
                    if self._estimate_tokens(sub_text + "\n" + line) > max_tokens and sub_text:
                        final_chunks.append({
                            "texte_chunk": sub_text.strip(),
                            "chunk_idx": chunk["chunk_idx"],
                            "nb_tokens_estime": self._estimate_tokens(sub_text),
                        })
                        chunk["chunk_idx"] += 1
                        sub_text = line
                    else:
                        sub_text += "\n" + line if sub_text else line
                if sub_text.strip():
                    final_chunks.append({
                        "texte_chunk": sub_text.strip(),
                        "chunk_idx": chunk["chunk_idx"],
                        "nb_tokens_estime": self._estimate_tokens(sub_text),
                    })
            else:
                final_chunks.append(chunk)

        return final_chunks

    # ── Sauvegarde des chunks ─────────────────────────────────────

    def sauvegarder_chunks(
        self,
        doc_id: int,
        chunks: List[Dict[str, Any]],
    ) -> List[int]:
        """Sauvegarde les DocumentChunk en base."""
        ids = []
        for c in chunks:
            chunk = DocumentChunk(
                doc_id=doc_id,
                texte_chunk=c["texte_chunk"],
                chunk_idx=c["chunk_idx"],
                nb_tokens_estime=c.get("nb_tokens_estime"),
            )
            self.db.add(chunk)
            self.db.flush()
            ids.append(chunk.id)
        self.db.commit()
        return ids

    # ── Embedding Vespa ───────────────────────────────────────────

    def embed_chunks_in_vespa(
        self,
        doc_id: int,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """Envoie les chunks à Vespa pour embedding.
        Placeholder : marque les chunks comme embedded.
        """
        count = 0
        for c in chunks:
            db_chunk = (
                self.db.query(DocumentChunk)
                .filter(
                    DocumentChunk.doc_id == doc_id,
                    DocumentChunk.chunk_idx == c["chunk_idx"],
                )
                .first()
            )
            if db_chunk:
                db_chunk.is_embedded = True
                count += 1

        self.db.commit()

        # Mark document as embedded
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.is_embedded = True

        # Check if all chunks are embedded
        total_chunks = (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.doc_id == doc_id)
            .count()
        )
        embedded_chunks = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.doc_id == doc_id,
                DocumentChunk.is_embedded == True,  # noqa: E712
            )
            .count()
        )
        if doc and total_chunks > 0 and embedded_chunks == total_chunks:
            doc.is_embedded = True
            self.db.commit()

        logger.info(f"Embedded {count}/{total_chunks} chunks for doc {doc_id}")
        return count

    # ── Indexation MeiliSearch ────────────────────────────────────

    def index_in_meilisearch(self, doc_id: int) -> bool:
        """Indexe un document dans MeiliSearch."""
        doc = (
            self.db.query(Document)
            .filter(Document.id == doc_id)
            .first()
        )
        if not doc:
            return False

        doc_data = {
            "id": doc.id,
            "nom_affiche": doc.nom_affiche or doc.nom_original,
            "matiere": doc.matiere,
            "niveau": doc.niveau,
            "serie": doc.serie,
            "annee": doc.annee,
            "region": doc.region,
            "type_doc": doc.type_doc,
            "notion_principale": doc.notion_principale,
            "difficulte_estimee": doc.difficulte_estimee,
            "nb_vues": doc.nb_vues,
            "is_validated": doc.is_validated,
            "mots_cles": doc.mots_cles or [],
            "texte_extrait": (doc.texte_extrait or "")[:5000],  # Truncate for indexing
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

        try:
            self.meili.index_document(doc_data)
            return True
        except Exception as e:
            logger.error(f"MeiliSearch indexing failed for doc {doc_id}: {e}")
            return False

    # ── Pipeline complet ──────────────────────────────────────────

    def run_full_ingestion(self, doc_id: int) -> dict:
        """Orchestre le pipeline complet d'ingestion."""
        doc = (
            self.db.query(Document)
            .filter(Document.id == doc_id)
            .first()
        )
        if not doc:
            raise ValueError(f"Document {doc_id} introuvable.")

        doc.ingest_status = "processing"
        self.db.commit()

        result = {
            "doc_id": doc_id,
            "text_extracted": False,
            "chunks_count": 0,
            "chunks_embedded": 0,
            "meilisearch_indexed": False,
        }

        try:
            # 1. Extract text
            if not doc.texte_extrait and doc.chemin_final:
                texte = self.extract_text_from_pdf(doc.chemin_final)
                if texte:
                    doc.texte_extrait = texte
                    result["text_extracted"] = True
                    self.db.commit()

            texte = doc.texte_extrait or ""

            # 2. Chunk text
            if texte:
                chunks = self.chunk_text(texte)
                result["chunks_count"] = len(chunks)

                if chunks:
                    # 3. Save chunks
                    self.sauvegarder_chunks(doc_id, chunks)

                    # 4. Embed chunks
                    result["chunks_embedded"] = self.embed_chunks_in_vespa(doc_id, chunks)

            # 5. Index in MeiliSearch
            result["meilisearch_indexed"] = self.index_in_meilisearch(doc_id)

            # Mark completed
            doc.ingest_status = "completed"
            self.db.commit()

        except Exception as e:
            logger.error(f"Ingestion failed for doc {doc_id}: {e}", exc_info=True)
            doc.ingest_status = "failed"
            self.db.commit()
            result["error"] = str(e)

        return result

    # ── Private helpers ───────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimation grossière : ~4 caractères par token."""
        if not text:
            return 0
        return max(1, len(text) // 4)
