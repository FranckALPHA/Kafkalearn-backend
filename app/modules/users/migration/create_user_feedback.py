"""
migration/create_user_feedback.py
==================================
Crée la table user_feedback via SQL pur.
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
            CREATE TABLE IF NOT EXISTS user_feedback (
                id SERIAL PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                feedback_type VARCHAR(30) NOT NULL,
                rating FLOAT,
                comment TEXT,
                related_entity_type VARCHAR(30),
                related_entity_id INTEGER,
                matiere VARCHAR(100),
                concept VARCHAR(200),
                action_taken VARCHAR(50),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT chk_feedback_rating_range CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)
            )
        """)
        conn.commit()
        print("✅ Table user_feedback créée")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_user ON user_feedback (user_id, created_at)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_type ON user_feedback (feedback_type)
        """)
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
