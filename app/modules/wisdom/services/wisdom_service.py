"""
services/wisdom_service.py
===========================
Service principal pour la gestion des conseils de sagesse quotidiens.
"""
import json
import logging
from datetime import date, datetime

from sqlalchemy import func

from app.modules.wisdom.services.base import WisdomBaseService
from app.modules.wisdom.models import WisdomTip, WisdomUserInteraction
from app.modules.wisdom.utils import get_static_tip_by_date, detect_category
from app.modules.wisdom.utils import ShareFormatter

logger = logging.getLogger(__name__)


class WisdomService(WisdomBaseService):
    """Service pour gerer les wisdom tips : obtention, generation, notation, partage."""

    async def obtenir_tip_du_jour(
        self, langue: str = "fr", date_cible: date = None, user_id: str = None
    ) -> dict:
        """Recupere le WisdomTip du jour depuis la DB.

        Si absent, genere via Celery et retourne un fallback statique.
        Si present, retourne le tip serialise. Marque comme vu si user_id fourni.
        """
        target_date = date_cible or date.today()

        tip = (
            self.db.query(WisdomTip)
            .filter(WisdomTip.tip_date == target_date)
            .first()
        )

        if tip is None:
            # Queue generation via Celery
            try:
                from app.modules.wisdom.jobs.tasks import generate_wisdom_task

                generate_wisdom_task.delay(target_date.isoformat())
            except ImportError:
                logger.warning("Celery task generate_wisdom_task non disponible.")
            except Exception as exc:
                logger.error("Erreur lors du queue de generate_wisdom_task: %s", exc)

            # Fallback statique
            static_data = get_static_tip_by_date(target_date)
            return {
                "id": None,
                "tip_date": str(target_date),
                "content": static_data.get(langue, static_data.get("fr", {})),
                "category": static_data.get("category", "vie"),
                "source": "static",
                "nb_vues": 0,
                "nb_partages": 0,
                "rating_moyen": None,
                "nb_notes": 0,
                "fallback": True,
            }

        if user_id:
            await self.marquer_vu(user_id=user_id, wisdom_id=tip.id)

        return tip.serialize(langue=langue)

    async def generer_wisdom_du_jour(self, date_str: str) -> dict | None:
        """Genere un wisdom tip via LLM, valide le JSON, detecte la categorie, sauvegarde en DB."""
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            logger.error("Format de date invalide: %s", date_str)
            return None

        # Tentative de generation via LLM
        try:
            from app.modules.skills.utils.llm_client import LLMClient

            llm = LLMClient()
            prompt = (
                "Genere un conseil de sagesse quotidien pour un etudiant camerounais. "
                "Retourne UNIQUEMENT un JSON valide avec cette structure: "
                '{"fr": {"text": "...", "author": "..."}, "en": {"text": "...", "author": "..."}}'
            )
            response = await llm.generate(prompt)
            raw_content = response if isinstance(response, str) else response.get("content", "")

            # Extraire le JSON du texte de reponse
            json_start = raw_content.find("{")
            json_end = raw_content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                logger.error("Aucun JSON trouve dans la reponse LLM.")
                return None

            content_json = json.loads(raw_content[json_start:json_end])

            # Validation minimale
            if "fr" not in content_json or "text" not in content_json.get("fr", {}):
                logger.error("Structure JSON invalide depuis LLM.")
                return None

        except ImportError:
            logger.error("Module LLM non disponible (app.modules.skills.utils.llm_client).")
            return None
        except json.JSONDecodeError as exc:
            logger.error("JSON invalide depuis LLM: %s", exc)
            return None
        except Exception as exc:
            logger.error("Erreur lors de la generation LLM: %s", exc)
            return None

        # Detection de categorie
        text_fr = content_json.get("fr", {}).get("text", "")
        text_en = content_json.get("en", {}).get("text", "")
        category = detect_category(text_fr, text_en)

        # Sauvegarde en DB
        tip = WisdomTip(
            tip_date=target_date,
            content_json=content_json,
            category=category,
            source="llm",
            llm_provider="skills.llm_client",
            nb_vues=0,
            nb_partages=0,
            nb_notes=0,
        )
        self.db.add(tip)
        self.db.commit()
        self.db.refresh(tip)

        logger.info("WisdomTip genere et sauve: id=%s, date=%s, category=%s", tip.id, tip.tip_date, category)
        return tip.serialize()

    async def marquer_vu(self, user_id: str, wisdom_id: int) -> None:
        """Upsert WisdomUserInteraction (vue=True) et incremente WisdomTip.nb_vues."""
        interaction = (
            self.db.query(WisdomUserInteraction)
            .filter(
                WisdomUserInteraction.user_id == user_id,
                WisdomUserInteraction.wisdom_id == wisdom_id,
            )
            .first()
        )

        if interaction is None:
            interaction = WisdomUserInteraction(
                user_id=user_id,
                wisdom_id=wisdom_id,
                vue=True,
            )
            self.db.add(interaction)
        else:
            interaction.vue = True

        # Incrementer le compteur de vues du tip
        tip = self.db.query(WisdomTip).filter(WisdomTip.id == wisdom_id).first()
        if tip:
            tip.nb_vues = (tip.nb_vues or 0) + 1

        self.db.commit()

    async def noter_tip(self, wisdom_id: int, user_id: str, note: int) -> dict:
        """Valide que l'utilisateur a vu le tip, upsert la note, recalcule la moyenne."""
        if not (1 <= note <= 5):
            raise ValueError("La note doit etre entre 1 et 5.")

        # Verifier que l'utilisateur a bien vu le tip
        interaction = (
            self.db.query(WisdomUserInteraction)
            .filter(
                WisdomUserInteraction.user_id == user_id,
                WisdomUserInteraction.wisdom_id == wisdom_id,
            )
            .first()
        )

        if interaction is None or not interaction.vue:
            raise ValueError("Vous devez d'abord consulter ce conseil avant de le noter.")

        # Upsert de la note
        interaction.note = note

        # Recalculer la moyenne
        avg_result = (
            self.db.query(func.avg(WisdomUserInteraction.note))
            .filter(
                WisdomUserInteraction.wisdom_id == wisdom_id,
                WisdomUserInteraction.note.isnot(None),
            )
            .scalar()
        )

        tip = self.db.query(WisdomTip).filter(WisdomTip.id == wisdom_id).first()
        if tip:
            tip.rating_moyen = round(float(avg_result), 2) if avg_result else None
            nb_notes = (
                self.db.query(func.count(WisdomUserInteraction.id))
                .filter(
                    WisdomUserInteraction.wisdom_id == wisdom_id,
                    WisdomUserInteraction.note.isnot(None),
                )
                .scalar()
            )
            tip.nb_notes = nb_notes or 0

        self.db.commit()

        nouveau_rating_moyen = tip.rating_moyen if tip else None
        return {"wisdom_id": wisdom_id, "nouveau_rating_moyen": nouveau_rating_moyen}

    async def enregistrer_partage(self, wisdom_id: int, user_id: str) -> str:
        """Upsert partage=True, incremente nb_partages, retourne le texte format pour le partage."""
        interaction = (
            self.db.query(WisdomUserInteraction)
            .filter(
                WisdomUserInteraction.user_id == user_id,
                WisdomUserInteraction.wisdom_id == wisdom_id,
            )
            .first()
        )

        if interaction is None:
            interaction = WisdomUserInteraction(
                user_id=user_id,
                wisdom_id=wisdom_id,
                vue=True,
                partage=True,
            )
            self.db.add(interaction)
        else:
            interaction.partage = True

        # Incrementer le compteur de partages
        tip = self.db.query(WisdomTip).filter(WisdomTip.id == wisdom_id).first()
        share_text = ""
        if tip:
            tip.nb_partages = (tip.nb_partages or 0) + 1
            content = tip.get_text(langue="fr")
            share_text = ShareFormatter.format_for_whatsapp(
                text=content.get("text", ""),
                author=content.get("author", ""),
            )

        self.db.commit()
        return share_text
