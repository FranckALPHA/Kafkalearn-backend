"""
jobs/ingest_folder_tasks.py
============================
Tâches Celery pour l'ingestion locale de dossiers de documents PDF.

Pipeline à étapes avec blocage + retry cron :
  Step 1: text_extract   → PDF natif ou OCR local
  Step 2: metadata_parse → Filename → fallback LLM
  Step 3: db_insert      → INSERT documents
  Step 4: memory_queue   → flashcards/QCM (uniquement leçons/cours)

Si une étape échoue → document bloqué → retry par cron.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.modules.ingest.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.core.database import SessionLocal
    return SessionLocal()


# ─── Helpers ───────────────────────────────────────────────────────

def _get_or_create_step_log(db, folder_path: str, filename: str, step: str, doc_id=None):
    """Récupère ou crée un step log pour un document."""
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT id, document_id, current_step, step_status, retry_count, max_retries, next_retry_at,
               extracted_metadata, extract_method, error_message
        FROM ingest_step_logs
        WHERE folder_path = :fp AND filename = :fn AND current_step = :step
        ORDER BY id DESC LIMIT 1
    """), {"fp": folder_path, "fn": filename, "step": step}).fetchone()
    return row


def _update_step_log(db, log_id: int, status: str, error: str = None, doc_id: int = None,
                     metadata: str = None, method: str = None, next_step: str = None):
    """Met à jour un step log."""
    from sqlalchemy import text
    db.execute(text("""
        UPDATE ingest_step_logs
        SET step_status = :status,
            error_message = :error,
            document_id = COALESCE(:doc_id, document_id),
            extracted_metadata = COALESCE(:metadata, extracted_metadata),
            extract_method = COALESCE(:method, extract_method),
            current_step = COALESCE(:next_step, current_step),
            updated_at = NOW()
        WHERE id = :log_id
    """), {
        "status": status, "error": error, "doc_id": doc_id,
        "metadata": metadata, "method": method, "next_step": next_step,
        "log_id": log_id
    })
    db.commit()


def _create_step_log(db, folder_path: str, filename: str, step: str, status: str = "running"):
    """Crée un nouveau step log."""
    from sqlalchemy import text
    result = db.execute(text("""
        INSERT INTO ingest_step_logs (folder_path, filename, current_step, step_status, created_at, updated_at)
        VALUES (:fp, :fn, :step, :status, NOW(), NOW())
        RETURNING id
    """), {"fp": folder_path, "fn": filename, "step": step, "status": status})
    log_id = result.fetchone()[0]
    db.commit()
    return log_id


def _set_blocked(db, log_id: int, error: str, retry_count: int, max_retries: int):
    """Bloque un document à une étape avec prochain retry."""
    from sqlalchemy import text
    next_retry = datetime.now(timezone.utc) + timedelta(minutes=5 * (retry_count + 1))
    db.execute(text("""
        UPDATE ingest_step_logs
        SET step_status = 'blocked',
            error_message = :error,
            retry_count = :rc,
            next_retry_at = :next_retry,
            updated_at = NOW()
        WHERE id = :log_id
    """), {"error": error[:500], "rc": retry_count, "next_retry": next_retry, "log_id": log_id})
    db.commit()


# ─── Extract text ──────────────────────────────────────────────────

def _extract_text_native(pdf_path: str) -> str:
    """Extrait le texte d'un PDF natif."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n\n".join(text_parts)
    except (ImportError, Exception):
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n\n".join(text_parts)
    except (ImportError, Exception):
        pass

    return ""


def _extract_text_ocr(pdf_path: str) -> str:
    """OCR local pour PDF scannés."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(pdf_path, dpi=200)
        text_parts = []
        for img in images:
            text_parts.append(pytesseract.image_to_string(img, lang='fra'))
        return "\n\n".join(text_parts)
    except (ImportError, Exception):
        return ""


def _extract_text(pdf_path: str):
    """Extract text: native → OCR → none."""
    texte = _extract_text_native(pdf_path)
    if texte and len(texte.strip()) > 50:
        return texte, "native"
    texte = _extract_text_ocr(pdf_path)
    if texte and len(texte.strip()) > 50:
        return texte, "ocr"
    return "", "none"


# ─── Parse metadata filename ──────────────────────────────────────

