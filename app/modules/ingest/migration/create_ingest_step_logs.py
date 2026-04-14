"""
migration/create_ingest_step_logs.py
=====================================
Crée la table ingest_step_logs pour le tracking des étapes du pipeline ingest.

Usage :
    uv run python -m app.modules.ingest.migration.create_ingest_step_logs
"""
import logging

logger = logging.getLogger(__name__)


def run():
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingest_step_logs (
                id SERIAL PRIMARY KEY,
                document_id INTEGER,
                folder_path VARCHAR(500) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                current_step VARCHAR(30) NOT NULL DEFAULT 'pending',
                step_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                next_retry_at TIMESTAMP,
                extracted_metadata TEXT,
                extract_method VARCHAR(20),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        conn.commit()
        print("✅ Table ingest_step_logs créée")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingest_step_folder ON ingest_step_logs (folder_path, filename)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingest_step_status ON ingest_step_logs (step_status, next_retry_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingest_step_doc ON ingest_step_logs (document_id)")
        conn.commit()
        print("✅ Index créés")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
