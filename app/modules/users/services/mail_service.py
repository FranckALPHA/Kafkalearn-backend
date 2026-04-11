"""
services/mail_service.py
========================
Service pour l'envoi d'emails (OTP, bienvenue, notifications).
"""
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

        # TODO: Implementer l'envoi reel via Brevo ou SMTP
        # Exemple avec Brevo (a decommenter quand la cle API est configuree) :
        #
        # import requests
        # url = "https://api.brevo.com/v3/smtp/email"
        # headers = {
        #     "accept": "application/json",
        #     "api-key": BREVO_API_KEY,
        #     "content-type": "application/json",
        # }
        # payload = {
        #     "sender": {"email": MAIL_FROM, "name": "KafkaLearn"},
        #     "to": [{"email": email, "name": prenom}],
        #     "subject": subject,
        #     "htmlContent": body,
        # }
        # response = requests.post(url, json=payload, headers=headers)
        # response.raise_for_status()

        # Pour l'instant, on log le code (development mode)
        logger.info(
            f"[EMAIL-OTP] To: {email} | Subject: {subject} | "
            f"Code: {otp_code} | Type: {type}"
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

        # TODO: Implementer l'envoi reel via Brevo ou SMTP
        # Voir exemple dans envoyer_otp()

        logger.info(
            f"[EMAIL-BIENVENUE] To: {email} | Subject: {subject}"
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
        logger.info(
            f"[EMAIL-NOTIFICATION] To: {email} | Subject: {subject}"
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
