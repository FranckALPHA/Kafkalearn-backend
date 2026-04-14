"""
app/modules/daily_quiz/routes/admin.py
======================================
Admin routes for daily quiz management.

Routes:
  GET  /admin/daily-quiz/all        → List ALL generated quizzes (with full questions)
  POST /admin/daily-quiz/generate   → Generate a specific quiz type
  GET  /admin/daily-quiz/stats      → Global stats
"""
import logging
import json
import asyncio
import concurrent.futures
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.daily_quiz.routes.dependencies import (
    get_db,
    get_current_user,
    get_quiz_generator,
    get_rate_limiter_dependency,
    daily_quiz_rate_limiter,
)
from app.modules.users.models import User
from app.modules.daily_quiz.models import DailyQuiz, DailyQuizAttempt
from app.modules.daily_quiz.services.daily_quiz_generator import (
    QUIZ_TYPES,
    get_prompt_for_type,
)
from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
from app.core.config import OPENROUTER_API_KEYS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/daily-quiz", tags=["admin-daily-quiz"])


def _require_superadmin(user: User):
    """Ensure the current user is a SuperAdmin."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")


def _call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM synchronously (OpenRouter → Ollama fallback)."""
    api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
    client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                client.generate(
                    messages=[{"role": "user", "content": user_prompt}],
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_tokens=3000,
                    response_format="json",
                )
            )
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_run).result(timeout=180)