def _parse_filename(filename: str) -> dict:
    """Parse metadata depuis le nom du fichier."""
    import json
    ref_path = Path(__file__).parent.parent / "utils" / "metadata_ref.json"
    with open(ref_path, "r", encoding="utf-8") as f:
        ref = json.load(f)

    parts = filename.replace(".pdf", "").replace(".docx", "").split("_")
    if len(parts) < 2:
        return None  # Pas assez d'infos

    result = {
        "matiere": parts[0],
        "notion": parts[1] if len(parts) > 1 else "",
        "niveau": "",
        "serie": "",
        "annee": 2024,
    }

    aliases = ref.get("alias_niveaux", {})
    valid_matieres = ref.get("matieres", [])
    alias_matieres = ref.get("alias_matieres", {})

    for p in parts[2:] if len(parts) > 2 else parts[1:]:
        p_lower = p.lower().strip()
        if p_lower in aliases:
            result["niveau"] = aliases[p_lower]
        elif p_lower.replace(" ", "") in aliases:
            result["niveau"] = aliases[p_lower.replace(" ", "")]

    # Normalize matiere
    m_lower = result["matiere"].lower().strip()
    if m_lower in alias_matieres:
        result["matiere"] = alias_matieres[m_lower]
    else:
        for v in valid_matieres:
            if v.lower() == m_lower or v.lower().startswith(m_lower):
                result["matiere"] = v
                break

    # Validate niveau
    valid_niveaux = ref.get("niveaux", [])
    if result["niveau"] and result["niveau"] not in valid_niveaux:
        result["niveau"] = ""

    return result


# ─── Main Celery Task ─────────────────────────────────────────────

