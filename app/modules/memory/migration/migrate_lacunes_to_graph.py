"""
migration/migrate_lacunes_to_graph.py
=====================================
Migre les lacunes existantes des quiz_sessions et user_learning_profiles
vers la table concept_graph.

Usage :
    uv run python -m app.modules.memory.migration.migrate_lacunes_to_graph [--dry-run]
"""
import logging
import uuid

logger = logging.getLogger(__name__)


def migrate(dry_run: bool = False):
    """Migre les données cognitives existantes vers concept_graph.

    Sources de migration :
    1. QuizSession.lacunes_detectees (score < 50% → A_ECHOUE_SUR)
    2. QuizSession (score >= 75% → MAITRISE)
    3. UserLearningProfile.lacunes (JSONB dict → A_ECHOUE_SUR)
    4. UserLearningProfile.forces (JSONB dict → MAITRISE)

    Args:
        dry_run: Si True, affiche ce qui serait migré sans modifier la DB.
    """
    from app.core.config import DATABASE_URL
    import psycopg2
    import json

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    total_inserted = 0
    total_skipped = 0
    errors = []

    try:
        # ─── 1. QuizSession.lacunes_detectees → A_ECHOUE_SUR ────────
        logger.info("Migration QuizSession.lacunes_detectees...")
        print("\n📋 Migration QuizSession.lacunes_detectees → A_ECHOUE_SUR")

        cur.execute("""
            SELECT qs.id, qs.user_id, qs.matiere, qs.score_percent, qs.lacunes_detectees
            FROM quiz_sessions qs
            WHERE qs.lacunes_detectees IS NOT NULL
              AND qs.submitted_at IS NOT NULL
            ORDER BY qs.submitted_at DESC
        """)
        quiz_rows = cur.fetchall()
        print(f"   {len(quiz_rows)} quiz sessions avec lacunes détectées")

        for quiz_id, user_id, matiere, score, lacunes_json in quiz_rows:
            if not lacunes_json:
                continue

            # Si score < 50% → A_ECHOUE_SUR pour chaque notion
            if score is not None and score < 50:
                for lacune in lacunes_json:
                    notion = lacune.get("notion") if isinstance(lacune, dict) else None
                    if not notion:
                        continue
                    nb_erreurs = lacune.get("erreurs", 1) if isinstance(lacune, dict) else 1
                    confidence = min(nb_erreurs * 0.2, 1.0)

                    if dry_run:
                        print(f"   [DRY] {user_id} A_ECHOUE_SUR {notion} (matiere={matiere}, conf={confidence:.2f})")
                        total_inserted += 1
                    else:
                        cur.execute("""
                            INSERT INTO concept_graph (id, user_id, source, target, relation,
                                confidence, source_type, matiere, context, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, 'A_ECHOUE_SUR', %s, 'migration', %s, %s, NOW(), NOW())
                            ON CONFLICT (user_id, source, target, relation) DO NOTHING
                        """, (
                            str(uuid.uuid4()), str(user_id), notion, notion,
                            confidence, matiere or "unknown", f"QuizSession {quiz_id}"
                        ))
                        if cur.rowcount > 0:
                            total_inserted += 1
                        else:
                            total_skipped += 1

            # Si score >= 75% → MAITRISE
            if score is not None and score >= 75 and matiere:
                if dry_run:
                    print(f"   [DRY] {user_id} MAITRISE {matiere} (score={score})")
                    total_inserted += 1
                else:
                    cur.execute("""
                        INSERT INTO concept_graph (id, user_id, source, target, relation,
                            confidence, source_type, matiere, context, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, 'MAITRISE', %s, 'migration', %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, source, target, relation) DO NOTHING
                    """, (
                        str(uuid.uuid4()), str(user_id), matiere, matiere,
                        score / 100.0, matiere, f"QuizSession {quiz_id}"
                    ))
                    if cur.rowcount > 0:
                        total_inserted += 1
                    else:
                        total_skipped += 1

        # ─── 2. UserLearningProfile.lacunes → A_ECHOUE_SUR ──────────
        logger.info("Migration UserLearningProfile.lacunes...")
        print("\n📋 Migration UserLearningProfile.lacunes → A_ECHOUE_SUR")

        cur.execute("""
            SELECT ulp.user_id, ulp.lacunes
            FROM user_learning_profiles ulp
            WHERE ulp.lacunes IS NOT NULL AND ulp.lacunes != '{}'
        """)
        profile_rows = cur.fetchall()
        print(f"   {len(profile_rows)} profils avec lacunes JSONB")

        for user_id, lacunes_json in profile_rows:
            if not lacunes_json:
                continue

            for matiere, notions in lacunes_json.items():
                if not isinstance(notions, list):
                    continue
                for notion in notions:
                    if dry_run:
                        print(f"   [DRY] {user_id} A_ECHOUE_SUR {notion} (matiere={matiere})")
                        total_inserted += 1
                    else:
                        cur.execute("""
                            INSERT INTO concept_graph (id, user_id, source, target, relation,
                                confidence, source_type, matiere, context, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, 'A_ECHOUE_SUR', 0.7, 'migration', %s, %s, NOW(), NOW())
                            ON CONFLICT (user_id, source, target, relation) DO NOTHING
                        """, (
                            str(uuid.uuid4()), str(user_id), notion, notion,
                            matiere, f"UserLearningProfile.lacunes"
                        ))
                        if cur.rowcount > 0:
                            total_inserted += 1
                        else:
                            total_skipped += 1

        # ─── 3. UserLearningProfile.forces → MAITRISE ───────────────
        logger.info("Migration UserLearningProfile.forces...")
        print("\n📋 Migration UserLearningProfile.forces → MAITRISE")

        cur.execute("""
            SELECT ulp.user_id, ulp.forces
            FROM user_learning_profiles ulp
            WHERE ulp.forces IS NOT NULL AND ulp.forces != '{}'
        """)
        forces_rows = cur.fetchall()
        print(f"   {len(forces_rows)} profils avec forces JSONB")

        for user_id, forces_json in forces_rows:
            if not forces_json:
                continue

            for matiere, data in forces_json.items():
                score = data.get("score", 75) if isinstance(data, dict) else 75
                if dry_run:
                    print(f"   [DRY] {user_id} MAITRISE {matiere} (score={score})")
                    total_inserted += 1
                else:
                    cur.execute("""
                        INSERT INTO concept_graph (id, user_id, source, target, relation,
                            confidence, source_type, matiere, context, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, 'MAITRISE', %s, 'migration', %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, source, target, relation) DO NOTHING
                    """, (
                        str(uuid.uuid4()), str(user_id), matiere, matiere,
                        min(score / 100.0, 1.0), matiere, f"UserLearningProfile.forces"
                    ))
                    if cur.rowcount > 0:
                        total_inserted += 1
                    else:
                        total_skipped += 1

        if not dry_run:
            conn.commit()

        print(f"\n{'[DRY RUN] ' if dry_run else ''}✅ Migration terminée : {total_inserted} arêtes insérées, {total_skipped} ignorées (déjà existantes)")
        if errors:
            print(f"⚠️  {len(errors)} erreurs : {errors[:5]}")

    except Exception as e:
        if not dry_run:
            conn.rollback()
        logger.error(f"Erreur lors de la migration : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
