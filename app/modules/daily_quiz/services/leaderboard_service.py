import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from redis import Redis

from app.modules.daily_quiz.services.base import DailyQuizBaseService
from app.modules.daily_quiz.models import MonthlyLeaderboard
from app.modules.users.models.user import User
from app.modules.daily_quiz.utils import Pseudonymizer

logger = logging.getLogger(__name__)


class LeaderboardService(DailyQuizBaseService):
    async def mettre_a_jour_score(
        self, user_id: uuid.UUID, score_pct: float, month_year: str
    ) -> None:
        """Upsert monthly leaderboard entry for a user."""
        entry = (
            self.db.query(MonthlyLeaderboard)
            .filter(
                MonthlyLeaderboard.user_id == user_id,
                MonthlyLeaderboard.month_year == month_year,
            )
            .first()
        )

        if entry is None:
            entry = MonthlyLeaderboard(
                user_id=user_id,
                month_year=month_year,
                total_score=0,
                nb_participations=0,
                nb_perfect_scores=0,
                meilleur_score_pct=0.0,
            )
            self.db.add(entry)
            self.db.flush()

        entry.nb_participations += 1
        entry.total_score += int(score_pct)
        if entry.meilleur_score_pct is None or score_pct > entry.meilleur_score_pct:
            entry.meilleur_score_pct = score_pct
        if abs(score_pct - 100.0) < 0.01:
            entry.nb_perfect_scores += 1

        self.db.flush()

    async def obtenir_leaderboard(
        self, month_year: str, limit: int = 20, user_id: uuid.UUID = None
    ) -> dict:
        """Get top leaderboard entries with optional current user rank."""
        entries = (
            self.db.query(MonthlyLeaderboard, User.prenom, User.classe)
            .join(User, MonthlyLeaderboard.user_id == User.id)
            .filter(MonthlyLeaderboard.month_year == month_year)
            .order_by(desc(MonthlyLeaderboard.total_score))
            .limit(limit)
            .all()
        )

        top_entries = []
        for entry, prenom, classe in entries:
            pseudonymized = Pseudonymizer.mask_name(prenom or "Anonyme")
            top_entries.append({
                "user_id": str(entry.user_id),
                "user_prenom": pseudonymized,
                "user_classe": classe,
                "month_year": entry.month_year,
                "total_score": entry.total_score,
                "nb_participations": entry.nb_participations,
                "nb_perfect_scores": entry.nb_perfect_scores,
                "meilleur_score_pct": entry.meilleur_score_pct,
                "rang": entry.rang,
            })

        current_user_rank = None
        if user_id:
            user_entry = (
                self.db.query(MonthlyLeaderboard)
                .filter(
                    MonthlyLeaderboard.user_id == user_id,
                    MonthlyLeaderboard.month_year == month_year,
                )
                .first()
            )
            if user_entry and user_entry.rang:
                # Count how many have strictly higher total_score to determine rank
                higher_count = (
                    self.db.query(MonthlyLeaderboard)
                    .filter(
                        MonthlyLeaderboard.month_year == month_year,
                        MonthlyLeaderboard.total_score > user_entry.total_score,
                    )
                    .count()
                )
                current_user_rank = higher_count + 1

        return {
            "month_year": month_year,
            "top_entries": top_entries,
            "current_user_rank": current_user_rank,
            "generated_at": datetime.now().isoformat(),
        }

    async def calculer_rangs(self, month_year: str) -> int:
        """Calculate and set rang for all entries of the given month."""
        entries = (
            self.db.query(MonthlyLeaderboard)
            .filter(MonthlyLeaderboard.month_year == month_year)
            .order_by(desc(MonthlyLeaderboard.total_score))
            .all()
        )

        now = datetime.now()
        for rank, entry in enumerate(entries, start=1):
            entry.rang = rank
            entry.rang_calcule_at = now

        self.db.commit()
        return len(entries)
