"""
app/core/database_init.py
=========================
Initialisation de la BDD avec découverte automatique des modèles.
"""
import logging
from app.core.database import Base, engine

# ─── Import TOUS les modèles AVANT toute utilisation ──────────────
# Ceci est critique pour éviter les erreurs de mapper SQLAlchemy
# quand des relations cross-module référencent des classes non définies.

# Users
from app.modules.users.models import (  # noqa: F401
    User,
    UserLearningProfile,
    UserActivity,
    EmailToken,
    RefreshToken,
    AuditLog,
    Role,
    Permission,
)

# Epreuves
from app.modules.epreuves.models import Document, Playlist  # noqa: F401
from app.modules.epreuves.models.document_view import DocumentView  # noqa: F401

# Notifications
from app.modules.notifications.models import Device  # noqa: F401
from app.modules.notifications.models.notification_log import NotificationLog  # noqa: F401
from app.modules.notifications.models.notification_preference import NotificationPreference  # noqa: F401

# Payment
from app.modules.payment.models.transaction import Transaction  # noqa: F401

# Ingest
from app.modules.ingest.models.ingest_job import IngestJob  # noqa: F401

# Calendar
from app.modules.calendar.models.calendar_personal_study import CalendarPersonalStudy  # noqa: F401
from app.modules.calendar.models.calendar_timetable import CalendarTimetable  # noqa: F401
from app.modules.calendar.models.daily_suggestions_cache import DailySuggestionsCache  # noqa: F401
from app.modules.calendar.models.calendar_session import CalendarSession  # noqa: F401

# Memory
from app.modules.memory.models.user_section_progress import UserSectionProgress  # noqa: F401

# Referral
from app.modules.referral.models.referral_reward import ReferralReward  # noqa: F401

# User Documents
from app.modules.user_documents.models.user_document import UserDocument  # noqa: F401

# Library
from app.modules.library.models.pedagogical_asset import PedagogicalAsset  # noqa: F401

# Wisdom
from app.modules.wisdom.models import WisdomUserInteraction  # noqa: F401

# School
from app.modules.school.models.school import School  # noqa: F401
from app.modules.school.models.school_member import SchoolMember  # noqa: F401
from app.modules.school.models.school_ai_usage import SchoolAIUsage  # noqa: F401

# Skills
from app.modules.skills.models import ChatSession, ChatMessage, SkillUsageLog, QuizSession  # noqa: F401

# Search
from app.modules.search.models import (  # noqa: F401
    SearchLog,
    SearchChunkReturned,
    SearchSuggestionCache,
)

# Daily Quiz
from app.modules.daily_quiz.models.daily_quiz_attempt import DailyQuizAttempt  # noqa: F401
from app.modules.daily_quiz.models.daily_quiz import DailyQuiz  # noqa: F401
from app.modules.daily_quiz.models.monthly_leaderboard import MonthlyLeaderboard  # noqa: F401

# User Learning Signals & Feedback
from app.modules.users.models.user_learning_signals import UserLearningSignals  # noqa: F401
from app.modules.users.models.user_feedback import UserFeedback  # noqa: F401

# Memory / Concept Graph
from app.modules.memory.models.concept_graph import ConceptGraph  # noqa: F401
from app.modules.memory.models.memory_section import MemorySection  # noqa: F401
from app.modules.memory.models.memory_item import MemoryItem  # noqa: F401

# Document Analysis
from app.modules.doc_analysis.models.document_analysis import DocumentAnalysis  # noqa: F401

# Epreuves chunks
from app.modules.epreuves.models.document_chunk import DocumentChunk  # noqa: F401

# Wisdom
from app.modules.wisdom.models.wisdom_tip import WisdomTip  # noqa: F401

# ─── Setup cross-module relationships ────────────────────────────
# Now that all models are imported, configure cross-module relationships
from app.modules.users.models.user import User, _setup_cross_module_relationships  # noqa: F401
_setup_cross_module_relationships()

log = logging.getLogger(__name__)


def init_db():
    """Crée les tables à partir des métadonnées découvertes."""
    try:
        log.info("Initialisation de la base de données...")
        Base.metadata.create_all(bind=engine)
        log.info("Base de données initialisée avec succès.")
    except Exception as e:
        log.error(f"Erreur lors de l'initialisation de la BDD : {e}")
        raise e
