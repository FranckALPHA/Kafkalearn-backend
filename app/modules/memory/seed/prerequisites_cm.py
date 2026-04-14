"""
seed/prerequisites_cm.py
========================
Seed manuel du graphe de prérequis du programme scolaire camerounais.
Couche GLOBALE (user_id = NULL) — partagé par tous les utilisateurs.

Utilise SQL raw pour contourner les bugs SQLAlchemy du model User.

Usage :
    uv run python -m app.modules.memory.seed.prerequisites_cm [--force]
"""
import logging
import uuid

logger = logging.getLogger(__name__)

# Prérequis globaux — programme camerounais
# (source, target, relation, matiere)
GLOBAL_EDGES = [
    # ─── Mathématiques ──────────────────────────────────────────
    ("arithmetique", "equations", "PRE_REQUIS_DE", "Mathematiques"),
    ("equations", "fonctions", "PRE_REQUIS_DE", "Mathematiques"),
    ("fonctions", "limites", "PRE_REQUIS_DE", "Mathematiques"),
    ("limites", "continuite", "PRE_REQUIS_DE", "Mathematiques"),
    ("limites", "derivees", "PRE_REQUIS_DE", "Mathematiques"),
    ("derivees", "integrales", "PRE_REQUIS_DE", "Mathematiques"),
    ("derivees", "etude_fonctions", "PRE_REQUIS_DE", "Mathematiques"),
    ("derivees", "optimisation", "PRE_REQUIS_DE", "Mathematiques"),
    ("integrales", "equations_differentielles", "PRE_REQUIS_DE", "Mathematiques"),
    ("suites", "series", "PRE_REQUIS_DE", "Mathematiques"),
    ("trigonometrie", "nombres_complexes", "PRE_REQUIS_DE", "Mathematiques"),
    ("probabilites", "statistiques", "PRE_REQUIS_DE", "Mathematiques"),

    # ─── Physique ───────────────────────────────────────────────
    ("forces", "mouvement", "PRE_REQUIS_DE", "Physique"),
    ("mouvement", "energie_cinetique", "PRE_REQUIS_DE", "Physique"),
    ("energie_cinetique", "travail_mecanique", "PRE_REQUIS_DE", "Physique"),
    ("energie_cinetique", "conservation_energie", "PRE_REQUIS_DE", "Physique"),
    ("electricite_base", "courant_continu", "PRE_REQUIS_DE", "Physique"),
    ("courant_continu", "circuits_electriques", "PRE_REQUIS_DE", "Physique"),
    ("magnetisme", "induction_electromagnetique", "PRE_REQUIS_DE", "Physique"),
    ("ondes_mecaniques", "ondes_lumineuses", "PRE_REQUIS_DE", "Physique"),
    ("optique_geometrique", "optique_ondulatoire", "PRE_REQUIS_DE", "Physique"),
    ("thermodynamique", "gaz_parfaits", "PRE_REQUIS_DE", "Physique"),

    # ─── SVT (Sciences de la Vie et de la Terre) ────────────────
    ("cellule", "adn", "PRE_REQUIS_DE", "SVT"),
    ("adn", "genetique", "PRE_REQUIS_DE", "SVT"),
    ("genetique", "evolution", "PRE_REQUIS_DE", "SVT"),
    ("genetique", "biotechnologie", "PRE_REQUIS_DE", "SVT"),
    ("photosynthese", "respiration_cellulaire", "PRE_REQUIS_DE", "SVT"),
    ("reproduction", "heredite", "PRE_REQUIS_DE", "SVT"),
    ("immunite", "pathologies", "PRE_REQUIS_DE", "SVT"),
    ("ecologie_base", "ecosystemes", "PRE_REQUIS_DE", "SVT"),
    ("ecosystemes", "biodiversite", "PRE_REQUIS_DE", "SVT"),

    # ─── Chimie ─────────────────────────────────────────────────
    ("atome", "liaison_chimique", "PRE_REQUIS_DE", "Chimie"),
    ("liaison_chimique", "reactions", "PRE_REQUIS_DE", "Chimie"),
    ("reactions", "cinetique_chimique", "PRE_REQUIS_DE", "Chimie"),
    ("reactions", "equilibre_chimique", "PRE_REQUIS_DE", "Chimie"),
    ("acide_base", "ph", "PRE_REQUIS_DE", "Chimie"),
    ("acide_base", "dosage", "PRE_REQUIS_DE", "Chimie"),
    ("oxydoreduction", "electrochimie", "PRE_REQUIS_DE", "Chimie"),
    ("chimie_organique_base", "alcanes", "PRE_REQUIS_DE", "Chimie"),
    ("alcanes", "alcools", "PRE_REQUIS_DE", "Chimie"),
    ("alcools", "acides_carboxyliques", "PRE_REQUIS_DE", "Chimie"),

    # ─── Français ───────────────────────────────────────────────
    ("grammaire_base", "conjugaison", "PRE_REQUIS_DE", "Francais"),
    ("conjugaison", "expression_ecrite", "PRE_REQUIS_DE", "Francais"),
    ("vocabulaire", "expression_ecrite", "PRE_REQUIS_DE", "Francais"),
    ("lecture_analyse", "dissertation", "PRE_REQUIS_DE", "Francais"),
    ("dissertation", "commentaire_litteraire", "PRE_REQUIS_DE", "Francais"),

    # ─── Anglais ────────────────────────────────────────────────
    ("grammar_base", "tenses", "PRE_REQUIS_DE", "Anglais"),
    ("tenses", "conditional", "PRE_REQUIS_DE", "Anglais"),
    ("tenses", "passive_voice", "PRE_REQUIS_DE", "Anglais"),
    ("vocabulary_base", "essay_writing", "PRE_REQUIS_DE", "Anglais"),
    ("reading_comprehension", "essay_writing", "PRE_REQUIS_DE", "Anglais"),

    # ─── Philosophie ────────────────────────────────────────────
    ("conscience", "liberte", "PRE_REQUIS_DE", "Philosophie"),
    ("liberte", "responsabilite", "PRE_REQUIS_DE", "Philosophie"),
    ("raison", "verite", "PRE_REQUIS_DE", "Philosophie"),
    ("ethique", "bonheur", "PRE_REQUIS_DE", "Philosophie"),
    ("politique", "justice", "PRE_REQUIS_DE", "Philosophie"),

    # ─── Histoire-Géographie ────────────────────────────────────
    ("colonisation", "independances", "PRE_REQUIS_DE", "Histoire"),
    ("independances", "construction_etatique", "PRE_REQUIS_DE", "Histoire"),
    ("geographie_physique", "geographie_humaine", "PRE_REQUIS_DE", "Geographie"),
    ("cartographie", "geopolitique", "PRE_REQUIS_DE", "Geographie"),

    # ─── Informatique ───────────────────────────────────────────
    ("algorithmes", "programmation", "PRE_REQUIS_DE", "Informatique"),
    ("programmation", "bases_de_donnees", "PRE_REQUIS_DE", "Informatique"),
    ("programmation", "web", "PRE_REQUIS_DE", "Informatique"),
    ("reseaux_base", "internet", "PRE_REQUIS_DE", "Informatique"),
]


