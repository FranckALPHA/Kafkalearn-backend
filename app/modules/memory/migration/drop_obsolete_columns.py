"""
migration/drop_obsolete_columns.py
===================================
Supprime les colonnes JSONB obsolètes de user_learning_profiles.
Les données ont été migrées vers concept_graph (Phases 1-2).

Usage :
    uv run python -m app.modules.memory.migration.drop_obsolete_columns [--dry-run]
"""
import logging

logger = logging.getLogger(__name__)

OBSOLETE_COLUMNS = [
    "lacunes",
    "forces",
    "intentions_recentes",
    "skills_utilises",
    "sujets_vus",
    "score_par_matiere",
]


def run(dry_run: bool = False):
    """Supprime les colonnes obsolètes."""
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        # Vérifier quelles colonnes existent encore
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'user_learning_profiles'
              AND column_name = ANY(%s)
        """, (OBSOLETE_COLUMNS,))
        existing = [row[0] for row in cur.fetchall()]

        if not existing:
            print("✅ Aucune colonne obsolète à supprimer (déjà nettoyé)")
            return

        print(f"📋 Colonnes obsolètes trouvées : {existing}")

        if dry_run:
            for col in existing:
                print(f"   [DRY] ALTER TABLE user_learning_profiles DROP COLUMN {col};")
            print(f"\n[DRY RUN] {len(existing)} colonnes seraient supprimées")
            return

        for col in existing:
            cur.execute(f"ALTER TABLE user_learning_profiles DROP COLUMN IF EXISTS {col}")
            logger.info(f"Dropped column {col}")
            print(f"🗑️  Supprimé : {col}")

        # Supprimer les index GIN obsolètes
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'user_learning_profiles'
              AND indexname LIKE 'idx_%_gin'
        """)
        gin_indexes = [row[0] for row in cur.fetchall()]
        for idx in gin_indexes:
            cur.execute(f"DROP INDEX IF EXISTS {idx}")
            print(f"🗑️  Index supprimé : {idx}")

        conn.commit()
        print(f"\n✅ {len(existing)} colonnes supprimées, {len(gin_indexes)} index GIN supprimés")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    run(dry_run=dry_run)
