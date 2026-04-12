import logging
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.calendar.services.base import CalendarBaseService
from app.modules.calendar.models import (
    CalendarTimetable,
    CalendarPersonalStudy,
    DailySuggestionsCache,
)

logger = logging.getLogger(__name__)


class ContentSuggestionService(CalendarBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ─── Génération des suggestions ──────────────────────────────

    async def generer_suggestions_jour(
        self, user_id: str, target_date: datetime = None
    ) -> dict:
        target_date = target_date or datetime.now(timezone.utc)
        matieres = await self._identifier_matieres_du_jour(user_id, target_date)

        suggestions = {
            "memory": await self._collect_memory_suggestions(user_id, matieres, target_date),
            "epreuves": await self._collect_epreuves_suggestions(user_id, matieres),
            "skills": await self._collect_skills_suggestions(user_id, matieres),
            "assets_perso": await self._collect_personal_assets(user_id, matieres),
        }

        # Tri par priorité
        for category in suggestions:
            suggestions[category].sort(key=lambda s: s.get("priority", 0), reverse=True)

        await self._cache_suggestions(user_id, target_date, suggestions)
        return {
            "date": target_date.date().isoformat(),
            "matieres_du_jour": matieres,
            "suggestions": suggestions,
        }

    # ─── Identification des matières du jour ─────────────────────

    async def _identifier_matieres_du_jour(
        self, user_id: str, target_date: datetime
    ) -> list:
        day_of_week = target_date.weekday()

        timetable_subjects = (
            self.db.query(CalendarTimetable.subject)
            .filter(
                CalendarTimetable.user_id == user_id,
                CalendarTimetable.day_of_week == day_of_week,
                CalendarTimetable.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        personal_subjects = (
            self.db.query(CalendarPersonalStudy.subject)
            .filter(
                CalendarPersonalStudy.user_id == user_id,
                CalendarPersonalStudy.day_of_week == day_of_week,
                CalendarPersonalStudy.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        unique = set()
        for row in timetable_subjects + personal_subjects:
            if row[0]:
                unique.add(row[0])

        return sorted(unique)

    # ─── Collecte par catégorie ──────────────────────────────────

    async def _collect_memory_suggestions(
        self, user_id: str, matieres: list, target_date: datetime
    ) -> list:
        results = []
        try:
            from app.modules.memory.models import MemorySection, UserSectionProgress
        except ImportError:
            logger.debug("Module memory non disponible")
            return results

        if not matieres:
            return results

        due_sections = (
            self.db.query(UserSectionProgress, MemorySection)
            .join(MemorySection, UserSectionProgress.section_id == MemorySection.id)
            .filter(
                UserSectionProgress.user_id == user_id,
                MemorySection.subject.in_(matieres),
                UserSectionProgress.next_review <= func.now(),
                UserSectionProgress.is_active.is_(True),
            )
            .order_by(UserSectionProgress.next_review.asc())
            .limit(20)
            .all()
        )

        for progress, section in due_sections:
            results.append({
                "type": "memory",
                "title": section.title,
                "subject": section.subject,
                "section_id": section.id,
                "priority": 10,
                "next_review": progress.next_review.isoformat() if progress.next_review else None,
            })

        return results

    async def _collect_epreuves_suggestions(
        self, user_id: str, matieres: list
    ) -> list:
        results = []
        try:
            from app.modules.epreuves.models import Document
        except ImportError:
            logger.debug("Module epreuves non disponible")
            return results

        if not matieres:
            return results

        popular_docs = (
            self.db.query(Document)
            .filter(
                Document.matiere.in_(matieres),
                Document.is_validated.is_(True),
                Document.type_doc == "EPREUVE",
            )
            .order_by(Document.nb_vues.desc())
            .limit(10)
            .all()
        )

        for doc in popular_docs:
            results.append({
                "type": "epreuve",
                "title": doc.nom_affiche or doc.nom_original,
                "subject": doc.matiere,
                "document_id": doc.id,
                "priority": 8,
                "nb_vues": doc.nb_vues,
            })

        return results

    async def _collect_skills_suggestions(
        self, user_id: str, matieres: list
    ) -> list:
        results = []
        if not matieres:
            return results

        for matiere in matieres:
            results.append({
                "type": "skill",
                "title": f"Exercice interactif — {matiere}",
                "subject": matiere,
                "priority": 7,
            })

        return results

    async def _collect_personal_assets(
        self, user_id: str, matieres: list
    ) -> list:
        results = []
        try:
            from app.modules.library.models import PedagogicalAsset
        except ImportError:
            logger.debug("Module library non disponible")
            return results

        if not matieres:
            return results

        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        assets = (
            self.db.query(PedagogicalAsset)
            .filter(
                PedagogicalAsset.user_id == user_id,
                PedagogicalAsset.subject.in_(matieres),
                PedagogicalAsset.created_at >= one_week_ago,
            )
            .order_by(PedagogicalAsset.created_at.desc())
            .limit(10)
            .all()
        )

        for asset in assets:
            results.append({
                "type": "asset",
                "title": asset.titre,
                "subject": asset.subject,
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "priority": 5,
            })

        return results

    # ─── Cache ───────────────────────────────────────────────────

    async def _cache_suggestions(
        self, user_id: str, target_date: datetime, suggestions: dict
    ) -> None:
        matieres = await self._identifier_matieres_du_jour(user_id, target_date)
        date_only = target_date.date()

        existing = (
            self.db.query(DailySuggestionsCache)
            .filter(
                DailySuggestionsCache.user_id == user_id,
                DailySuggestionsCache.date_suggestion == date_only,
            )
            .first()
        )

        if existing:
            existing.suggestions_json = suggestions
            existing.matieres_du_jour = matieres
            existing.generated_at = func.now()
        else:
            from app.modules.users.models import User

            cache_entry = DailySuggestionsCache(
                user_id=user_id,
                date_suggestion=date_only,
                suggestions_json=suggestions,
                matieres_du_jour=matieres,
            )
            self.db.add(cache_entry)

        self.db.commit()

        # Redis cache
        redis_key = f"calendar:suggestions:{user_id}:{date_only.isoformat()}"
        midnight = datetime.combine(
            date_only + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
        )
        ttl = int((midnight - datetime.now(timezone.utc)).total_seconds())
        if ttl > 0:
            try:
                import json
                self.redis.setex(redis_key, ttl, json.dumps(suggestions, default=str))
            except Exception as e:
                logger.warning("Erreur cache Redis suggestions: %s", e)

    # ─── Obtention avec cache ────────────────────────────────────

    async def obtenir_suggestions_cached(
        self, user_id: str, target_date: datetime = None
    ) -> dict:
        target_date = target_date or datetime.now(timezone.utc)
        date_only = target_date.date()

        # 1. Redis
        redis_key = f"calendar:suggestions:{user_id}:{date_only.isoformat()}"
        try:
            import json
            cached = self.redis.get(redis_key)
            if cached:
                data = json.loads(cached)
                return {
                    "date": date_only.isoformat(),
                    "suggestions": data,
                    "source": "redis",
                }
        except Exception as e:
            logger.debug("Redis cache miss: %s", e)

        # 2. DB
        db_entry = (
            self.db.query(DailySuggestionsCache)
            .filter(
                DailySuggestionsCache.user_id == user_id,
                DailySuggestionsCache.date_suggestion == date_only,
            )
            .first()
        )
        if db_entry and not db_entry.is_expired:
            return {
                "date": date_only.isoformat(),
                "suggestions": db_entry.suggestions_json,
                "matieres_du_jour": db_entry.matieres_du_jour,
                "source": "db",
            }

        # 3. Génération fraîche
        result = await self.generer_suggestions_jour(user_id, target_date)
        result["source"] = "generated"
        return result
