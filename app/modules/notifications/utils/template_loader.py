"""
utils/template_loader.py
=========================
Notification template management with inline templates and variable substitution.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Loads and renders notification templates."""

    TEMPLATES = {
        # ─── quiz_dispo ──────────────────────────────────────────────
        "quiz_dispo": {
            "fr": {"title": "Quiz du jour disponible 🎯", "body": "Nouveau quiz — As-tu 5 minutes ?"},
            "en": {"title": "Today's quiz available 🎯", "body": "New quiz — Got 5 minutes?"},
        },
        # ─── memory_review ──────────────────────────────────────────
        "memory_review": {
            "fr": {"title": "Rappel de révision 📚", "body": "Tu as {nb_sections} section(s) à réviser (~{temps_min} min)"},
            "en": {"title": "Review reminder 📚", "body": "You have {nb_sections} section(s) to review (~{temps_min} min)"},
        },
        # ─── session_rappel ─────────────────────────────────────────
        "session_rappel": {
            "fr": {"title": "Session dans 15min ⏰", "body": "{subject} commence à {debut}"},
            "en": {"title": "Session in 15min ⏰", "body": "{subject} starts at {debut}"},
        },
        # ─── streak_danger ──────────────────────────────────────────
        "streak_danger": {
            "fr": {"title": "Streak en danger 🔥", "body": "Ton streak de {nb_jours} jours risque de tomber !"},
            "en": {"title": "Streak in danger 🔥", "body": "Your {nb_jours}-day streak is at risk!"},
        },
        # ─── payment_confirm ────────────────────────────────────────
        "payment_confirm": {
            "fr": {"title": "Paiement confirmé ✅", "body": "Ton plan {plan} est actif"},
            "en": {"title": "Payment confirmed ✅", "body": "Your {plan} plan is active"},
        },
        # ─── referral_actif ─────────────────────────────────────────
        "referral_actif": {
            "fr": {"title": "🎉 {prenom} est actif !", "body": "Encore {nb_restants} pour ton bonus !"},
            "en": {"title": "🎉 {prenom} is active!", "body": "{nb_restants} more for your bonus!"},
        },
        # ─── referral_reward ────────────────────────────────────────
        "referral_reward": {
            "fr": {"title": "🎁 Bonus parrainage !", "body": "Félicitations, plan {plan} actif pour 30 jours !"},
            "en": {"title": "🎁 Referral bonus!", "body": "Congratulations, {plan} plan active for 30 days!"},
        },
        # ─── lacune_detectee ────────────────────────────────────────
        "lacune_detectee": {
            "fr": {"title": "Lacune détectée 🎯", "body": "Tu bloques sur {notion} en {matiere}"},
            "en": {"title": "Gap detected 🎯", "body": "You're struggling with {notion} in {matiere}"},
        },
        # ─── annonce ────────────────────────────────────────────────
        "annonce": {
            "fr": {"title": "Annonce importante 📢", "body": "{message}"},
            "en": {"title": "Important announcement 📢", "body": "{message}"},
        },
    }

    def __init__(self, default_lang: str = "fr"):
        self.default_lang = default_lang
        self._cache: Dict[str, Dict[str, str]] = {}

    def get_template(self, notif_type: str, lang: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Return title/body template dict or None."""
        lang = lang or self.default_lang
        cache_key = f"{notif_type}:{lang}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        type_templates = self.TEMPLATES.get(notif_type)
        if type_templates is None:
            logger.warning("No template for notif_type: %s", notif_type)
            return None

        template = type_templates.get(lang) or type_templates.get(self.default_lang)
        if template:
            self._cache[cache_key] = template
        return template

    def render_template(
        self,
        notif_type: str,
        params: Optional[Dict[str, Any]] = None,
        lang: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Return rendered title/body with {key} substitution."""
        template = self.get_template(notif_type, lang)
        if template is None:
            return None
        params = params or {}
        rendered = {
            "title": template["title"].format(**params),
            "body": template["body"].format(**params),
        }
        return rendered