@celery_app.task(
    name="ingest.tasks.ingest_folder_task",
    queue="heavy",
    bind=True,
    max_retries=2,
)
def ingest_folder_task(self, folder_path: str, uploaded_by: str, force: bool = False):
    """
    Scanne un dossier local, ingère les PDFs, puis nettoie le dossier source.

    Pipeline :
    1. Supprime les fichiers non-PDF du dossier source
    2. Pour chaque PDF : extraction texte → metadata → DB → memory queue
    3. Renomme les PDFs indexés et les déplace vers le dossier d'archive
    4. Vide et supprime le dossier source
    """
    from app.core.config import DATABASE_URL
    import psycopg2
    import asyncio
    import shutil
    from datetime import datetime

    folder = Path(folder_path)
    if not folder.exists():
        return {"status": "error", "reason": f"Folder not found: {folder_path}"}

    # ═══ PHASE 0 : Nettoyage du dossier source (supprime non-PDF) ═══
    non_pdf_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() != '.pdf']
    non_pdf_count = len(non_pdf_files)
    for f in non_pdf_files:
        try:
            f.unlink()
            logger.info(f"🗑️  Supprimé (non-PDF) : {f.name}")
        except Exception as e:
            logger.warning(f"⚠️  Impossible de supprimer {f.name}: {e}")

    pdf_files = list(folder.glob("*.pdf"))
    if not pdf_files:
        # Dossier vide ou plus de PDFs → supprimer le dossier
        try:
            folder.rmdir()
            logger.info(f"📁 Dossier source supprimé (vide) : {folder_path}")
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
        return {"status": "no_pdfs", "non_pdf_removed": non_pdf_count}

    logger.info(f"📁 {len(pdf_files)} PDFs à ingérer dans {folder_path} ({non_pdf_count} fichiers non-PDF supprimés)")

    # Dossier d'archive pour les PDFs traités
    archive_base = Path("/home/franckalpha/Bureau/Kafkalearn/backend/data/ingest_archive")
    archive_base.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_archive = archive_base / run_id
    run_archive.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    results = {
        "ingested": 0, "skipped": 0, "errors": 0, "blocked": 0,
        "memory_queued": 0, "ocr_count": 0, "non_pdf_removed": non_pdf_count,
        "archived": 0,
    }

    archived_files = []

    for pdf_file in pdf_files:
        try:
            with open(pdf_file, "rb") as f:
                file_bytes = f.read()

            content_hash = hashlib.sha256(file_bytes).hexdigest()

            # Check duplicate
            cur.execute("SELECT id FROM documents WHERE hash_contenu = %s", (content_hash,))
            existing = cur.fetchone()
            if existing and not force:
                logger.info(f"⏭️  Skip (déjà) : {pdf_file.name}")
                results["skipped"] += 1
                continue

            # ═══ STEP 1: Text extraction ═══
            log_id = _create_step_log(cur, folder_path, pdf_file.name, "text_extract")
            texte, methode = _extract_text(str(pdf_file))

            if methode == "ocr":
                results["ocr_count"] += 1
                logger.info(f"📸 OCR utilisé pour {pdf_file.name}")
            elif methode == "none":
                _set_blocked(cur, log_id, "No text extracted (not native, OCR failed)", 0, 3)
                results["blocked"] += 1
                conn.rollback()
                continue

            _update_step_log(cur, log_id, "completed", next_step="metadata_parse", doc_id=None)
            conn.commit()

            # ═══ STEP 2: Metadata parsing ═══
            log_id = _create_step_log(cur, folder_path, pdf_file.name, "metadata_parse")
            meta = _parse_filename(pdf_file.name)

            extract_method = "filename"
            if meta is None or (meta.get("niveau", "") == "" and meta.get("matiere", "") == "Autre"):
                # Fallback LLM
                logger.info(f"🤖 LLM metadata fallback pour {pdf_file.name}")
                meta_llm = asyncio.run(_call_llm_metadata(texte, pdf_file.name))
                if meta_llm and meta_llm.get("confidence", 0) > 0.5:
                    meta = meta_llm
                    extract_method = "llm"
                else:
                    _set_blocked(cur, log_id, "LLM metadata extraction failed", 0, 3)
                    results["blocked"] += 1
                    conn.rollback()
                    continue

            metadata_json = json.dumps(meta, ensure_ascii=False)
            _update_step_log(cur, log_id, "completed", metadata=metadata_json,
                           method=extract_method, next_step="db_insert")
            conn.commit()

            # ═══ STEP 3: DB insert ═══
            log_id = _create_step_log(cur, folder_path, pdf_file.name, "db_insert")
            try:
                niveau = meta.get("niveau", "")
                matiere = meta.get('matiere', 'Autre')

                # Nom final : {matiere}_{niveau}_{notion}_{hash[:8]}.pdf
                notion = (meta.get('notion_principale') or meta.get('notion') or 'document')[:30]
                final_name = f"{matiere}_{niveau}_{notion}_{content_hash[:8]}.pdf"
                final_name = final_name.replace(" ", "_").replace("/", "_")

                chemin_final = f"{matiere}/{niveau}/{final_name}" if niveau else f"{matiere}/{final_name}"

                cur.execute("""
                    INSERT INTO documents (
                        nom_original, nom_affiche, chemin_final, mimetype, poids_octets,
                        hash_contenu, matiere, niveau, serie, annee, type_doc, langue,
                        is_embedded, is_validated, ingest_status, texte_extrait,
                        notion_principale,
                        nb_vues, nb_telechargements, nb_favoris, nb_tentatives_ia,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id
                """, (
                    pdf_file.name, final_name, chemin_final, 'application/pdf', len(file_bytes),
                    content_hash, matiere, niveau,
                    meta.get('serie') or None, meta.get('annee', 2024),
                    meta.get('type_doc', 'epreuve'), 'fr',
                    False, True, 'completed', texte[:50000] if texte else None,
                    notion[:200],
                    0, 0, 0, 0
                ))
                doc_id = cur.fetchone()[0]
                conn.commit()

                _update_step_log(cur, log_id, "completed", doc_id=doc_id, next_step="memory_queue")
                conn.commit()

                logger.info(f"✅ Document {doc_id}: {final_name} ({matiere} {niveau}) [{methode}]")
                results["ingested"] += 1

                # ═══ Archiver le PDF traité ═══
                archive_dest = run_archive / final_name
                shutil.copy2(str(pdf_file), str(archive_dest))
                archived_files.append((pdf_file, archive_dest))
                results["archived"] += 1

            except Exception as e:
                _set_blocked(cur, log_id, f"DB insert failed: {e}", 0, 3)
                results["blocked"] += 1
                conn.rollback()
                continue

            # ═══ STEP 4: Memory queue (uniquement lecons/cours) ═══
            log_id = _create_step_log(cur, folder_path, pdf_file.name, "memory_queue")
            type_doc = meta.get("type_doc", "epreuve")
            if type_doc in ("lecon", "cours", "resume") and texte and len(texte) > 100:
                try:
                    from app.modules.memory.jobs.tasks import generate_memory_items_task
                    generate_memory_items_task.delay(
                        document_id=doc_id,
                        section_title=meta.get('notion_principale') or meta.get('notion') or "Contenu principal",
                        texte_section=texte[:5000],
                        langue="fr",
                    )
                    results["memory_queued"] += 1
                    _update_step_log(cur, log_id, "completed", doc_id=doc_id, next_step="done")
                    logger.info(f"   📝 Memory generation queued")
                except Exception as e:
                    _update_step_log(cur, log_id, "completed", doc_id=doc_id,
                                   error=f"Memory queue failed: {e}", next_step="done")
                    logger.warning(f"   ⚠️  Memory queue failed: {e}")
            else:
                _update_step_log(cur, log_id, "completed", doc_id=doc_id,
                               next_step="done", error="Skipped (not a lecon/cours)")

            conn.commit()

        except Exception as e:
            logger.error(f"❌ Erreur fatale {pdf_file.name}: {e}")
            results["errors"] += 1
            conn.rollback()

    conn.close()

    # ═══ PHASE FINALE : Supprimer les PDFs originaux et le dossier source ═══
    for original_path, archive_path in archived_files:
        try:
            original_path.unlink()
            logger.info(f"🗑️  Supprimé (traité) : {original_path.name}")
        except Exception as e:
            logger.warning(f"⚠️  Impossible de supprimer {original_path.name}: {e}")

    # Supprimer le dossier source s'il est vide
    try:
        if not any(folder.iterdir()):
            folder.rmdir()
            logger.info(f"📁 Dossier source supprimé (vide) : {folder_path}")
        else:
            shutil.rmtree(folder, ignore_errors=True)
            logger.info(f"📁 Dossier source supprimé : {folder_path}")
    except Exception as e:
        logger.warning(f"⚠️  Impossible de supprimer le dossier source : {e}")

    results["archive_path"] = str(run_archive)
    logger.info(f"📊 Résumé ingest: {results}")
    return results


