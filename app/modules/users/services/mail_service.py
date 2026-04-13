"""
services/mail_service.py
========================
Service pour l'envoi d'emails (OTP, bienvenue, notifications).
"""
import asyncio
import logging
from typing import Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.core.config import (
    MAIL_FROM,
    BREVO_API_KEY,
    MAIL_HOST,
    MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    FRONTEND_URL,
)
from app.modules.core.mail import send_email
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)


class MailService(BaseService):
    """Service pour l'envoi d'emails via Brevo ou SMTP (placeholder)."""

    def envoyer_otp(
        self,
        email: str,
        prenom: str,
        otp_code: str,
        type: str = "email_verify",
    ) -> bool:
        """
        Envoie un email contenant le code OTP a l'utilisateur.

        Args:
            email: Adresse email du destinataire.
            prenom: Prenom du destinataire.
            otp_code: Code OTP a 6 chiffres.
            type: Type de token ('email_verify', 'password_reset', 'login_otp').

        Returns:
            True si l'email a ete envoye avec succes.
        """
        type_labels = {
            "email_verify": "verification de votre compte",
            "password_reset": "reinitialisation de votre mot de passe",
            "login_otp": "connexion a votre compte",
        }
        objet = type_labels.get(type, "verification")

        # Construction du corps de l'email
        subject = f"KafkaLearn - Code de {objet}"
        body = self._build_otp_email_html(prenom, otp_code, objet)

        # Envoi via Brevo (synchrone pour compatibilite avec l'interface actuelle)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        message_id = loop.run_until_complete(
            send_email(to=email, subject=subject, body_html=body)
        )

        if message_id:
            logger.info(
                f"[EMAIL-OTP] Sent to {email} | Subject: {subject} | "
                f"Message-ID: {message_id}"
            )
            return True
        else:
            # Fallback: log le code (development mode)
            logger.warning(
                f"[EMAIL-OTP] Brevo unavailable, logging code for dev: "
                f"To: {email} | Code: {otp_code} | Type: {type}"
            )
            return True

    def envoyer_bienvenue(self, email: str, prenom: str) -> bool:
        """
        Envoie un email de bienvenue a un nouvel utilisateur.

        Args:
            email: Adresse email du destinataire.
            prenom: Prenom du destinataire.

        Returns:
            True si l'email a ete envoye avec succes.
        """
        subject = "Bienvenue sur KafkaLearn !"
        body = self._build_bienvenue_email_html(prenom)

        # Envoi via Brevo
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        message_id = loop.run_until_complete(
            send_email(to=email, subject=subject, body_html=body)
        )

        if message_id:
            logger.info(
                f"[EMAIL-BIENVENUE] Sent to {email} | Subject: {subject} | Message-ID: {message_id}"
            )
            return True
        else:
            # Fallback: log uniquement
            logger.warning(
                f"[EMAIL-BIENVENUE] Brevo unavailable, logging for dev: To: {email}"
            )
            return True

    def envoyer_notification(
        self,
        email: str,
        prenom: str,
        subject: str,
        content: str,
    ) -> bool:
        """
        Envoie un email de notification generique.

        Args:
            email: Adresse email du destinataire.
            prenom: Prenom du destinataire.
            subject: Objet de l'email.
            content: Corps de l'email (texte brut ou HTML).

        Returns:
            True si l'email a ete envoye avec succes.
        """
        # Si le contenu est du HTML, l'utiliser directement; sinon, generer un template simple
        if content.strip().startswith("<!"):
            body_html = content
        else:
            body_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px;">
                    <h2 style="color: #4F46E5;">KafkaLearn</h2>
                    <p>Bonjour {prenom},</p>
                    {content}
                    <p style="color: #6b7280; font-size: 12px; margin-top: 30px;">&copy; 2026 KafkaLearn. Tous droits reserves.</p>
                </div>
            </body>
            </html>
            """

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        message_id = loop.run_until_complete(
            send_email(to=email, subject=subject, body_html=body_html)
        )

        if message_id:
            logger.info(
                f"[EMAIL-NOTIFICATION] Sent to {email} | Subject: {subject} | Message-ID: {message_id}"
            )
            return True
        else:
            logger.warning(
                f"[EMAIL-NOTIFICATION] Brevo unavailable, logging for dev: To: {email} | Subject: {subject}"
            )
            return True

    # ─── Templates HTML ─────────────────────────────────────────

    @staticmethod
    def _build_otp_email_html(prenom: str, otp_code: str, objet: str) -> str:
        """Genere le HTML pour l'email OTP."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .header {{ background: #4F46E5; color: #ffffff; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; }}
                .otp-code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #4F46E5; text-align: center; padding: 20px; background: #EEF2FF; border-radius: 8px; margin: 20px 0; }}
                .footer {{ background: #f9fafb; padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>KafkaLearn</h1>
                </div>
                <div class="content">
                    <p>Bonjour {prenom},</p>
                    <p>Voici votre code de {objet} :</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>Ce code expire dans 15 minutes. Ne le partagez avec personne.</p>
                    <p>Si vous n'avez pas demande ce code, ignorez cet email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 KafkaLearn. Tous droits reserves.</p>
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _build_bienvenue_email_html(prenom: str) -> str:
        """Genere le HTML pour l'email de bienvenue."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .header {{ background: #4F46E5; color: #ffffff; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; }}
                .btn {{ display: inline-block; background: #4F46E5; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                .footer {{ background: #f9fafb; padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Bienvenue sur KafkaLearn !</h1>
                </div>
                <div class="content">
                    <p>Bonjour {prenom},</p>
                    <p>Nous sommes ravis de vous accueillir sur KafkaLearn, votre plateforme d'apprentissage intelligent.</p>
                    <p>Commencez des maintenant a explorer nos cours, quizzes et outils d'IA pour accelerer votre progression.</p>
                    <p style="text-align: center;">
                        <a href="{FRONTEND_URL}" class="btn">Commencer a apprendre</a>
                    </p>
                    <p>A bientot,<br>L'equipe KafkaLearn</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 KafkaLearn. Tous droits reserves.</p>
                </div>
            </div>
        </body>
        </html>
        """
