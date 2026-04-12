import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.models import UserSectionProgress, MemorySection, MemoryItemAttempt
from app.modules.memory.utils import SM2Algorithm, SM2Result

logger = logging.getLogger(__name__)


class SpacedRepetitionScheduler(MemoryBaseService):
    """Service responsible for spaced repetition scheduling using the SM-2 algorithm."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculer_prochaine_revision(
        self,
        user_id: str,
        section_id: int,
        qualite_reponse: int,
        repetition_count: Optional[int] = None,
    ) -> SM2Result:
        """Calculate the next review date for a user's section using SM-2.

        Loads UserSectionProgress with for_update, computes repetition_count
        if None from recent attempts, applies SM2Algorithm.calculate, updates
        progress fields, commits, and returns the result.
        """
        # 1. Load progress with row-level lock
        progress = (
            self.db.query(UserSectionProgress)
            .filter(
                UserSectionProgress.user_id == user_id,
                UserSectionProgress.section_id == section_id,
            )
            .with_for_update()
            .first()
        )
        if progress is None:
            raise ValueError(f"No progress record found for user={user_id}, section={section_id}")

        # 2. Compute repetition_count if not provided
        if repetition_count is None:
            repetition_count = await self._compter_reussites_consecutives(user_id, section_id)

        # 3. Apply SM-2
        now = datetime.now(timezone.utc)
        result = SM2Algorithm.calculate(
            quality=qualite_reponse,
            current_ef=progress.easiness_factor,
            current_interval=progress.interval_jours,
            repetition_count=repetition_count,
            review_date=now,
        )

        # 4. Update progress fields
        progress.easiness_factor = result.easiness_factor
        progress.interval_jours = result.interval_days
        progress.next_review_at = result.next_review_date
        progress.last_reviewed_at = now
        progress.nb_revisions = (progress.nb_revisions or 0) + 1

        self.db.commit()

        return result

    async def obtenir_sections_a_revoir(
        self, user_id: str, grace_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get sections that are due for review for a given user.

        Queries UserSectionProgress joined with MemorySection where
        next_review_at <= now + grace_hours and is_completed=True,
        orders by urgency, returns list of dicts.
        """
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=grace_hours)

        rows = (
            self.db.query(UserSectionProgress, MemorySection)
            .join(MemorySection, UserSectionProgress.section_id == MemorySection.id)
            .filter(
                UserSectionProgress.user_id == user_id,
                UserSectionProgress.is_completed.is_(True),
                UserSectionProgress.next_review_at.isnot(None),
                UserSectionProgress.next_review_at <= deadline,
            )
            .order_by(UserSectionProgress.next_review_at.asc())
            .all()
        )

        result = []
        for progress, section in rows:
            urgence = self._calculer_urgence(progress, now)
            jours_depuis = (now - progress.last_reviewed_at).days if progress.last_reviewed_at else None
            result.append(
                {
                    "section": section.serialize_list_item(user_progress=progress),
                    "urgence": urgence,
                    "nb_jours_depuis_revision": jours_depuis,
                    "progress": progress.serialize_progress(),
                }
            )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculer_urgence(progress: UserSectionProgress, now: datetime) -> str:
        """Categorize review urgency."""
        if progress.next_review_at is None:
            return "urgent"

        next_review = progress.next_review_at
        if next_review.tzinfo is None:
            next_review = next_review.replace(tzinfo=timezone.utc)

        days_overdue = (now - next_review).days

        if days_overdue > 3:
            return "urgent"
        elif days_overdue > 0:
            return "en_retard"
        elif days_overdue >= -1:
            return "normal"
        else:
            return "avance"

    async def _compter_reussites_consecutives(self, user_id: str, section_id: int) -> int:
        """Count consecutive correct attempts from most recent for a user/section."""
        attempts = (
            self.db.query(MemoryItemAttempt)
            .join(UserSectionProgress, UserSectionProgress.section_id == MemoryItemAttempt.section_id)
            .filter(
                UserSectionProgress.user_id == user_id,
                MemoryItemAttempt.section_id == section_id,
            )
            .order_by(MemoryItemAttempt.created_at.desc())
            .all()
        )

        count = 0
        for attempt in attempts:
            if attempt.est_correct:
                count += 1
            else:
                break

        return count
