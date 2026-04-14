"""
services/user_service.py
========================
Service principal pour l'authentification et la gestion des utilisateurs.
"""
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    generate_fingerprint,
    generate_otp,
    decode_token,
)
from app.modules.users.utils.helpers import generate_referral_code
from app.modules.users.utils.cache import redis_client, set_cached
from app.modules.users.models import (
    User,
    UserLearningProfile,
    EmailToken,
    RefreshToken,
)
from app.modules.users.services.base import BaseService
from app.modules.users.services.mail_service import MailService

logger = logging.getLogger(__name__)


class UserService(BaseService):
    """Service pour l'inscription, l'authentification et la gestion des utilisateurs."""

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        """Hash SHA-256 du refresh token pour stockage DB."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def inscrire_utilisateur(
        self,
        email: str,
        password: str,
        prenom: str,
        langue: str = "fr",
        referral_code: Optional[str] = None,
    ) -> str:
        """
        Inscrit un nouvel utilisateur avec mot de passe hash, profil d'apprentissage
        et token OTP. Retourne l'UUID de l'utilisateur cree.

        Args:
            email: Adresse email de l'utilisateur.
            password: Mot de passe en clair (sera hash).
            prenom: Prenom de l'utilisateur.
            langue: Langue par defaut ('fr' ou 'en').
            referral_code: Code de parrainage optionnel.

        Returns:
            L'UUID de l'utilisateur cree sous forme de string.

        Raises:
            ValueError: Si l'email existe deja ou si les parametres sont invalides.
        """
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("USER_ALREADY_EXISTS")

        # Verifier le code de parrainage referent
        referred_by_id = None
        if referral_code:
            referent = (
                self.db.query(User)
                .filter(User.referral_code == referral_code)
                .first()
            )
            if referent:
                referred_by_id = referent.id

        user_id = secrets.token_urlsafe(16)  # temporary, will be replaced by DB UUID

        user = User(
            email=email,
            password_hash=hash_password(password),
            prenom=prenom,
            langue=langue,
            referral_code=generate_referral_code(),
            referred_by_id=referred_by_id,
            email_verified=False,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()  # Get the generated UUID

        # Creer le profil d'apprentissage
        learning_profile = UserLearningProfile(user_id=user.id)
        self.db.add(learning_profile)

        # Generer et stocker l'OTP
        otp_code = generate_otp()
        otp_token = EmailToken(
            user_id=user.id,
            token=otp_code,
            token_type="email_verify",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            used=False,
        )
        self.db.add(otp_token)

        # Envoyer l'email OTP (placeholder, log pour l'instant)
        mail_service = MailService(self.db, self.redis)
        try:
            mail_service.envoyer_otp(email, prenom, otp_code, "email_verify")
        except Exception as e:
            logger.warning(f"Failed to send OTP email: {e}")

        self.db.commit()

        return str(user.id)

    def verifier_otp_et_authentifier(
        self, email: str, code: str
    ) -> Dict[str, Any]:
        """
        Verifie le code OTP, marque l'utilisateur comme verifie, et retourne
        les tokens d'acces.

        Args:
            email: Adresse email de l'utilisateur.
            code: Code OTP a verifier.

        Returns:
            Dictionnaire contenant access_token, refresh_token, et user info.

        Raises:
            ValueError: Si l'email n'existe pas ou si le code est invalide.
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        if user.email_verified:
            raise ValueError("USER_ALREADY_VERIFIED")

        # Trouver le token OTP valide
        otp_token = (
            self.db.query(EmailToken)
            .filter(
                EmailToken.user_id == user.id,
                EmailToken.token == code,
                EmailToken.token_type == "email_verify",
                EmailToken.used == False,  # noqa: E712
                EmailToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not otp_token:
            raise ValueError("INVALID_OR_EXPIRED_OTP")

        # Marquer l'OTP comme utilise et l'utilisateur comme verifie
        otp_token.used = True
        user.email_verified = True
        user.derniere_connexion_at = datetime.utcnow()
        self.db.commit()

        # Generer les tokens
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=str(user.id),
            fingerprint="otp-verification",
        )

        # Decoder le refresh token pour obtenir le JTI
        rt_payload = decode_token(refresh_token, "refresh")
        jti = rt_payload.get("jti")

        # Stocker le refresh token en DB
        rt_record = RefreshToken(
            user_id=user.id,
            token_jti=jti,
            token_hash=self._hash_refresh_token(refresh_token),
            fingerprint="otp-verification",
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=False,
        )
        self.db.add(rt_record)
        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user.serialize_minimal(),
        }

    def authentifier(
        self, email: str, password: str, fingerprint: str
    ) -> Dict[str, Any]:
        """
        Authentifie un utilisateur par email/mot de passe. Retourne les tokens
        d'acces et de rafraichissement.

        Args:
            email: Adresse email de l'utilisateur.
            password: Mot de passe en clair.
            fingerprint: Empreinte de l'appareil.

        Returns:
            Dictionnaire contenant access_token, refresh_token, et user info.

        Raises:
            ValueError: Si les identifiants sont invalides.
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("INVALID_CREDENTIALS")

        if not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("INVALID_CREDENTIALS")

        if not user.email_verified:
            raise ValueError("EMAIL_NOT_VERIFIED")

        if not user.is_active:
            raise ValueError("ACCOUNT_DISABLED")

        # Mettre a jour la derniere connexion
        user.derniere_connexion_at = datetime.utcnow()
        self.db.commit()

        # Generer les tokens
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=str(user.id),
            fingerprint=fingerprint,
        )

        # Decoder le refresh token pour obtenir le JTI
        rt_payload = decode_token(refresh_token, "refresh")
        jti = rt_payload.get("jti")

        # Stocker le refresh token en DB
        rt_record = RefreshToken(
            user_id=user.id,
            token_jti=jti,
            token_hash=self._hash_refresh_token(refresh_token),
            fingerprint=fingerprint,
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=False,
        )
        self.db.add(rt_record)
        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user.serialize_minimal(),
        }

    def mettre_a_jour_profil(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Met a jour les champs du profil utilisateur et invalide le cache.

        Args:
            user_id: UUID de l'utilisateur.
            payload: Dictionnaire des champs a mettre a jour.

        Returns:
            Dictionnaire du profil mis a jour.

        Raises:
            ValueError: Si l'utilisateur n'existe pas.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # Champs autorises a la mise a jour
        allowed_fields = {
            "prenom", "nom", "phone", "photo_url", "langue",
            "classe", "serie", "region", "etablissement",
        }

        updated = False
        for field, value in payload.items():
            if field in allowed_fields and hasattr(user, field):
                setattr(user, field, value)
                updated = True

        if updated:
            self.db.commit()
            self._invalidate_profile_cache(str(user_id))

        return user.serialize_minimal()

    def demander_reset_mot_de_passe(self, email: str) -> bool:
        """
        Demande de reinitialisation de mot de passe.
        Genere un code OTP et l'envoie par email.

        Args:
            email: Adresse email de l'utilisateur.

        Returns:
            True si la demande a ete traitee (meme si l'email n'existe pas,
            pour des raisons de securite).
        """
        user = self.db.query(User).filter(User.email == email).first()

        # Toujours retourner True pour ne pas reveler l'existence d'un compte
        if not user:
            logger.info(f"Password reset requested for non-existent email: {email}")
            return True

        # Generer le code OTP
        otp_code = generate_otp()

        # Invalider les anciens tokens password_reset non utilises
        (
            self.db.query(EmailToken)
            .filter(
                EmailToken.user_id == user.id,
                EmailToken.token_type == "password_reset",
                EmailToken.used == False,
            )
            .update({"used": True})
        )

        # Creer le nouveau token
        otp_token = EmailToken(
            user_id=user.id,
            token=otp_code,
            token_type="password_reset",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            used=False,
        )
        self.db.add(otp_token)
        self.db.commit()

        # Envoyer l'email
        mail_service = MailService(self.db, self.redis)
        try:
            mail_service.envoyer_otp(email, user.prenom or "Utilisateur", otp_code, "password_reset")
        except Exception as e:
            logger.warning(f"Failed to send password reset email: {e}")

        return True

    def reinitialiser_mot_de_passe(
        self, email: str, code: str, nouveau_mot_de_passe: str
    ) -> bool:
        """
        Reinitialise le mot de passe d'un utilisateur avec le code OTP.

        Args:
            email: Adresse email de l'utilisateur.
            code: Code OTP de verification.
            nouveau_mot_de_passe: Nouveau mot de passe.

        Returns:
            True si le mot de passe a ete reinitialise.

        Raises:
            ValueError: Si l'email, le code ou le token est invalide.
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # Trouver le token password_reset valide
        otp_token = (
            self.db.query(EmailToken)
            .filter(
                EmailToken.user_id == user.id,
                EmailToken.token == code,
                EmailToken.token_type == "password_reset",
                EmailToken.used == False,
                EmailToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not otp_token:
            raise ValueError("INVALID_OR_EXPIRED_OTP")

        # Marquer le token comme utilise
        otp_token.used = True

        # Changer le mot de passe
        user.password_hash = hash_password(nouveau_mot_de_passe)
        user.derniere_activite_at = datetime.utcnow()
        self.db.commit()

        # Revoquer tous les refresh tokens pour forcer la reconnexion
        self.logout(str(user.id))

        return True

    def changer_mot_de_passe(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool:
        """
        Change le mot de passe d'un utilisateur apres validation de l'ancien.

        Args:
            user_id: UUID de l'utilisateur.
            old_password: Ancien mot de passe.
            new_password: Nouveau mot de passe.

        Returns:
            True si le mot de passe a ete change.

        Raises:
            ValueError: Si l'ancien mot de passe est incorrect.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        if not user.password_hash or not verify_password(old_password, user.password_hash):
            raise ValueError("INVALID_OLD_PASSWORD")

        user.password_hash = hash_password(new_password)
        self.db.commit()

        # Revoquer tous les refresh tokens pour forcer la reconnexion
        self.logout(user_id)

        return True

    def logout(self, user_id: str) -> int:
        """
        Revoque tous les refresh tokens d'un utilisateur (deconnexion complete).

        Args:
            user_id: UUID de l'utilisateur.

        Returns:
            Nombre de tokens revoques.
        """
        revoked_count = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
            .update({"revoked": True, "revoked_at": datetime.utcnow()})
        )
        self.db.commit()

        # Invalider le cache
        self._invalidate_profile_cache(str(user_id))

        return revoked_count

    def refresh_access_token(
        self, refresh_token: str, fingerprint: str
    ) -> Dict[str, Any]:
        """
        Génère un nouveau access token depuis un refresh token valide.

        Args:
            refresh_token: Le refresh token JWT.
            fingerprint: L'empreinte device actuelle.

        Returns:
            Dictionnaire avec nouveau access_token et refresh_token.

        Raises:
            ValueError: Si le refresh token est invalide, expiré ou révoqué.
        """
        try:
            payload = decode_token(refresh_token, "refresh")
        except Exception:
            raise ValueError("INVALID_REFRESH_TOKEN")

        jti = payload.get("jti")
        user_id = payload.get("sub")
        stored_fingerprint = payload.get("fingerprint")

        # Vérifier le fingerprint
        if stored_fingerprint != fingerprint:
            raise ValueError("DEVICE_MISMATCH")

        # Vérifier que le token n'est pas révoqué en DB
        rt_record = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.token_jti == jti,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not rt_record:
            raise ValueError("INVALID_OR_REVOKED_REFRESH_TOKEN")

        # Récupérer l'utilisateur
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_active == True,  # noqa: E712
            User.is_deleted == False,
        ).first()

        if not user:
            raise ValueError("USER_NOT_FOUND")

        # Révoquer l'ancien refresh token (rotation)
        rt_record.revoked = True
        rt_record.revoked_at = datetime.utcnow()

        # Générer de nouveaux tokens
        new_access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
        )
        new_refresh_token = create_refresh_token(
            user_id=str(user.id),
            fingerprint=fingerprint,
        )

        # Stocker le nouveau refresh token
        new_rt_payload = decode_token(new_refresh_token, "refresh")
        new_jti = new_rt_payload.get("jti")

        new_rt_record = RefreshToken(
            user_id=user.id,
            token_jti=new_jti,
            token_hash=self._hash_refresh_token(new_refresh_token),
            fingerprint=fingerprint,
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=False,
        )
        self.db.add(new_rt_record)
        self.db.commit()

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": user.serialize_minimal(),
        }
