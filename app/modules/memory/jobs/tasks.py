"""
jobs/tasks.py
=============
Celery tasks for the memory module.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.modules.memory.jobs.celery_app import celery_app
from app.modules.memory.services.memory_stats_service import MemoryStatsService
from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
from app.modules.memory.models import MemorySection, UserSectionProgress

logger = logging.getLogger(__name__)


def _get_db() -> Session:
    """Create a new DB session for use inside Celery tasks."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    return db


# -------------------------------------------------------------------
# Task: Generate memory items for a section
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_memory_items_task(self, document_id: int, section_title: str, texte_section: str, langue: str = "fr"):
    """Generate memory items for a document section via MemoryGeneratorService."""
    db = _get_db()
    try:
        from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
        service = MemoryGeneratorService(db=db)
        import asyncio
        result = asyncio.run(service.generer_pack_section(
            document_id=document_id,
            section_title=section_title,
            texte_section=texte_section,
            langue=langue,
        ))
        logger.info("Generated %d items for section '%s'", result.get("nb_items_generes", 0), section_title)
        return result
    except Exception as exc:
        logger.error("Failed to generate memory items: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Send review reminder to a single user
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def send_review_reminder_task(self, user_id: str, sections_due: list):
    """Send a review reminder notification to a user for due sections."""
    db = _get_db()
    try:
        try:
            from app.modules.notifications.services.notification_service import NotificationService
        except ImportError:
            logger.warning("NotificationService not available; skipping reminder for user %s", user_id)
            return {"status": "skipped", "reason": "NotificationService not available"}

        service = NotificationService(db=db)
        message = f"You have {len(sections_due)} section(s) to review today."
        notification = service.send_notification(
            user_id=user_id,
            notification_type="review_reminder",
            title="Time to Review!",
            message=message,
            data={"sections_due": sections_due},
        )
        logger.info("Sent review reminder to user %s", user_id)
        return {"status": "sent", "user_id": user_id, "notification_id": notification.id if notification else None}
    except Exception as exc:
        logger.error("Failed to send review reminder to user %s: %s", user_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Send daily review reminders to all users with due sections
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_daily_review_reminders_task(self):
    """Find users with due sections and send daily review reminders."""
    db = _get_db()
    try:
        now = datetime.now(timezone.utc)
        # Check anti-duplicate flag in Redis
        try:
            from redis import Redis
            from app.core.config import REDIS_URL
            redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
            today_key = f"memory:daily_reminder_sent:{now.strftime('%Y-%m-%d')}"
            if redis_client.exists(today_key):
                logger.info("Daily review reminders already sent today")
                return {"status": "skipped", "reason": "already_sent_today"}
        except Exception:
            logger.warning("Redis not available; proceeding without anti-duplicate check")
            redis_client = None

        # Find users with due sections
        rows = (
            db.query(UserSectionProgress.user_id)
            .filter(
                UserSectionProgress.is_completed.is_(True),
                UserSectionProgress.next_review_at.isnot(None),
                UserSectionProgress.next_review_at <= now,
            )
            .distinct()
            .all()
        )

        user_ids = [row[0] for row in rows]
        if not user_ids:
            logger.info("No users with due sections for daily reminder")
            return {"status": "no_due_sections"}

        sent_count = 0
        for user_id in user_ids:
            sections_due = (
                db.query(MemorySection)
                .join(UserSectionProgress, UserSectionProgress.section_id == MemorySection.id)
                .filter(
                    UserSectionProgress.user_id == user_id,
                    UserSectionProgress.next_review_at <= now,
                )
                .all()
            )
            send_review_reminder_task.delay(
                user_id=user_id,
                sections_due=[{"section_id": s.id, "title": s.section_title} for s in sections_due],
            )
            sent_count += 1

        # Set anti-duplicate flag (24h TTL)
        if redis_client:
            redis_client.setex(today_key, 86400, "1")

        logger.info("Queued daily review reminders for %d users", sent_count)
        return {"status": "queued", "users_count": sent_count}
    except Exception as exc:
        logger.error("Failed to send daily review reminders: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Regenerate weekly packs older than 7 days
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def regenerate_weekly_packs_task(self):
    """Regenerate memory packs older than 7 days."""
    db = _get_db()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        stale_sections = (
            db.query(MemorySection)
            .filter(
                MemorySection.generation_status == "complete",
                MemorySection.generated_at < cutoff,
            )
            .all()
        )

        if not stale_sections:
            logger.info("No stale packs to regenerate")
            return {"status": "no_stale_packs"}

        regenerated = 0
        for section in stale_sections:
            try:
                service = MemoryGeneratorService(db=db)
                import asyncio
                result = asyncio.run(service.regenerer_section(section_id=section.id, force=True))
                if result.get("nb_items_generes", 0) > 0:
                    regenerated += 1
                logger.info("Regenerated section %d: %d items", section.id, result.get("nb_items_generes", 0))
            except Exception as exc:
                logger.error("Failed to regenerate section %d: %s", section.id, exc)

        logger.info("Regenerated %d/%d stale packs", regenerated, len(stale_sections))
        return {"status": "done", "regenerated": regenerated, "total": len(stale_sections)}
    except Exception as exc:
        logger.error("Failed to regenerate weekly packs: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Update item difficulty from recent attempts
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def update_item_difficulty_task(self):
    """Recalculate item difficulty from recent attempts across all sections."""
    db = _get_db()
    try:
        service = MemoryStatsService(db=db)

        # Get all sections with attempts
        sections = (
            db.query(MemorySection.id)
            .join(UserSectionProgress, UserSectionProgress.section_id == MemorySection.id)
            .distinct()
            .all()
        )

        updated = 0
        for (section_id,) in sections:
            try:
                import asyncio
                asyncio.run(service.mettre_a_jour_difficulte_section(section_id))
                updated += 1
            except Exception as exc:
                logger.error("Failed to update difficulty for section %d: %s", section_id, exc)

        logger.info("Updated difficulty for %d sections", updated)
        return {"status": "done", "sections_updated": updated}
    except Exception as exc:
        logger.error("Failed to update item difficulty: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Extract global concept graph from documents (LLM-driven)
# -------------------------------------------------------------------
@celery_app.task(
    name="memory.tasks.extract_global_graph_from_documents",
    queue="heavy",
    bind=True,
    max_retries=3,
)
def extract_global_graph_from_documents_task(self, batch_size: int = 50):
    """
    Analyse les documents epreuves et construit le graphe cognitif global.
    One-shot au premier lancement, puis incremental (nouveaux docs uniquement).
    """
    db = _get_db()
    try:
        import json
        from app.modules.memory.services.concept_graph_service import ConceptGraphService
        from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
        from app.core.config import OPENROUTER_API_KEYS
        from app.modules.epreuves.models import Document
        from sqlalchemy import text

        # Documents deja analyses
        analyzed = db.execute(
            text(
                "SELECT DISTINCT CAST(context->>'document_id' AS INTEGER) "
                "FROM concept_graph WHERE source_type = 'document_analysis'"
            )
        ).fetchall()
        analyzed_doc_ids = {r[0] for r in analyzed if r[0]}

        docs = (
            db.query(Document)
            .filter(Document.is_validated == True)
            .limit(batch_size)
            .all()
        )
        if analyzed_doc_ids:
            docs = [d for d in docs if d.id not in analyzed_doc_ids]

        if not docs:
            logger.info("Aucun nouveau document a analyser pour le graphe global")
            return {"status": "no_new_documents", "analyzed": 0}

        logger.info(f"Analyse de {len(docs)} documents pour le graphe global...")

        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
        graph_svc = ConceptGraphService(db)

        total_edges = 0
        total_docs_analyzed = 0

        for doc in docs:
            try:
                content_preview = ""
                if hasattr(doc, 'texte_extrait') and doc.texte_extrait:
                    content_preview = doc.texte_extrait[:3000]
                else:
                    content_preview = f"{doc.nom_affiche or ''} | {doc.matiere or ''} | {doc.niveau or ''}"

                prompt = f"""Analyse ce document du programme scolaire camerounais et extrais les relations de prerequis implicites.

Document:
Titre: {doc.nom_affiche} | Matiere: {doc.matiere} | Niveau: {doc.niveau} | Serie: {doc.serie}
Contenu: {content_preview}

Retourne UNIQUEMENT un JSON valide avec cette structure :
{{
  "notions_principales": [
    {{"nom": "derivees", "profondeur": 4, "matiere": "Mathematiques"}}
  ],
  "pre_requis_detectes": [
    {{"source": "limites", "target": "derivees", "matiere": "Mathematiques", "confidence": 0.85}}
  ]
}}

Regles : profondeur 1-5, confidence 0.6-0.9, target = notion du document, source = prerequis implicite.
"""

                response = client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=1500,
                    response_format="json",
                )

                text = response.get("text", "").strip()
                if text.startswith("```"):
                    text = text.split("```", 2)[-2].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()

                result = json.loads(text)

                for notion in result.get("notions_principales", []):
                    graph_svc.add_edge(
                        user_id=None,
                        source=notion["nom"],
                        target=notion["nom"],
                        relation="EN_COURS",
                        confidence=1.0,
                        source_type="document_analysis",
                        matiere=notion.get("matiere", doc.matiere),
                        canonical_name=notion["nom"],
                        context=json.dumps({"document_id": doc.id, "profondeur": notion.get("profondeur")}),
                    )
                    total_edges += 1

                for rel in result.get("pre_requis_detectes", []):
                    graph_svc.add_edge(
                        user_id=None,
                        source=rel["source"],
                        target=rel["target"],
                        relation="PRE_REQUIS_DE",
                        confidence=rel.get("confidence", 0.7),
                        source_type="document_analysis",
                        matiere=rel.get("matiere", doc.matiere),
                        canonical_name=f"{rel['source']}_prereq_{rel['target']}",
                        context=json.dumps({"document_id": doc.id}),
                    )
                    total_edges += 1

                total_docs_analyzed += 1
            except Exception as e:
                logger.error(f"Erreur analyse document {doc.id}: {e}")
                continue

        db.commit()
        logger.info(f"Graphe global: {total_docs_analyzed} docs, {total_edges} aretes")
        return {"status": "done", "docs_analyzed": total_docs_analyzed, "edges_added": total_edges}

    except Exception as e:
        logger.error(f"Global graph extraction failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Validate/correct a global graph edge (admin action)
# -------------------------------------------------------------------
@celery_app.task(name="memory.tasks.validate_global_graph_edge", queue="default", bind=True)
def validate_global_graph_edge_task(self, edge_id: str, is_valid: bool, corrected_relation: str = None):
    """Validation manuelle d'une arete du graphe global."""
    db = _get_db()
    try:
        from sqlalchemy import text

        if not is_valid:
            db.execute(text("DELETE FROM concept_graph WHERE id = :eid AND user_id IS NULL"), {"eid": edge_id})
            action = "deleted"
        elif corrected_relation:
            db.execute(text("UPDATE concept_graph SET relation = :rel, confidence = 1.0, source_type = 'human_validated' WHERE id = :eid AND user_id IS NULL"), {"eid": edge_id, "rel": corrected_relation})
            action = "corrected"
        else:
            db.execute(text("UPDATE concept_graph SET confidence = LEAST(confidence + 0.2, 1.0), source_type = 'human_validated' WHERE id = :eid AND user_id IS NULL"), {"eid": edge_id})
            action = "validated"

        db.commit()
        return {"action": action, "edge_id": edge_id}
    except Exception as e:
        db.rollback()
        logger.error(f"Validation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Cleanup stale concept edges (low confidence, old)
# -------------------------------------------------------------------
@celery_app.task(name="memory.tasks.cleanup_stale_concept_edges", queue="cron", bind=True)
def cleanup_stale_concept_edges(self, days_to_keep: int = 90):
    """Supprime les aretes personnelles avec confiance faible et anciennes."""
    db = _get_db()
    try:
        from sqlalchemy import text
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        result = db.execute(
            text("""
                DELETE FROM concept_graph
                WHERE user_id IS NOT NULL
                  AND confidence < 0.4
                  AND source_type IN ('chat', 'inference')
                  AND created_at < :cutoff
            """),
            {"cutoff": cutoff},
        )
        db.commit()
        logger.info(f"Cleanup concept edges: {result.rowcount} stale edges removed")
        return {"deleted": result.rowcount}
    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup concept edges failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=3600)
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Extract concepts from chat -> enrich concept_graph
# -------------------------------------------------------------------
@celery_app.task(
    name="memory.tasks.extract_concepts_from_chat",
    queue="heavy",
    bind=True,
    max_retries=2,
)
def extract_concepts_from_chat_task(
    self, message_id: int, user_id: str, user_message: str, llm_response: str
):
    """Extrait entites et relations d'un echange chat -> enrichit le graphe cognitif."""
    db = _get_db()
    try:
        import json
        from app.modules.memory.services.concept_graph_service import ConceptGraphService
        from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
        from app.core.config import OPENROUTER_API_KEYS

        prompt = f"""Extrais les concepts educatifs et leurs relations de cet echange pedagogique.
Retourne UNIQUEMENT un JSON valide avec cette structure :

[
  {{"concept": "derivees", "matiere": "Mathematiques", "type": "notion"}},
  {{"source": "limites", "target": "derivees", "relation": "PRE_REQUIS_DE", "confidence": 0.9, "matiere": "Mathematiques"}}
]

Message utilisateur : {user_message[:500]}
Reponse IA : {llm_response[:1000]}
"""
        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
        response = client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
            response_format="json",
        )

        text = response.get("text", "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[-2].strip()
            if text.startswith("json"):
                text = text[4:].strip()

        extracted = json.loads(text)
        if not isinstance(extracted, list):
            return {"success": False, "reason": "invalid_json"}

        graph_svc = ConceptGraphService(db)
        inserted_concepts = 0
        inserted_edges = 0

        for item in extracted:
            if "source" in item and "target" in item:
                graph_svc.add_edge(
                    user_id=user_id,
                    source=item["source"],
                    target=item["target"],
                    relation=item.get("relation", "LIEN_FAIBLE"),
                    confidence=item.get("confidence", 0.5),
                    source_type="chat",
                    matiere=item.get("matiere"),
                    canonical_name=f"{item['source']}_prereq_{item['target']}",
                    context=json.dumps({"message_id": message_id}),
                )
                inserted_edges += 1
            elif "concept" in item:
                graph_svc.add_edge(
                    user_id=user_id,
                    source=item["concept"],
                    target=item["concept"],
                    relation="EN_COURS",
                    confidence=0.3,
                    source_type="chat",
                    matiere=item.get("matiere"),
                    canonical_name=item["concept"],
                    context=json.dumps({"message_id": message_id}),
                )
                inserted_concepts += 1

        db.commit()
        return {"success": True, "concepts": inserted_concepts, "edges": inserted_edges}

    except Exception as e:
        logger.error(f"Extraction concepts failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()