async def _call_llm_metadata(texte: str, nom_fichier: str) -> dict:
    """Wrapper async pour le parser LLM."""
    from app.modules.ingest.services.llm_metadata_parser import extract_metadata_llm
    return await extract_metadata_llm(texte, nom_fichier)


# ─── Retry Cron Task ──────────────────────────────────────────────

@celery_app.task(
    name="ingest.tasks.retry_blocked_ingest_steps",
    queue="default",
    bind=True,
    max_retries=1,
)
def retry_blocked_ingest_steps(self):
    """
    Retry les documents bloqués dans le pipeline ingest.
    Exécuté par Celery Beat toutes les 30 minutes.
    """
    from app.core.config import DATABASE_URL
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Trouver les documents bloqués prêts au retry
    now = datetime.now(timezone.utc)
    cur.execute("""
        SELECT id, folder_path, filename, current_step, retry_count, max_retries
        FROM ingest_step_logs
        WHERE step_status = 'blocked'
          AND (next_retry_at IS NULL OR next_retry_at <= %s)
          AND retry_count < max_retries
        ORDER BY created_at ASC
        LIMIT 50
    """, (now,))

    blocked_docs = cur.fetchall()
    if not blocked_docs:
        conn.close()
        return {"status": "no_blocked_docs", "checked_at": now.isoformat()}

    logger.info(f"🔄 Retrying {len(blocked_docs)} blocked ingest documents")

    retried = 0
    permanently_failed = 0

    for log_id, folder_path, filename, current_step, retry_count, max_retries in blocked_docs:
        try:
            # Marquer comme retry en cours
            cur.execute("""
                UPDATE ingest_step_logs
                SET step_status = 'retrying',
                    retry_count = retry_count + 1,
                    updated_at = NOW()
                WHERE id = %s
            """, (log_id,))
            conn.commit()

            # Re-run le pipeline depuis l'étape bloquée
            pdf_path = os.path.join(folder_path, filename)
            if not os.path.exists(pdf_path):
                cur.execute("""
                    UPDATE ingest_step_logs
                    SET step_status = 'failed',
                        error_message = 'File not found',
                        updated_at = NOW()
                    WHERE id = %s
                """, (log_id,))
                conn.commit()
                permanently_failed += 1
                continue

            # Relancer la task principale pour ce fichier
            from app.modules.ingest.jobs.ingest_folder_tasks import ingest_folder_task
            # On ne peut pas relancer une sous-partie, donc on log le retry
            cur.execute("""
                UPDATE ingest_step_logs
                SET step_status = 'pending',
                    next_retry_at = NOW() + INTERVAL '%s minutes',
                    updated_at = NOW()
                WHERE id = %s
            """, (5 * (retry_count + 2), log_id))
            conn.commit()
            retried += 1

        except Exception as e:
            logger.error(f"Retry failed for {filename}: {e}")
            permanently_failed += 1

    conn.close()
    return {
        "status": "done",
        "retried": retried,
        "permanently_failed": permanently_failed,
    }
