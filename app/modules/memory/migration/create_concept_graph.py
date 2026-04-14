"""
migration/create_concept_graph.py
=================================
Crée la table concept_graph et seed les prérequis globaux.

Usage :
    uv run python -m app.modules.memory.migration.create_concept_graph
"""
import logging
from app.core.database import engine, SessionLocal
from app.modules.memory.models.concept_graph import ConceptGraph

logger = logging.getLogger(__name__)


def create_table():
    """Crée la table concept_graph si elle n'existe pas."""
    logger.info("Création de la table concept_graph...")
    ConceptGraph.__table__.create(bind=engine, checkfirst=True)
    print("✅ Table concept_graph créée (ou déjà existante)")


def run(force_seed: bool = False):
    """Crée la table et seed les prérequis."""
    create_table()

    # Seed
    from app.modules.memory.seed.prerequisites_cm import seed as seed_prerequisites
    seed_prerequisites(force=force_seed)


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    run(force_seed=force)
