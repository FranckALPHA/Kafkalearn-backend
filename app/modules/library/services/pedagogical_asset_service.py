"""
services/pedagogical_asset_service.py
=====================================
Service principal pour la gestion des assets pedagogiques.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.library.models import PedagogicalAsset, AssetCopy
from app.modules.library.utils import ShareCodeGenerator, StorageService, PLAN_HIERARCHY

logger = logging.getLogger(__name__)

try:
    from app.modules.library.jobs.tasks import increment_asset_stat_task
except ImportError:
    increment_asset_stat_task = None

from .base import LibraryBaseService


class PedagogicalAssetService(LibraryBaseService):
    def __init__(self, db: Session, redis=None):
        super().__init__(db, redis)
        self.storage = StorageService()

    # ─────────────────────────────────────────────────────────────
    # Sauvegarde d'un asset
    # ─────────────────────────────────────────────────────────────
    async def sauvegarder_asset(
        self,
        user_id,
        titre: str,
        asset_type: str,
        subject: Optional[str] = None,
        class_name: Optional[str] = None,
        serie: Optional[str] = None,
        notion: Optional[str] = None,
        content_json=None,
        file_url: Optional[str] = None,
        langue: str = "fr",
        required_plan: str = "access",
        source_doc_id: Optional[int] = None,
    ) -> Tuple[PedagogicalAsset, bool]:
        """Verifie le deduplication (meme user+titre+asset_type), cree si nouveau."""
        existing = (
            self.db.query(PedagogicalAsset)
            .filter(
                PedagogicalAsset.user_id == user_id,
                PedagogicalAsset.titre == titre,
                PedagogicalAsset.asset_type == asset_type,
                PedagogicalAsset.is_deleted.isnot(True),
            )
            .first()
        )
        if existing:
            return existing, True

        file_size_bytes = None
        if file_url:
            file_size_bytes = self.storage.get_file_size(file_url.lstrip("/storage/"))

        asset = PedagogicalAsset(
            user_id=user_id,
            titre=titre,
            asset_type=asset_type,
            subject=subject,
            class_name=class_name,
            serie=serie,
            notion=notion,
            content_json=content_json,
            file_url=file_url,
            file_size_bytes=file_size_bytes,
            langue=langue,
            required_plan=required_plan,
            source_doc_id=source_doc_id,
            generation_status="complete",
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset, False

    # ─────────────────────────────────────────────────────────────
    # Recuperation par ID
    # ─────────────────────────────────────────────────────────────
    async def recuperer_par_id(self, asset_id: int, user_id):
        """Recupere un asset, verifie propriete/plan, retourne le detail serialise."""
        asset = (
            self.db.query(PedagogicalAsset)
            .filter(PedagogicalAsset.id == asset_id)
            .first()
        )
        if not asset:
            raise ValueError("NOT_FOUND")

        is_owner = asset.user_id == user_id

        if not is_owner and not asset.is_public:
            raise ValueError("NOT_OWNER")

        if not is_owner and asset.is_public:
            user_plan = self._get_user_plan(user_id)
            if not self._plan_sufficient(user_plan, asset.required_plan):
                raise ValueError("PLAN_INSUFFICIENT")

        user_note = None
        if asset.is_public and not is_owner:
            from app.modules.library.models import AssetRating

            rating = (
                self.db.query(AssetRating)
                .filter(
                    AssetRating.asset_id == asset_id,
                    AssetRating.user_id == user_id,
                )
                .first()
            )
            if rating:
                user_note = rating.note

        # Incrementer nb_vues via Celery
        if increment_asset_stat_task:
            increment_asset_stat_task.delay(asset_id, "nb_vues")

        return asset.serialize_detail(is_owner=is_owner, user_note=user_note)

    # ─────────────────────────────────────────────────────────────
    # Lister assets utilisateur
    # ─────────────────────────────────────────────────────────────
    async def lister_assets_utilisateur(
        self,
        user_id,
        asset_type: Optional[str] = None,
        subject: Optional[str] = None,
        search: Optional[str] = None,
        tri: str = "date_desc",
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Liste les assets d'un utilisateur avec filtres, pagination, tri."""
        query = self.db.query(PedagogicalAsset).filter(
            PedagogicalAsset.user_id == user_id,
            PedagogicalAsset.is_deleted.isnot(True),
        )

        if asset_type:
            query = query.filter(PedagogicalAsset.asset_type == asset_type)
        if subject:
            query = query.filter(PedagogicalAsset.subject == subject)
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    PedagogicalAsset.titre.ilike(like),
                    PedagogicalAsset.notion.ilike(like),
                )
            )

        total = query.count()

        # Tri
        if tri == "date_desc":
            query = query.order_by(PedagogicalAsset.created_at.desc())
        elif tri == "date_asc":
            query = query.order_by(PedagogicalAsset.created_at.asc())
        elif tri == "note_desc":
            query = query.order_by(PedagogicalAsset.note_moyenne.desc().nullslast())
        elif tri == "vues_desc":
            query = query.order_by(PedagogicalAsset.nb_vues.desc())

        offset = (page - 1) * limit
        assets = query.offset(offset).limit(limit).all()

        return {
            "items": [a.serialize_list_item(is_owner=True) for a in assets],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1,
        }

    # ─────────────────────────────────────────────────────────────
    # Partager un asset
    # ─────────────────────────────────────────────────────────────
    async def partager_asset(self, asset_id: int, user_id, is_public: bool) -> dict:
        """Verifie la propriete, genere un code de partage si necessaire, met a jour is_public."""
        asset = self._verify_ownership(asset_id, user_id)
        asset.is_public = is_public

        if is_public and not asset.lien_partage:
            asset.lien_partage = ShareCodeGenerator.generate(self.db)

        self.db.commit()
        self.db.refresh(asset)

        lien_complet = None
        if asset.lien_partage:
            lien_complet = f"/library/explore?code={asset.lien_partage}"

        return {
            "is_public": asset.is_public,
            "lien_partage": asset.lien_partage,
            "url_complete": lien_complet,
        }

    # ─────────────────────────────────────────────────────────────
    # Copier un asset public
    # ─────────────────────────────────────────────────────────────
    async def copier_asset_public(self, asset_id: int, user_id) -> dict:
        """Verifie que l'asset est public, non possede par l'utilisateur, et non deja copie."""
        original = (
            self.db.query(PedagogicalAsset)
            .filter(PedagogicalAsset.id == asset_id)
            .first()
        )
        if not original:
            raise ValueError("NOT_FOUND")
        if not original.is_public:
            raise ValueError("NOT_PUBLIC")
        if original.user_id == user_id:
            raise ValueError("OWN_ASSET")

        deja_copie = (
            self.db.query(AssetCopy)
            .filter(
                AssetCopy.original_asset_id == asset_id,
                AssetCopy.copied_by == user_id,
            )
            .first()
        )
        if deja_copie:
            raise ValueError("ALREADY_COPIED")

        # Deep copy de l'asset
        copie = PedagogicalAsset(
            user_id=user_id,
            titre=f"{original.titre} (copie)",
            asset_type=original.asset_type,
            subject=original.subject,
            class_name=original.class_name,
            serie=original.serie,
            notion=original.notion,
            content_json=original.content_json,
            file_url=original.file_url,
            file_size_bytes=original.file_size_bytes,
            langue=original.langue,
            required_plan=original.required_plan,
            source_doc_id=original.source_doc_id,
            generation_status="complete",
            is_public=False,
        )
        self.db.add(copie)
        self.db.flush()

        # Enregistrer la copie
        record = AssetCopy(
            original_asset_id=asset_id,
            copy_asset_id=copie.id,
            copied_by=user_id,
        )
        self.db.add(record)

        # Incrementer le compteur de l'original
        original.nb_copies = (original.nb_copies or 0) + 1

        self.db.commit()
        self.db.refresh(copie)

        return {
            "copy_id": copie.id,
            "titre": copie.titre,
            "original_id": asset_id,
            "message": "Asset copie avec succes",
        }

    # ─────────────────────────────────────────────────────────────
    # Supprimer un asset
    # ─────────────────────────────────────────────────────────────
    async def supprimer_asset(self, asset_id: int, user_id) -> dict:
        """Verifie la propriete, supprime le fichier physique si local, soft-delete l'asset."""
        asset = self._verify_ownership(asset_id, user_id)

        # Supprimer le fichier physique si stockage local
        if asset.file_url:
            relative_path = asset.file_url.lstrip("/storage/")
            self.storage.delete_file(relative_path)

        # Soft delete
        asset.is_deleted = True
        self.db.commit()

        return {
            "asset_id": asset_id,
            "message": "Asset supprime avec succes",
        }

    # ─────────────────────────────────────────────────────────────
    # Explorer la communaute
    # ─────────────────────────────────────────────────────────────
    async def explorer_communaute(
        self,
        asset_type: Optional[str] = None,
        subject: Optional[str] = None,
        class_name: Optional[str] = None,
        search: Optional[str] = None,
        tri: str = "note_desc",
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Liste les assets publics avec filtres, pagination, tri."""
        query = self.db.query(PedagogicalAsset).filter(
            PedagogicalAsset.is_public == True,
            PedagogicalAsset.is_deleted.isnot(True),
        )

        if asset_type:
            query = query.filter(PedagogicalAsset.asset_type == asset_type)
        if subject:
            query = query.filter(PedagogicalAsset.subject == subject)
        if class_name:
            query = query.filter(PedagogicalAsset.class_name == class_name)
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    PedagogicalAsset.titre.ilike(like),
                    PedagogicalAsset.notion.ilike(like),
                )
            )

        total = query.count()

        # Tri
        if tri == "note_desc":
            query = query.order_by(PedagogicalAsset.note_moyenne.desc().nullslast())
        elif tri == "date_desc":
            query = query.order_by(PedagogicalAsset.created_at.desc())
        elif tri == "vues_desc":
            query = query.order_by(PedagogicalAsset.nb_vues.desc())
        elif tri == "copies_desc":
            query = query.order_by(PedagogicalAsset.nb_copies.desc())
        else:
            query = query.order_by(PedagogicalAsset.note_moyenne.desc().nullslast())

        offset = (page - 1) * limit
        assets = query.offset(offset).limit(limit).all()

        return {
            "items": [a.serialize_list_item(is_owner=False, mask_author=True) for a in assets],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1,
        }

    # ─────────────────────────────────────────────────────────────
    # Methodes internes
    # ─────────────────────────────────────────────────────────────
    def _verify_ownership(self, asset_id: int, user_id) -> PedagogicalAsset:
        """Verifie que l'asset existe et appartient a l'utilisateur."""
        asset = (
            self.db.query(PedagogicalAsset)
            .filter(PedagogicalAsset.id == asset_id)
            .first()
        )
        if not asset:
            raise ValueError("NOT_FOUND")
        if asset.user_id != user_id:
            raise ValueError("NOT_OWNER")
        return asset

    @staticmethod
    def _plan_sufficient(user_plan: Optional[str], required_plan: str) -> bool:
        """Verifie que le plan de l'utilisateur est suffisant."""
        if not user_plan:
            return required_plan == "freemium"
        try:
            user_idx = PLAN_HIERARCHY.index(user_plan)
            required_idx = PLAN_HIERARCHY.index(required_plan)
            return user_idx >= required_idx
        except ValueError:
            return False

    @staticmethod
    def _get_user_plan(user_id) -> Optional[str]:
        """Recupere le plan_effectif d'un utilisateur."""
        from app.modules.users.models import User

        user = (
            User.__table__.bind.execute(
                User.__table__.select().where(User.id == user_id)
            ).mappings()
            .first()
        )
        # Fallback via session si disponible
        if hasattr(user_id, "db") and user is None:
            return None
        return user.get("plan_effectif") if user else None
