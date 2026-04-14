"""
scripts/create_superadmin.py
=============================
Crée le superadmin par défaut si il n'existe pas.
Utilise les variables SUPERADMIN_EMAIL et SUPERADMIN_PASSWORD du .env.
"""
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def _hash_password_argon2(password: str) -> str:
    """Hash un mot de passe avec Argon2."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    return ph.hash(password)


def create_superadmin():
    """Crée le superadmin par défaut si il n'existe pas."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

    email = os.getenv("SUPERADMIN_EMAIL", "superadmin@kafkalearn.cm")
    password = os.getenv("SUPERADMIN_PASSWORD", "KafkaLearn@2026!")

    # Utiliser psycopg2 directement pour éviter les problèmes SQLAlchemy
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, email, role FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()
        if existing:
            user_id, user_email, user_role = existing
            if user_role != "superadmin":
                cur.execute("UPDATE users SET role = 'superadmin', is_active = true WHERE id = %s", (user_id,))
                conn.commit()
                logger.info(f"🔄 Utilisateur existant promu superadmin : {email}")
            else:
                logger.info(f"✅ Superadmin déjà existant : {email}")
            return

        # Créer le superadmin
        user_id = str(uuid.uuid4())
        password_hash = _hash_password_argon2(password)
        now = "NOW()"

        cur.execute("""
            INSERT INTO users (
                id, email, password_hash, prenom, nom, langue, role,
                plan_base, plan_effectif, is_active, email_verified,
                referral_code, streak_jours, score_global, onboarding_completed,
                is_deleted, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, email, password_hash,
            "Super", "Admin", "fr", "superadmin",
            "unlimited", "unlimited", True, True,
            "SUPERADMIN", 0, 0.0, True,
            False, now, now
        ))
        conn.commit()
        logger.info(f"✅ Superadmin créé : {email}")
        print(f"\n{'='*60}")
        print(f"  Superadmin créé avec succès")
        print(f"  Email : {email}")
        print(f"  Mot de passe : {password}")
        print(f"  Rôle : superadmin")
        print(f"  Plan : unlimited")
        print(f"{'='*60}\n")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur création superadmin : {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_superadmin()
