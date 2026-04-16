"""
routes/admin.py
===============
Endpoints admin pour le module wisdom (stats, top tips, liste complète).
Reserve aux superadmins.
"""
from fastapi import APIRouter, Depends, Query

from app.modules.wisdom.routes.dependencies import (
    get_current_superadmin,
    get_wisdom_analytics_service,
)
from app.modules.users.models import User
from app.modules.wisdom.models import WisdomTip

router = APIRouter(prefix="/admin/wisdom", tags=["admin-wisdom"])


@router.get("/stats")
async def get_wisdom_stats(
    current_user: User = Depends(get_current_superadmin),
    analytics_service=Depends(get_wisdom_analytics_service),
):
    """Statistiques globales sur les wisdom tips (SuperAdmin uniquement)."""
    stats = await analytics_service.obtenir_stats_globales()
    return stats


@router.get("/top")
async def get_top_wisdom_tips(
    limit: int = 10,
    current_user: User = Depends(get_current_superadmin),
    analytics_service=Depends(get_wisdom_analytics_service),
):
    """Top des conseils les mieux notes (SuperAdmin uniquement)."""
    top_tips = await analytics_service.obtenir_top_citations(limit=limit)
    return {"top_tips": top_tips}


@router.get("/all")
async def list_all_wisdom_tips(
    limit: int = Query(50, ge=1, le=500),
    source: str = Query(None, description="Filtrer par source: llm, static"),
    category: str = Query(None, description="Filtrer par catégorie"),
    with_content: bool = Query(False, description="Inclure le texte complet des conseils"),
    db=None,
    current_user: User = Depends(get_current_superadmin),
    analytics_service=Depends(get_wisdom_analytics_service),
):
    """
    **Liste TOUS les wisdom tips générés.**

    Filtres :
    - `source` : llm, static
    - `category` : vie, philosophie, strategie, etudes, humour, challenge, vigilance
    - `with_content` : true pour voir le texte complet

    Retourne :
    ```json
    {
      "total": 42,
      "wisdom_tips": [
        {
          "id": 1,
          "tip_date": "2026-04-15",
          "source": "llm",
          "category": "philosophie",
          "nb_vues": 10,
          "nb_partages": 2,
          "rating_moyen": 4.5,
          "text_fr": "Chaque jour est une page blanche..."
        }
      ]
    }
    """
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal

    tmp_db = SessionLocal()
    try:
        q = tmp_db.query(WisdomTip)
        if source:
            q = q.filter(WisdomTip.source == source)
        if category:
            q = q.filter(WisdomTip.category == category)

        total = q.count()
        tips = q.order_by(WisdomTip.tip_date.desc(), WisdomTip.id.desc()).limit(limit).all()

        results = []
        for tip in tips:
            entry = {
                "id": tip.id,
                "tip_date": str(tip.tip_date),
                "source": tip.source,
                "category": tip.category,
                "nb_vues": tip.nb_vues or 0,
                "nb_partages": tip.nb_partages or 0,
                "rating_moyen": tip.rating_moyen,
                "created_at": tip.created_at.isoformat() if tip.created_at else None,
            }
            if with_content:
                content = tip.content_json
                if isinstance(content, dict):
                    entry["text_fr"] = content.get("fr", {}).get("text", "")
                    entry["text_en"] = content.get("en", {}).get("text", "")
                    entry["author_fr"] = content.get("fr", {}).get("author", "")
                    entry["author_en"] = content.get("en", {}).get("author", "")
                elif isinstance(content, str):
                    import json
                    try:
                        data = json.loads(content)
                        entry["text_fr"] = data.get("fr", {}).get("text", "")
                        entry["text_en"] = data.get("en", {}).get("text", "")
                    except Exception:
                        entry["text_fr"] = content
            results.append(entry)

        return {
            "total": total,
            "wisdom_tips": results,
        }
    finally:
        tmp_db.close()
