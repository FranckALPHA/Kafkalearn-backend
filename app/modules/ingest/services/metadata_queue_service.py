import logging
from datetime import datetime

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.ingest.services.base import IngestBaseService

logger = logging.getLogger(__name__)


class MetadataQueueService(IngestBaseService):
    def mettre_en_attente(
        self,
        fichier_path: str,
        raison: str,
        metadata_tentee: dict = None,
        texte_preview: str = None,
    ):
        """Create a MetadataQueue entry for unresolved metadata."""
        from app.modules.ingest.models import MetadataQueue
        from app.modules.users.models.user import User

        # Get a default resolver (first admin or system user)
        resolver = self.db.query(User).first()
        resolved_by = resolver.id if resolver else None

        entry = MetadataQueue(
            fichier_path=fichier_path,
            texte_extrait_preview=texte_preview,
            raison_echec=raison,
            metadata_tentee=metadata_tentee or {},
            nb_retries=0,
            is_resolved=False,
            resolved_by=resolved_by,
        )
        self.db.add(entry)
        self.db.commit()
        return entry

    async def reprocesser_batch(self, limit: int = 15, force: bool = False) -> dict:
        """Re-process unresolved queue entries using MetadataParserService."""
        from app.modules.ingest.models import MetadataQueue
        from app.modules.ingest.services.metadata_parser_service import (
            MetadataParserService,
        )

        query = self.db.query(MetadataQueue).filter(
            MetadataQueue.is_resolved == False  # noqa: E712
        )
        if not force:
            query = query.filter(MetadataQueue.nb_retries < 3)

        entries = query.limit(limit).all()

        resultats = {"total": len(entries), "succes": 0, "echecs": 0, "details": []}

        for entry in entries:
            try:
                parser = MetadataParserService(db=self.db, redis=self.redis)
                texte = entry.texte_extrait_preview or ""
                metadata, confidence = await parser.extraire_metadata(
                    texte, entry.fichier_path
                )

                if confidence >= 0.6:
                    entry.is_resolved = True
                    entry.resolved_at = datetime.utcnow()
                    entry.metadata_tentee = metadata
                    entry.nb_retries += 1
                    entry.dernier_retry_at = datetime.utcnow()
                    resultats["succes"] += 1
                    resultats["details"].append(
                        {
                            "queue_id": entry.id,
                            "status": "resolved",
                            "confidence": confidence,
                        }
                    )
                else:
                    entry.nb_retries += 1
                    entry.dernier_retry_at = datetime.utcnow()
                    resultats["echecs"] += 1
                    resultats["details"].append(
                        {
                            "queue_id": entry.id,
                            "status": "low_confidence",
                            "confidence": confidence,
                        }
                    )

            except Exception as exc:
                logger.error(f"Reprocessing failed for queue entry {entry.id}: {exc}")
                entry.nb_retries += 1
                entry.dernier_retry_at = datetime.utcnow()
                resultats["echecs"] += 1
                resultats["details"].append(
                    {
                        "queue_id": entry.id,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        self.db.commit()
        return resultats

    def obtenir_non_resolus(self, limit: int = 20) -> list:
        """Return unresolved queue entries."""
        from app.modules.ingest.models import MetadataQueue

        entries = (
            self.db.query(MetadataQueue)
            .filter(MetadataQueue.is_resolved == False)  # noqa: E712
            .order_by(MetadataQueue.created_at.desc())
            .limit(limit)
            .all()
        )
        return [entry.serialize_for_admin() for entry in entries]
