"""
playlist_service.py
===================
Gestion des playlists : CRUD, ajout/suppression de documents, partage, copie.
"""
import logging
import random
import string
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document, Playlist, PlaylistDocument

logger = logging.getLogger(__name__)

MAX_PLAYLISTS_PER_USER = 20
MAX_DOCUMENTS_PER_PLAYLIST = 100


class PlaylistService(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ── Création ──────────────────────────────────────────────────

    async def creer_playlist(
        self,
        user_id: Any,
        nom: str,
        description: Optional[str] = None,
        objectif: Optional[str] = None,
    ) -> dict:
        """Crée une nouvelle playlist pour un utilisateur."""
        # Check limit
        count = (
            self.db.query(Playlist)
            .filter(Playlist.user_id == user_id, Playlist.is_archived == False)  # noqa: E712
            .count()
        )
        if count >= MAX_PLAYLISTS_PER_USER:
            raise ValueError(
                f"Maximum {MAX_PLAYLISTS_PER_USER} playlists par utilisateur atteint."
            )

        playlist = Playlist(
            user_id=user_id,
            nom=nom,
            description=description,
            objectif=objectif,
        )
        self.db.add(playlist)
        self.db.commit()
        self.db.refresh(playlist)
        return playlist.serialize_detail()

    # ── Ajout / suppression de documents ──────────────────────────

    async def ajouter_document(
        self,
        playlist_id: int,
        document_id: int,
        user_id: Any,
    ) -> dict:
        """Ajoute un document à une playlist."""
        self._verify_playlist_ownership(playlist_id, user_id)

        # Verify document exists
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} introuvable.")

        # Check not duplicate
        existing = (
            self.db.query(PlaylistDocument)
            .filter(
                PlaylistDocument.playlist_id == playlist_id,
                PlaylistDocument.document_id == document_id,
            )
            .first()
        )
        if existing:
            raise ValueError("Ce document est déjà dans la playlist.")

        # Check playlist limit
        playlist = (
            self.db.query(Playlist)
            .filter(Playlist.id == playlist_id)
            .first()
        )
        if playlist.nb_documents >= MAX_DOCUMENTS_PER_PLAYLIST:
            raise ValueError(
                f"Maximum {MAX_DOCUMENTS_PER_PLAYLIST} documents par playlist atteint."
            )

        # Add
        position = (
            self.db.query(PlaylistDocument)
            .filter(PlaylistDocument.playlist_id == playlist_id)
            .count()
        )
        item = PlaylistDocument(
            playlist_id=playlist_id,
            document_id=document_id,
            position=position,
        )
        self.db.add(item)

        # Increment counters
        playlist.nb_documents += 1
        doc.nb_favoris += 1

        self.db.commit()
        self.db.refresh(playlist)
        return playlist.serialize_detail()

    async def supprimer_document(
        self,
        playlist_id: int,
        document_id: int,
        user_id: Any,
    ) -> bool:
        """Supprime un document d'une playlist."""
        self._verify_playlist_ownership(playlist_id, user_id)

        item = (
            self.db.query(PlaylistDocument)
            .filter(
                PlaylistDocument.playlist_id == playlist_id,
                PlaylistDocument.document_id == document_id,
            )
            .first()
        )
        if not item:
            return False

        self.db.delete(item)

        # Decrement counters
        playlist = (
            self.db.query(Playlist)
            .filter(Playlist.id == playlist_id)
            .first()
        )
        if playlist and playlist.nb_documents > 0:
            playlist.nb_documents -= 1

        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if doc and doc.nb_favoris > 0:
            doc.nb_favoris -= 1

        self.db.commit()
        return True

    # ── Listing / détail ──────────────────────────────────────────

    async def lister_playlists(self, user_id: Any) -> List[dict]:
        """Liste toutes les playlists d'un utilisateur (non archivées)."""
        playlists = (
            self.db.query(Playlist)
            .filter(
                Playlist.user_id == user_id,
                Playlist.is_archived == False,  # noqa: E712
            )
            .order_by(Playlist.updated_at.desc())
            .all()
        )
        return [p.serialize_list_item() for p in playlists]

    async def obtenir_playlist(
        self,
        playlist_id: int,
        user_id: Optional[Any] = None,
    ) -> Optional[dict]:
        """Obtient le détail d'une playlist avec ses documents."""
        q = self.db.query(Playlist).filter(Playlist.id == playlist_id)
        if user_id is not None:
            q = q.filter(Playlist.user_id == user_id)

        playlist = q.first()
        if not playlist:
            return None

        # Fetch documents in order
        items = (
            self.db.query(PlaylistDocument)
            .filter(PlaylistDocument.playlist_id == playlist_id)
            .order_by(PlaylistDocument.position)
            .all()
        )
        documents = []
        for item in items:
            doc = (
                self.db.query(Document)
                .filter(Document.id == item.document_id)
                .first()
            )
            if doc:
                documents.append(doc.serialize_list_item())

        result = playlist.serialize_detail()
        result["documents"] = documents
        return result

    # ── Partage ───────────────────────────────────────────────────

    async def partager_playlist(
        self,
        playlist_id: int,
        user_id: Any,
        is_public: bool = True,
    ) -> dict:
        """Active/désactive le partage d'une playlist et génère un code."""
        self._verify_playlist_ownership(playlist_id, user_id)

        playlist = (
            self.db.query(Playlist)
            .filter(Playlist.id == playlist_id)
            .first()
        )
        if is_public and not playlist.lien_partage:
            playlist.lien_partage = self._generate_partage_code()

        playlist.is_public = is_public
        self.db.commit()
        self.db.refresh(playlist)
        return playlist.serialize_detail()

    async def copier_playlist_publique(
        self,
        playlist_id_source: int,
        user_id: Any,
    ) -> dict:
        """Copie une playlist publique dans les playlists de l'utilisateur."""
        source = (
            self.db.query(Playlist)
            .filter(
                Playlist.id == playlist_id_source,
                Playlist.is_public == True,  # noqa: E712
            )
            .first()
        )
        if not source:
            raise ValueError("Playlist publique introuvable.")

        # Check user limit
        count = (
            self.db.query(Playlist)
            .filter(Playlist.user_id == user_id, Playlist.is_archived == False)  # noqa: E712
            .count()
        )
        if count >= MAX_PLAYLISTS_PER_USER:
            raise ValueError(
                f"Maximum {MAX_PLAYLISTS_PER_USER} playlists par utilisateur atteint."
            )

        # Create copy
        copy = Playlist(
            user_id=user_id,
            nom=f"{source.nom} (copie)",
            description=source.description,
            objectif=source.objectif,
            matiere_cible=source.matiere_cible,
            niveau_cible=source.niveau_cible,
        )
        self.db.add(copy)
        self.db.flush()

        # Copy documents
        source_items = (
            self.db.query(PlaylistDocument)
            .filter(PlaylistDocument.playlist_id == source.id)
            .order_by(PlaylistDocument.position)
            .all()
        )
        for idx, si in enumerate(source_items):
            self.db.add(
                PlaylistDocument(
                    playlist_id=copy.id,
                    document_id=si.document_id,
                    position=idx,
                )
            )

        copy.nb_documents = len(source_items)

        # Increment source nb_copies
        source.nb_copies += 1

        self.db.commit()
        self.db.refresh(copy)
        return copy.serialize_detail()

    # ── Suppression ───────────────────────────────────────────────

    async def supprimer_playlist(
        self,
        playlist_id: int,
        user_id: Any,
    ) -> bool:
        """Soft delete d'une playlist."""
        self._verify_playlist_ownership(playlist_id, user_id)

        playlist = (
            self.db.query(Playlist)
            .filter(Playlist.id == playlist_id)
            .first()
        )
        if not playlist:
            return False

        playlist.is_archived = True
        self.db.commit()
        return True

    # ── Private helpers ───────────────────────────────────────────

    def _verify_playlist_ownership(self, playlist_id: int, user_id: Any) -> Playlist:
        """Vérifie que la playlist appartient à l'utilisateur."""
        playlist = (
            self.db.query(Playlist)
            .filter(Playlist.id == playlist_id, Playlist.user_id == user_id)
            .first()
        )
        if not playlist:
            raise ValueError("Playlist introuvable ou non autorisée.")
        return playlist

    @staticmethod
    def _generate_partage_code() -> str:
        """Génère un code de partage unique PLY-XXXXXX."""
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"PLY-{code}"
