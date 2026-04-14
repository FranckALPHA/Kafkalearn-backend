"""
services/learning_profile_service.py
====================================
Service pour la gestion du profil cognitif d'apprentissage.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.models import UserLearningProfile
from app.modules.users.utils.cache import cache_result
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)

MAX_HISTORIQUE_SIZE = 100
MAX_INTENTIONS_SIZE = 20


class LearningProfileService(BaseService):
    """Service pour gerer le profil d'apprentissage d'un utilisateur."""

    @cache_result(key_prefix="user:learning-profile", ttl_seconds=300)
    async def obtenir_profil_complet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le profil d'apprentissage complet d'un utilisateur.
        Les lacunes/forces sont maintenant lus depuis le graphe cognitif (concept_graph).
        """
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )

        if not profile:
            return None

        # Lacunes et forces depuis le graphe cognitif
        try:
            from app.modules.memory.services.concept_graph_service import ConceptGraphService
            graph_svc = ConceptGraphService(self.db)
            lacunes = graph_svc.get_concepts_lacunes(user_id)
            forces = graph_svc.get_concepts_maitrises(user_id)
            stats = graph_svc.get_statistiques_personnelles(user_id)
        except Exception:
            lacunes = {}
            forces = {}
            stats = {}

        return {
            "id": profile.id,
            "user_id": str(profile.user_id),
            "historique_recherches": profile.historique_recherches or [],
            "lacunes": lacunes,
            "forces": forces,
            "interets": profile.interets or [],
            "matieres_frequentes": profile.matieres_frequentes or {},
            "heures_actives": profile.heures_actives or {},
            "jours_actifs": profile.jours_actifs or {},
            "score_par_matiere": stats,
            "last_wisdom_id": profile.last_wisdom_id,
            "dernier_rapport_at": (
                profile.dernier_rapport_at.isoformat() if profile.dernier_rapport_at else None
            ),
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    def ajouter_recherche(
        self,
        user_id: str,
        requete: str,
        intention: Optional[str] = None,
        matiere: Optional[str] = None,
        notion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ajoute une recherche a l'historique (FIFO 100) et met a jour
        les matieres frequentes.

        Args:
            user_id: UUID de l'utilisateur.
            requete: Texte de la recherche.
            intention: Intention detectee (ex: "revision", "approfondissement").
            matiere: Matiere concernee.
            notion: Notion specifique recherchee.

        Returns:
            Le profil mis a jour (partiel).

        Raises:
            ValueError: Si le profil n'existe pas.
        """
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ValueError("LEARNING_PROFILE_NOT_FOUND")

        # Ajouter la recherche a l'historique (FIFO 100)
        historique = profile.historique_recherches or []
        entree = {
            "requete": requete,
            "intention": intention,
            "matiere": matiere,
            "notion": notion,
            "timestamp": datetime.utcnow().isoformat(),
        }
        historique.append(entree)
        if len(historique) > MAX_HISTORIQUE_SIZE:
            historique = historique[-MAX_HISTORIQUE_SIZE:]
        profile.historique_recherches = historique

        # Mettre a jour les matieres frequentes
        matieres_freq = profile.matieres_frequentes or {}
        if matiere:
            matieres_freq[matiere] = matieres_freq.get(matiere, 0) + 1
        profile.matieres_frequentes = matieres_freq

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "historique_count": len(historique),
            "matieres_frequentes": matieres_freq,
        }

    def enregistrer_score_quiz(
        self,
        user_id: str,
        matiere: str,
        score: float,
        lacune_notion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enregistre le score d'un quiz et met à jour le graphe cognitif.
        Score < 50% → arête A_ECHOUE_SUR dans concept_graph
        Score >= 75% → arête MAITRISE dans concept_graph
        """
        from app.modules.memory.services.concept_graph_service import ConceptGraphService

        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ValueError("LEARNING_PROFILE_NOT_FOUND")

        graph_svc = ConceptGraphService(self.db)

        # Écrire dans le graphe cognitif
        if score < 50:
            notion = lacune_notion or "general"
            graph_svc.add_edge(
                user_id=user_id,
                source=notion,
                target=notion,
                relation="A_ECHOUE_SUR",
                confidence=min(score / 50.0, 1.0),
                source_type="quiz",
                matiere=matiere,
                context=f"Quiz score: {score}%",
            )
        elif score >= 75:
            graph_svc.add_edge(
                user_id=user_id,
                source=matiere,
                target=matiere,
                relation="MAITRISE",
                confidence=score / 100.0,
                source_type="quiz",
                matiere=matiere,
                context=f"Quiz score: {score}%",
            )

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        lacunes = graph_svc.get_concepts_lacunes(user_id)
        forces = graph_svc.get_concepts_maitrises(user_id)

        return {
            "lacunes": lacunes,
            "forces": forces,
        }

    def analyser_lacunes_retroactif(self, user_id: str) -> Dict[str, Any]:
        """
        Analyse rétroactive des lacunes à partir des sessions quiz existantes.
        Écrit les résultats dans le graphe cognitif (concept_graph).

        Parcours toutes les QuizSession soumises de l'utilisateur,
        agrège les scores par matière et les notions problématiques.

        Args:
            user_id: UUID de l'utilisateur.

        Returns:
            Dictionnaire avec les lacunes et forces calculées (depuis le graphe).

        Raises:
            ValueError: Si le profil n'existe pas.
        """
        from uuid import UUID
        from app.modules.skills.models import QuizSession
        from app.modules.memory.services.concept_graph_service import ConceptGraphService

        user_uuid = UUID(user_id)

        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_uuid)
            .first()
        )
        if not profile:
            raise ValueError("LEARNING_PROFILE_NOT_FOUND")

        graph_svc = ConceptGraphService(self.db)

        # Récupérer tous les quiz soumis de l'utilisateur
        quiz_sessions = (
            self.db.query(QuizSession)
            .filter(
                QuizSession.user_id == user_uuid,
                QuizSession.submitted_at.isnot(None),
                QuizSession.score_percent.isnot(None),
                QuizSession.matiere.isnot(None),
            )
            .order_by(QuizSession.submitted_at.desc())
            .all()
        )

        if not quiz_sessions:
            return {"lacunes": {}, "forces": {}, "quiz_analyses": 0}

        # Agrégation par matière
        matiere_scores: Dict[str, List[float]] = {}
        matiere_notions_faibles: Dict[str, set] = {}

        for qs in quiz_sessions:
            matiere = qs.matiere
            score = qs.score_percent or 0

            matiere_scores.setdefault(matiere, []).append(score)

            # Notions faibles depuis lacunes_detectees
            if qs.lacunes_detectees:
                matiere_notions_faibles.setdefault(matiere, set())
                for lacune in qs.lacunes_detectees:
                    notion = lacune.get("notion")
                    if notion:
                        matiere_notions_faibles[matiere].add(notion)

            # Notion depuis le champ notion du quiz si score faible
            if score < 50 and qs.notion:
                matiere_notions_faibles.setdefault(matiere, set())
                matiere_notions_faibles[matiere].add(qs.notion)

        # Écrire dans le graphe cognitif
        for matiere, scores in matiere_scores.items():
            avg_score = sum(scores) / len(scores)
            notions_faibles = matiere_notions_faibles.get(matiere, set())

            if avg_score < 50:
                # Lacunes : A_ECHOUE_SUR pour chaque notion
                for notion in (notions_faibles or {"general"}):
                    graph_svc.add_edge(
                        user_id=user_id,
                        source=notion,
                        target=notion,
                        relation="A_ECHOUE_SUR",
                        confidence=min(avg_score / 50.0, 1.0),
                        source_type="migration",
                        matiere=matiere,
                        context=f"Rétroactif: {len(scores)} quiz analysés",
                    )
            elif avg_score >= 75:
                # Maîtrise
                graph_svc.add_edge(
                    user_id=user_id,
                    source=matiere,
                    target=matiere,
                    relation="MAITRISE",
                    confidence=avg_score / 100.0,
                    source_type="migration",
                    matiere=matiere,
                    context=f"Rétroactif: {len(scores)} quiz analysés",
                )

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        logger.info(
            f"Analyse rétroactive user {user_id}: {len(matiere_scores)} matières, "
            f"{len(quiz_sessions)} quiz analysés"
        )

        # Retourner les lacunes/forces depuis le graphe
        lacunes = graph_svc.get_concepts_lacunes(user_id)
        forces = graph_svc.get_concepts_maitrises(user_id)

        scores_dict = {
            m: {"avg": round(sum(s) / len(s), 2), "count": len(s)}
            for m, s in matiere_scores.items()
        }

        return {
            "lacunes": lacunes,
            "forces": forces,
            "score_par_matiere": scores_dict,
            "quiz_analyses": len(quiz_sessions),
        }