def seed(force: bool = False):
    """Insère les prérequis globaux dans concept_graph via SQL raw.

    Args:
        force: Si True, supprime les arêtes globales existantes avant de reseeder.
    """
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        if force:
            cur.execute("DELETE FROM concept_graph WHERE user_id IS NULL")
            deleted = cur.rowcount
            conn.commit()
            logger.info(f"Supprimé {deleted} arêtes globales existantes")
            print(f"🗑️  Supprimé {deleted} arêtes globales existantes")

        inserted = 0
        skipped = 0

        for source, target, relation, matiere in GLOBAL_EDGES:
            # Vérifier si l'arête existe déjà
            cur.execute("""
                SELECT 1 FROM concept_graph
                WHERE user_id IS NULL
                  AND source = %s AND target = %s AND relation = %s
                LIMIT 1
            """, (source, target, relation))

            if cur.fetchone():
                skipped += 1
                continue

            cur.execute("""
                INSERT INTO concept_graph (
                    id, user_id, source, target, relation,
                    confidence, source_type, matiere, context,
                    created_at, updated_at
                ) VALUES (%s, NULL, %s, %s, %s, 1.0, 'manual', %s, %s, NOW(), NOW())
            """, (
                str(uuid.uuid4()),
                source, target, relation,
                matiere,
                "Programme scolaire camerounais — seed manuel",
            ))
            inserted += 1

        conn.commit()
        logger.info(f"Seed terminé : {inserted} arêtes insérées, {skipped} ignorées")
        print(f"✅ Seed concept_graph global : {inserted} arêtes insérées, {skipped} ignorées (déjà existantes)")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors du seed : {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    seed(force=force)
