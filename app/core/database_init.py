"""
app/core/database_init.py
=========================
Initialisation de la BDD avec découverte automatique des modèles.
"""
import logging
from app.core.database import Base, engine

# Import des modèles pour l'enregistrement dans Base.metadata
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

# Search
from app.modules.search.models import (  # noqa: F401
    SearchLog,
    SearchChunkReturned,
    SearchSuggestionCache,
)

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
