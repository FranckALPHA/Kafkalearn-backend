"""
services/search_suggestion_service.py
=====================================
Suggestions de recherche personnalisées.
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func
from redis import Redis

from app.modules.search.services.base import SearchBaseService
from app.modules.search.models import SearchSuggestionCache, SearchLog

logger = logging.getLogger(__name__)


class SearchSuggestionService(SearchBaseService):
    """Génération de suggestions personnalisées basées sur le profil."""

    TTL_HOURS = 24

    async def generer_suggestions(self, user_id: str) -> dict:
        """
        Génère des suggestions de recherche personnalisées.
        Utilise le cache Redis 24h.
        """
        from uuid import UUID
        user_uuid = UUID(user_id)

        # Vérifier le cache
        cache_entry = (
            self.db.query(SearchSuggestionCache)
            .filter(SearchSuggestionCache.user_id == user_uuid)
            .first()
        )

        if cache_entry and not cache_entry.is_expired():
            return {
                "suggestions": cache_entry.suggestions,
                "generated_at": cache_entry.generated_at,
                "expires_at": cache_entry.expires_at,
            }

        # Générer nouvelles suggestions
        suggestions = await self._generer_suggestions_from_profile(user_id)

        # Mettre à jour ou créer le cache
        expires_at = datetime.utcnow() + timedelta(hours=self.TTL_HOURS)

        if cache_entry:
            cache_entry.suggestions = suggestions
            cache_entry.generated_at = datetime.utcnow()
            cache_entry.expires_at = expires_at
        else:
            cache_entry = SearchSuggestionCache(
                user_id=user_id,
                suggestions=suggestions,
                generated_at=datetime.utcnow(),
                expires_at=expires_at,
            )
            self.db.add(cache_entry)

        self.db.commit()

        return {
            "suggestions": suggestions,
            "generated_at": cache_entry.generated_at,
            "expires_at": expires_at,
        }

    async def _generer_suggestions_from_profile(self, user_id: str) -> List[str]:
        """
        Génère des suggestions basées sur l'historique et les matières fréquentes.
        Enrichi avec le profil d'apprentissage et les lacunes détectées.
        """
        from uuid import UUID
        user_uuid = UUID(user_id)

        # Recherches populaires de l'utilisateur
        user_top = (
            self.db.query(SearchLog.texte_requete)
            .filter(SearchLog.user_id == user_uuid)
            .order_by(SearchLog.created_at.desc())
            .limit(5)
            .all()
        )

        # Requêtes populaires globales (fallback)
        global_top = (
            self.db.query(SearchLog.texte_requete)
            .filter(SearchLog.created_at >= datetime.utcnow() - timedelta(days=7))
            .group_by(SearchLog.texte_requete)
            .order_by(func.count(SearchLog.id).desc())
            .limit(10)
            .all()
        )

        suggestions = [r[0] for r in user_top]
        for r in global_top:
            if r[0] not in suggestions and len(suggestions) < 10:
                suggestions.append(r[0])

        # Enrichissement via les lacunes du profil utilisateur
        try:
            from app.modules.users.models import UserLearningProfile
            profile = (
                self.db.query(UserLearningProfile)
                .filter(UserLearningProfile.user_id == user_uuid)
                .first()
            )
            if profile and profile.lacunes:
                for matiere, notions in list(profile.lacunes.items())[:2]:
                    for notion in notions[:1]:
                        tip = f"Révise les {notion} en {matiere}"
                        if tip not in suggestions and len(suggestions) < 10:
                            suggestions.append(tip)
        except Exception:
            pass  # Profil non disponible

        # Suggestions par défaut si vide
        if not suggestions:
            suggestions = [
                "Explique les dérivées en Mathématiques",
                "Exercice de Physique Terminale C",
                "Résumé du programme de SVT",
                "Épreuve de Français au BEPC",
                "Cours complet sur les intégrales",
            ]

        return suggestions[:10]
