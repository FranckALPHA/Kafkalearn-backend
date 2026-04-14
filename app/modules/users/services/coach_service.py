"""
services/coach_service.py
=========================
Coach IA — combine les 4 couches de signaux pour prendre des décisions
d'enseignement personnalisées.

Architecture :
  1. Lit le graphe cognitif (lacunes, maîtrises, prérequis)
  2. Lit les signaux d'apprentissage (temporel, comportemental, contextuel)
  3. Calcule le meilleur contenu, moment et format
  4. Retourne une recommandation actionnable
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.users.models.user_learning_signals import UserLearningSignals

logger = logging.getLogger(__name__)


class CoachService:
    """Coach IA : décide QUOI, QUAND et COMMENT faire réviser."""

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────
    # Récupération / initialisation des signaux
    # ─────────────────────────────────────────────────────────────

    def _get_signals(self, user_id: str) -> UserLearningSignals:
        """Récupère ou crée les signaux d'un utilisateur."""
        from uuid import UUID
        signals = (
            self.db.query(UserLearningSignals)
            .filter(UserLearningSignals.user_id == UUID(user_id))
            .first()
        )
        if not signals:
            signals = UserLearningSignals(user_id=user_id)
            self.db.add(signals)
            self.db.commit()
            self.db.refresh(signals)
        return signals

    def _update_layer(self, user_id: str, layer: str, data: dict):
        """Met à jour une couche de signaux (merge profond)."""
        signals = self._get_signals(user_id)
        current = getattr(signals, layer) or {}
        current.update(data)
        setattr(signals, layer, current)
        self.db.commit()

    # ─────────────────────────────────────────────────────────────
    # Enrichissement automatique des signaux
    # ─────────────────────────────────────────────────────────────

    def record_session(self, user_id: str, duration_min: int, matiere: str,
                       score: float, difficulty: str = "medium",
                       completed: bool = True):
        """Enregistre une session d'étude et met à jour les signaux."""
        signals = self._get_signals(user_id)
        now = datetime.utcnow()
        hour = now.hour
        day_name = now.strftime("%A").lower()

        # Temporel
        temporal = signals.temporal_signals or {}
        hours = temporal.get("preferred_hours", {})
        hours[str(hour)] = hours.get(str(hour), 0) + 1
        days = temporal.get("preferred_days", {})
        days[day_name] = days.get(day_name, 0) + 1

        # Moyenne mobile de la durée
        avg_dur = temporal.get("avg_session_duration_min", duration_min)
        temporal["avg_session_duration_min"] = round(avg_dur * 0.8 + duration_min * 0.2, 1)
        temporal["preferred_hours"] = hours
        temporal["preferred_days"] = days
        temporal["last_active_at"] = now.isoformat()
        temporal["current_streak"] = temporal.get("current_streak", 0) + 1 if completed else 0
        signals.temporal_signals = temporal

        # Comportemental
        behavioral = signals.behavioral_signals or {}
        quit_key = f"quit_rate_{difficulty}"
        current_quit = behavioral.get(quit_key, 0.1)
        behavioral[quit_key] = round(current_quit * 0.9 + (0 if completed else 1) * 0.1, 2)

        # Profil : cherche-t-il la pratique ou la théorie ?
        if difficulty == "hard" and completed and score < 50:
            behavioral["retry_after_failure"] = True
        elif difficulty == "hard" and not completed:
            behavioral["retry_after_failure"] = False

        signals.behavioral_signals = behavioral

        # Cognitif : vélocité d'apprentissage
        cognitive = signals.cognitive_signals or {}
        velocity = cognitive.get("learning_velocity", {})
        old_v = velocity.get(matiere, 0)
        velocity[matiere] = round(old_v * 0.9 + (score - 50) / 500 * 0.1, 3)
        cognitive["learning_velocity"] = velocity
        signals.cognitive_signals = cognitive

        self.db.commit()

    def record_quiz_result(self, user_id: str, matiere: str, score: float,
                           notions: List[str], time_spent_sec: int):
        """Enregistre un résultat de quiz et détecte les patterns profonds."""
        signals = self._get_signals(user_id)
        cognitive = signals.cognitive_signals or {}

        deep = cognitive.get("deep_blockages", {})
        superficial = cognitive.get("superficial_gaps", {})

        if score < 40:
            # Échec sévère
            if matiere in superficial:
                # C'était superficiel → devient profond
                data = superficial.pop(matiere)
                data["weeks_stuck"] = data.get("weeks_stuck", 0) + 1
                deep[matiere] = data
            elif matiere in deep:
                deep[matiere]["attempts"] = deep[matiere].get("attempts", 0) + 1
                deep[matiere]["best_score"] = max(
                    deep[matiere].get("best_score", 0), score
                )
            else:
                deep[matiere] = {
                    "weeks_stuck": 0,
                    "attempts": 1,
                    "best_score": score,
                }
        elif score >= 60:
            # Progrès
            if matiere in deep:
                entry = deep.pop(matiere)
                if score >= 75:
                    superficial[matiere] = {
                        "attempts": entry.get("attempts", 1),
                        "best_score": score,
                        "improving": True,
                    }
            if matiere in superficial:
                superficial[matiere]["best_score"] = max(
                    superficial[matiere].get("best_score", 0), score
                )
                if score >= 75:
                    superficial[matiere]["improving"] = True

        cognitive["deep_blockages"] = deep
        cognitive["superficial_gaps"] = superficial

        # Méta-conscience : écart entre score attendu et réel
        behavioral = signals.behavioral_signals or {}
        expected = behavioral.get("expected_score", {})
        expected_matiere = expected.get(matiere, 60)
        gap = abs(score - expected_matiere)
        current_meta = cognitive.get("meta_awareness", 0.5)
        cognitive["meta_awareness"] = round(current_meta * 0.95 + (1 - gap / 100) * 0.05, 2)

        signals.cognitive_signals = cognitive
        self.db.commit()

    def detect_context_from_chat(self, user_id: str, message: str):
        """Détecte le contexte depuis les messages chat (urgence, préférences)."""
        msg_lower = message.lower()
        signals = self._get_signals(user_id)
        contextual = signals.contextual_signals or {}

        # Mode urgence
        urgency_keywords = ["examen", "bac", "baccalauréat", "dans ", "jours", "semaines",
                          "demain", "bientôt", "urgent", "presse"]
        if any(kw in msg_lower for kw in urgency_keywords):
            contextual["urgency_mode"] = True
            # Extraire le nombre de jours si possible
            import re
            days_match = re.search(r'(\d+)\s*(jour|semaine)', msg_lower)
            if days_match:
                val = int(days_match.group(1))
                unit = days_match.group(2)
                contextual["days_until_exam"] = val if unit == "jour" else val * 7

        # Mode d'apprentissage
        if "comprends pas" in msg_lower or "professeur" in msg_lower:
            contextual["learning_mode"] = "autodidact"
        elif "explique" in msg_lower or "cours" in msg_lower:
            contextual["learning_mode"] = contextual.get("learning_mode", "guided")

        # Préférences explicites
        if "schéma" in msg_lower or "image" in msg_lower or "dessin" in msg_lower:
            prefs = contextual.get("explicit_preferences", {})
            prefs["prefers_schemas"] = True
            contextual["explicit_preferences"] = prefs

        if "préfère" in msg_lower or "aime" in msg_lower:
            behavioral = signals.behavioral_signals or {}
            if "quiz" in msg_lower:
                behavioral["content_preference"] = "exercises"
                signals.behavioral_signals = behavioral

        signals.contextual_signals = contextual
        self.db.commit()

    # ─────────────────────────────────────────────────────────────
    # Recommandation intelligente
    # ─────────────────────────────────────────────────────────────

    async def get_personalized_recommendation(
        self,
        user_id: str,
        concept_graph_service=None,
        available_content: List[dict] = None,
    ) -> Dict[str, Any]:
        """
        Génère la recommandation la plus intelligente possible.
        Fallback si le graphe n'est pas disponible (problème RAM).
        """
        try:
            return await self._recommend_with_graph(user_id, concept_graph_service, available_content)
        except Exception as e:
            logger.warning(f"Graph recommendation failed: {e}, using fallback")
            return self._recommend_fallback(user_id)

    async def _recommend_with_graph(
        self, user_id: str, concept_graph_service=None, available_content=None
    ) -> Dict[str, Any]:
        from app.modules.memory.services.concept_graph_service import ConceptGraphService

        signals = self._get_signals(user_id)
        temporal = signals.temporal_signals or {}
        behavioral = signals.behavioral_signals or {}
        cognitive = signals.cognitive_signals or {}
        contextual = signals.contextual_signals or {}

        # 1. Déterminer le concept cible
        concept = None
        matiere = None
        reason = ""

        if concept_graph_service:
            lacunes = concept_graph_service.get_concepts_lacunes(user_id)

            # Priorité aux blocages profonds
            deep_blockages = cognitive.get("deep_blockages", {})
            for concept_name in deep_blockages:
                for mat, notions in lacunes.items():
                    if concept_name in notions:
                        concept = concept_name
                        matiere = mat
                        reason = f"Blocage profond sur {concept_name} ({deep_blockages[concept_name].get('weeks_stuck', 0)} semaines)"
                        break
                if concept:
                    break

            # Sinon : prochaine étape dans la zone proximale
            if not concept:
                zone = cognitive.get("zone_proximale", {})
                if zone:
                    matiere = list(zone.keys())[0]
                    concept = zone[matiere]
                    reason = f"Zone proximale en {matiere}"

            # Sinon : première lacune
            if not concept and lacunes:
                matiere = list(lacunes.keys())[0]
                concept = lacunes[matiere][0] if lacunes[matiere] else None
                reason = f"Lacune détectée en {matiere}"

        if not concept:
            concept = "general"
            matiere = "general"
            reason = "Pas de données suffisantes"

        # 2. Déterminer le format
        profile = behavioral.get("profile_type", "mixed")
        content_pref = behavioral.get("content_preference", "mixed")

        if contextual.get("urgency_mode"):
            # Mode urgence → exercices directs, pas de théorie
            content_type = "exercise"
        elif profile == "practical":
            content_type = "exercise"
        elif profile == "theoretical":
            content_type = "fiche"
        else:
            content_type = content_pref if content_pref != "mixed" else "quiz"

        # 3. Déterminer la difficulté
        deep = cognitive.get("deep_blockages", {})
        if concept in deep:
            difficulty = "easy"  # Revenir aux bases pour un blocage profond
        elif contextual.get("urgency_mode"):
            difficulty = "medium"
        else:
            difficulty = "medium"

        # 4. Déterminer le message
        message = self._generate_message(
            concept=concept, matiere=matiere, reason=reason,
            contextual=contextual, behavioral=behavioral, temporal=temporal,
        )

        # 5. Temps estimé
        avg_duration = temporal.get("avg_session_duration_min", 20)
        if contextual.get("urgency_mode"):
            estimated_time = min(avg_duration, 30)
        else:
            estimated_time = avg_duration

        return {
            "content_type": content_type,
            "concept": concept,
            "matiere": matiere,
            "difficulty": difficulty,
            "message": message,
            "estimated_time_min": round(estimated_time),
            "reasoning": reason,
            "urgency_mode": contextual.get("urgency_mode", False),
        }

    def _recommend_fallback(self, user_id: str) -> Dict[str, Any]:
        """Fallback quand le graphe n'est pas dispo."""
        return {
            "content_type": "quiz",
            "concept": "general",
            "matiere": "general",
            "difficulty": "medium",
            "message": "📚 Prêt pour une session de révision ?",
            "estimated_time_min": 20,
            "reasoning": "Mode dégradé (graphe non disponible)",
            "urgency_mode": False,
        }

    def _generate_message(
        self, concept: str, matiere: str, reason: str,
        contextual: dict, behavioral: dict, temporal: dict,
        langue: str = "fr",
    ) -> str:
        """Génère un message motivationnel personnalisé. Bilingue FR/EN."""
        from app.core.utils.i18n import t, format_msg, COACH_MESSAGES

        streak = temporal.get("current_streak", 0)
        urgency = contextual.get("urgency_mode", False)
        days_exam = contextual.get("days_until_exam")

        if urgency and days_exam:
            return format_msg(
                t(COACH_MESSAGES["urgence_examen"], langue),
                days=days_exam,
                concept=concept,
                matiere=matiere,
            )
        elif streak >= 7:
            return format_msg(
                t(COACH_MESSAGES["streak"], langue),
                days=streak,
            ) + f" {format_msg(t(COACH_MESSAGES['session_recommendation'], langue), concept=concept, matiere=matiere, duration=temporal.get('avg_session_duration_min', 20))}"
        elif concept and reason:
            return format_msg(t(COACH_MESSAGES["session_recommendation"], langue), concept=concept, matiere=matiere, duration=temporal.get('avg_session_duration_min', 20))
        else:
            return t(COACH_MESSAGES["no_data"], langue)

    # ─────────────────────────────────────────────────────────────
    # Intégration Calendar
    # ─────────────────────────────────────────────────────────────

    async def generate_study_plan(
        self,
        user_id: str,
        days_ahead: int = 7,
        concept_graph_service=None,
    ) -> List[Dict[str, Any]]:
        """
        Génère un planning de révision sur N jours.
        Fallback simple si le graphe n'est pas dispo.
        """
        try:
            return await self._generate_plan_with_graph(user_id, days_ahead, concept_graph_service)
        except Exception as e:
            logger.warning(f"Study plan failed: {e}, using fallback")
            return self._generate_plan_fallback(user_id, days_ahead)

    async def _generate_plan_with_graph(
        self, user_id: str, days_ahead: int, concept_graph_service=None
    ) -> List[Dict[str, Any]]:
        """Planning avec graphe cognitif + interleaving."""
        signals = self._get_signals(user_id)
        temporal = signals.temporal_signals or {}
        cognitive = signals.cognitive_signals or {}

        # Heures préférées
        preferred_hours = temporal.get("preferred_hours", {})
        if preferred_hours:
            best_hour = max(preferred_hours, key=preferred_hours.get)
        else:
            best_hour = 20  # défaut

        # Concepts à travailler
        lacunes = {}
        if concept_graph_service:
            lacunes = concept_graph_service.get_concepts_lacunes(user_id)

        # Créer un planning sur N jours avec interleaving
        plan = []
        concepts_list = []
        for mat, notions in lacunes.items():
            for notion in notions:
                concepts_list.append({"concept": notion, "matiere": mat})

        # Interleaving : mélanger les matières
        import random
        random.shuffle(concepts_list)

        from datetime import date as dt_date
        today = dt_date.today()

        for day_offset in range(days_ahead):
            current_date = today + timedelta(days=day_offset)
            day_slots = 2 if temporal.get("urgency_mode") else 1

            for slot in range(day_slots):
                if not concepts_list:
                    break
                item = concepts_list.pop(0)

                plan.append({
                    "date": current_date.isoformat(),
                    "hour": int(best_hour) + slot * 2,
                    "concept": item["concept"],
                    "matiere": item["matiere"],
                    "type": "revision",
                    "estimated_duration_min": 20,
                })

                # Remettre le concept en fin de liste pour la répétition espacée
                concepts_list.append(item)

        return plan

    def _generate_plan_fallback(self, user_id: str, days_ahead: int) -> List[Dict[str, Any]]:
        """Planning simplifié sans graphe."""
        from datetime import date as dt_date
        today = dt_date.today()
        plan = []
        for day_offset in range(days_ahead):
            current_date = today + timedelta(days=day_offset)
            plan.append({
                "date": current_date.isoformat(),
                "hour": 20,
                "concept": "revision_generale",
                "matiere": "general",
                "type": "quiz",
                "estimated_duration_min": 20,
            })
        return plan
