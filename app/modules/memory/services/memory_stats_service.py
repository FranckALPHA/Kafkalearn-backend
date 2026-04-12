import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.models import MemorySection, MemoryItem, MemoryItemAttempt, UserSectionProgress

logger = logging.getLogger(__name__)


class MemoryStatsService(MemoryBaseService):
    """Service responsible for computing memory-related statistics for users and sections."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculer_stats_utilisateur(self, user_id: str) -> Dict[str, Any]:
        """Compute comprehensive memory statistics for a user.

        Returns dict with: total_sections, completed_sections, avg_score,
        total_reviews, accuracy, streak, next_reviews_due, top_weak_subjects.
        """
        # Total sections the user has engaged with
        total_sections = (
            self.db.query(func.count(UserSectionProgress.id))
            .filter(UserSectionProgress.user_id == user_id)
            .scalar()
            or 0
        )

        # Completed sections
        completed_sections = (
            self.db.query(func.count(UserSectionProgress.id))
            .filter(
                UserSectionProgress.user_id == user_id,
                UserSectionProgress.is_completed.is_(True),
            )
            .scalar()
            or 0
        )

        # Average score
        avg_score_row = (
            self.db.query(func.avg(UserSectionProgress.score_section))
            .filter(UserSectionProgress.user_id == user_id)
            .first()
        )
        avg_score = float(avg_score_row[0]) if avg_score_row and avg_score_row[0] is not None else 0.0

        # Total reviews (from attempts)
        total_reviews = (
            self.db.query(func.count(MemoryItemAttempt.id))
            .join(UserSectionProgress, UserSectionProgress.section_id == MemoryItemAttempt.section_id)
            .filter(UserSectionProgress.user_id == user_id)
            .scalar()
            or 0
        )

        # Accuracy (correct / total attempts)
        if total_reviews > 0:
            correct_count = (
                self.db.query(func.count(MemoryItemAttempt.id))
                .join(UserSectionProgress, UserSectionProgress.section_id == MemoryItemAttempt.section_id)
                .filter(
                    UserSectionProgress.user_id == user_id,
                    MemoryItemAttempt.est_correct.is_(True),
                )
                .scalar()
                or 0
            )
            accuracy = correct_count / total_reviews
        else:
            accuracy = 0.0

        # Streak (simplified: from user-level; could be enhanced with a dedicated streak table)
        streak = 0
        try:
            from app.modules.users.models import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, "streak"):
                streak = user.streak or 0
        except Exception:
            streak = 0

        # Next reviews due
        now = datetime.now(timezone.utc)
        next_reviews_due = (
            self.db.query(func.count(UserSectionProgress.id))
            .filter(
                UserSectionProgress.user_id == user_id,
                UserSectionProgress.next_review_at.isnot(None),
                UserSectionProgress.next_review_at <= now,
            )
            .scalar()
            or 0
        )

        # Top weak subjects (sections with lowest success rate)
        top_weak_subjects = await self._obtenir_sujets_faibles(user_id)

        return {
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "avg_score": round(avg_score, 2),
            "total_reviews": total_reviews,
            "accuracy": round(accuracy, 4),
            "streak": streak,
            "next_reviews_due": next_reviews_due,
            "top_weak_subjects": top_weak_subjects,
        }

    async def mettre_a_jour_difficulte_section(self, section_id: int) -> None:
        """Recalculate MemoryItem taux_reussite and difficulte_percue from attempts,
        and update MemorySection difficulte_moyenne.
        """
        section = (
            self.db.query(MemorySection)
            .filter(MemorySection.id == section_id)
            .first()
        )
        if section is None:
            raise ValueError(f"MemorySection {section_id} not found")

        items = self.db.query(MemoryItem).filter(MemoryItem.section_id == section_id).all()

        total_difficulte = 0.0
        item_count = 0

        for item in items:
            attempts = (
                self.db.query(MemoryItemAttempt)
                .filter(MemoryItemAttempt.item_id == item.id)
                .all()
            )

            if attempts:
                nb_tentatives = len(attempts)
                correct_count = sum(1 for a in attempts if a.est_correct)
                taux_reussite = correct_count / nb_tentatives if nb_tentatives > 0 else 0.0

                item.nb_tentatives = nb_tentatives
                item.taux_reussite = round(taux_reussite, 4)

                # Perceived difficulty: inverse of success rate
                item.difficulte_percue = round(1.0 - taux_reussite, 4)
                total_difficulte += item.difficulte_percue
                item_count += 1

        # Update section average difficulty
        if item_count > 0:
            section.difficulte_moyenne = round(total_difficulte / item_count, 4)
        else:
            section.difficulte_moyenne = None

        self.db.commit()
        logger.info(
            "Updated difficulty for section %s: %.4f (%d items)",
            section_id,
            section.difficulte_moyenne or 0,
            item_count,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _obtenir_sujets_faibles(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the user's weakest subjects (sections with lowest success rate)."""
        # Subquery: average qualite_reponse per section for this user
        subq = (
            self.db.query(
                MemoryItemAttempt.section_id,
                func.avg(MemoryItemAttempt.qualite_reponse).label("avg_qualite"),
                func.count(MemoryItemAttempt.id).label("nb_attempts"),
            )
            .join(UserSectionProgress, UserSectionProgress.section_id == MemoryItemAttempt.section_id)
            .filter(UserSectionProgress.user_id == user_id)
            .group_by(MemoryItemAttempt.section_id)
            .having(func.count(MemoryItemAttempt.id) >= 1)
            .subquery()
        )

        rows = (
            self.db.query(MemorySection, subq.c.avg_qualite, subq.c.nb_attempts)
            .join(subq, MemorySection.id == subq.c.section_id)
            .order_by(subq.c.avg_qualite.asc())
            .limit(limit)
            .all()
        )

        result = []
        for section, avg_qualite, nb_attempts in rows:
            result.append(
                {
                    "section_id": section.id,
                    "section_title": section.section_title,
                    "avg_qualite": round(float(avg_qualite), 2) if avg_qualite else 0,
                    "nb_attempts": nb_attempts,
                    "matiere": section.document.matiere if section.document else "unknown",
                }
            )

        return result
