"""
migration/add_canonical_name_column.py
======================================
Ajoute la colonne canonical_name à concept_graph pour la déduplication sémantique.

Usage :
    uv run python -m app.modules.memory.migration.add_canonical_name_column
"""
import logging

logger = logging.getLogger(__name__)


def run():
    """Ajoute la colonne canonical_name et initialise les valeurs existantes."""
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        # Vérifier si la colonne existe déjà
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'concept_graph' AND column_name = 'canonical_name'
        """)
        if cur.fetchone():
            print("✅ Colonne canonical_name déjà existante")
        else:
            cur.execute("ALTER TABLE concept_graph ADD COLUMN canonical_name VARCHAR(200)")
            cur.execute("CREATE INDEX idx_cg_canonical ON concept_graph (canonical_name)")
            conn.commit()
            print("✅ Colonne canonical_name ajoutée")

        # Initialiser canonical_name = source pour les arêtes existantes sans canonical
        cur.execute("""
            UPDATE concept_graph
            SET canonical_name = source
            WHERE canonical_name IS NULL
        """)
        updated = cur.rowcount
        conn.commit()

        if updated > 0:
            print(f"✅ {updated} arêtes initialisées avec canonical_name = source")
        else:
            print("ℹ️  Aucune arête à initialiser")

        # Élargir source_type pour accueillir les nouvelles valeurs
        cur.execute("""
            SELECT data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'concept_graph' AND column_name = 'source_type'
        """)
        row = cur.fetchone()
        if row and row[1] and row[1] < 30:
            cur.execute("ALTER TABLE concept_graph ALTER COLUMN source_type TYPE VARCHAR(30)")
            conn.commit()
            print("✅ source_type élargi à VARCHAR(30)")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