# ─────────────────────────────────────────────────────────────────────
# 1. GET /admin/daily-quiz/all  —  Voir tous les quiz générés
# ─────────────────────────────────────────────────────────────────────
@router.get("/all")
async def list_all_quizzes(
    quiz_type: Optional[str] = Query(None, description="Filtrer par type: qcm, qro, true_false, phrase_completion, ordering, matching"),
    quiz_date: Optional[str] = Query(None, description="Filtrer par date: YYYY-MM-DD"),
    with_questions: bool = Query(False, description="Inclure les questions complètes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    **Liste TOUS les quiz générés.**

    Filtres optionnels :
    - `quiz_type` : qcm, qro, true_false, phrase_completion, ordering, matching
    - `quiz_date` : YYYY-MM-DD
    - `with_questions` : true pour voir les questions complètes

    Retourne :
    ```json
    {
      "total": 42,
      "quizzes": [
        {
          "id": 1,
          "quiz_date": "2026-04-14",
          "quiz_type": "qcm",
          "nb_questions": 5,
          "nb_attempts": 0,
          "created_at": "2026-04-14T07:00:00",
          "questions": [...]  // si with_questions=true
        }
      ]
    }
    """
    _require_superadmin(current_user)

    q = db.query(DailyQuiz)
    if quiz_type:
        q = q.filter(DailyQuiz.quiz_type == quiz_type)
    if quiz_date:
        try:
            d = date.fromisoformat(quiz_date)
            q = q.filter(DailyQuiz.quiz_date == d)
        except ValueError:
            raise HTTPException(status_code=400, detail="INVALID_DATE_FORMAT")

    quizzes = q.order_by(DailyQuiz.quiz_date.desc(), DailyQuiz.id.desc()).all()

    results = []
    for quiz in quizzes:
        attempts_count = (
            db.query(func.count(DailyQuizAttempt.id))
            .filter(DailyQuizAttempt.daily_quiz_id == quiz.id)
            .scalar()
        )
        entry = {
            "id": quiz.id,
            "quiz_date": str(quiz.quiz_date),
            "quiz_type": quiz.quiz_type,
            "nb_questions": quiz.nb_questions,
            "source": quiz.source,
            "nb_attempts": attempts_count or 0,
            "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
        }
        if with_questions:
            entry["questions"] = quiz.questions_json
        results.append(entry)

    return {
        "total": len(results),
        "quizzes": results,
    }


# ─────────────────────────────────────────────────────────────────────
# 2. POST /admin/daily-quiz/generate  —  Générer un type précis
# ─────────────────────────────────────────────────────────────────────
@router.post("/generate")
async def generate_quiz(
    quiz_type: str = Query(..., description="Type: qcm, qro, true_false, phrase_completion, ordering, matching"),
    quiz_date: Optional[str] = Query(None, description="Date cible (défaut: aujourd'hui)"),
    force: bool = Query(False, description="Forcer la régénération même si un quiz existe déjà"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    **Générer un quiz d'un type précis.**

    Types disponibles :
    - `qcm` — Question à choix multiples (4 options, 1 réponse)
    - `qro` — Question à réponse ouverte courte
    - `true_false` — Vrai ou Faux
    - `phrase_completion` — Compléter une phrase à trous
    - `ordering` — Remettre dans l'ordre
    - `matching` — Associer des éléments

    Exemple :
    ```
    POST /admin/daily-quiz/generate?quiz_type=qcm&quiz_date=2026-04-15
    ```

    Retourne :
    ```json
    {
      "status": "created",
      "quiz": {
        "id": 5,
        "quiz_type": "qcm",
        "quiz_date": "2026-04-15",
        "nb_questions": 5,
        "questions": [...]
      }
    }
    ```
    """
    _require_superadmin(current_user)

    # Validate quiz type
    if quiz_type not in QUIZ_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"INVALID_QUIZ_TYPE. Available: {', '.join(QUIZ_TYPES)}",
        )

    target_date = date.fromisoformat(quiz_date) if quiz_date else date.today()

    # Check existing quiz
    existing = db.query(DailyQuiz).filter(
        DailyQuiz.quiz_date == target_date,
        DailyQuiz.quiz_type == quiz_type,
    ).first()
    if existing and not force:
        return {
            "status": "exists",
            "message": f"Un quiz {quiz_type} existe déjà pour {target_date}. Utilisez force=true pour regénérer.",
            "quiz": {
                "id": existing.id,
                "quiz_date": str(existing.quiz_date),
                "quiz_type": existing.quiz_type,
                "nb_questions": existing.nb_questions,
                "questions": existing.questions_json,
            },
        }

    # Generate via LLM
    system_prompt, prompt = get_prompt_for_type(quiz_type, target_date)
    try:
        response = _call_llm(system_prompt, prompt)
    except Exception as exc:
        raise HTTPException(status_code=504, detail=f"LLM_FAILED: {exc}")

    raw_text = response.get("text", "").replace("```json", "").replace("```", "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=500,
            detail=f"LLM_EMPTY_RESPONSE. error_code={response.get('error_code', 'UNKNOWN')}, provider={response.get('provider', 'unknown')}",
        )

    logger.info(f"LLM raw response for {quiz_type}: {raw_text[:300]!r}")

    # Retry loop: keep regenerating until we get valid JSON
    max_retries = 3
    retry_count = 0
    questions = None

    while questions is None and retry_count < max_retries:
        try:
            data = json.loads(raw_text)
            # Extract questions from whatever key the LLM used
            if isinstance(data, dict):
                for key in ["questions", "quiz", quiz_type, "true_false", "matching", "ordering", "phrase_completion", "qcm", "qro"]:
                    if key in data and isinstance(data[key], (list, dict)):
                        questions = data[key]
                        break
                if questions is None:
                    for v in data.values():
                        if isinstance(v, (list, dict)):
                            questions = v
                            break
            elif isinstance(data, (list, dict)):
                questions = data
        except json.JSONDecodeError:
            retry_count += 1
            logger.warning(f"LLM returned non-JSON for {quiz_type}, retry {retry_count}/{max_retries}")
            if retry_count >= max_retries:
                break
            # Regenerate with same prompt
            try:
                response = _call_llm(system_prompt, prompt)
                raw_text = response.get("text", "").replace("```json", "").replace("```", "").strip()
                logger.info(f"Retry {retry_count} raw response: {raw_text[:300]!r}")
            except Exception as exc:
                raise HTTPException(status_code=504, detail=f"LLM_RETRY_FAILED: {exc}")

    if questions is None:
        raise HTTPException(
            status_code=500,
            detail=f"LLM_JSON_INVALID after {max_retries} retries. Last response was: {raw_text[:300]!r}",
        )

    # Delete existing if force
    if existing and force:
        db.query(DailyQuizAttempt).filter(
            DailyQuizAttempt.daily_quiz_id == existing.id
        ).delete()
        db.delete(existing)
        db.commit()

    # Compute nb_questions
    if isinstance(questions, list):
        nb_q = len(questions)
    elif isinstance(questions, dict):
        nb_q = len(questions)
    else:
        nb_q = 5

    # Create quiz
    new_quiz = DailyQuiz(
        quiz_date=target_date,
        quiz_type=quiz_type,
        questions_json=questions,
        source="llm",
        nb_questions=nb_q,
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    return {
        "status": "created",
        "quiz": {
            "id": new_quiz.id,
            "quiz_date": str(new_quiz.quiz_date),
            "quiz_type": new_quiz.quiz_type,
            "nb_questions": new_quiz.nb_questions,
            "questions": new_quiz.questions_json,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# 3. GET /admin/daily-quiz/stats  —  Statistiques globales
# ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_global_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Global quiz statistics (SuperAdmin only)."""
    _require_superadmin(current_user)

    total_quizzes = db.query(func.count(DailyQuiz.id)).scalar()
    total_attempts = db.query(func.count(DailyQuizAttempt.id)).scalar()
    avg_score_row = db.query(func.avg(DailyQuizAttempt.score_pourcentage)).first()
    avg_score = float(avg_score_row[0]) if avg_score_row and avg_score_row[0] is not None else 0.0

    # Count by type
    type_counts = {}
    for qt in QUIZ_TYPES:
        count = db.query(func.count(DailyQuiz.id)).filter(DailyQuiz.quiz_type == qt).scalar()
        type_counts[qt] = count or 0

    today = date.today()
    today_quizzes = db.query(DailyQuiz).filter(DailyQuiz.quiz_date == today).all()
    today_attempts = 0
    for tq in today_quizzes:
        today_attempts += (
            db.query(func.count(DailyQuizAttempt.id))
            .filter(DailyQuizAttempt.daily_quiz_id == tq.id)
            .scalar()
        )

    return {
        "total_quizzes": total_quizzes or 0,
        "total_attempts": total_attempts or 0,
        "average_score": round(avg_score, 2),
        "by_type": type_counts,
        "today": {
            "quiz_count": len(today_quizzes),
            "attempts": today_attempts or 0,
            "types": [tq.quiz_type for tq in today_quizzes],
        },
    }
