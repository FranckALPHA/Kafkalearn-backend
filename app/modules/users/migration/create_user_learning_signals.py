"""
migration/create_user_learning_signals.py
==========================================
Crée la table user_learning_signals via SQL (contourne le bug DailyQuizAttempt du User model).
"""
import logging

logger = logging.getLogger(__name__)


def run():
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        # Créer la table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_learning_signals (
                id SERIAL PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                temporal_signals JSONB DEFAULT '{}',
                behavioral_signals JSONB DEFAULT '{}',
                cognitive_signals JSONB DEFAULT '{}',
                contextual_signals JSONB DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uls_user_unique UNIQUE (user_id)
            )
        """)
        conn.commit()
        print("✅ Table user_learning_signals créée")

        # Index
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_uls_user ON user_learning_signals (user_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_uls_temporal_gin ON user_learning_signals
            USING gin (temporal_signals)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_uls_cognitive_gin ON user_learning_signals
            USING gin (cognitive_signals)
        """)
        conn.commit()
        print("✅ Index créés")

        # Initialiser pour les utilisateurs existants
        cur.execute("""
            INSERT INTO user_learning_signals (user_id, created_at, updated_at)
            SELECT id, NOW(), NOW() FROM users
            WHERE id NOT IN (SELECT user_id FROM user_learning_signals)
        """)
        created = cur.rowcount
        conn.commit()
        if created > 0:
            print(f"✅ {created} profils de signaux initialisés")
        else:
            print("ℹ️  Profils déjà initialisés")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
