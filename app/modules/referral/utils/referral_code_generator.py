"""
utils/referral_code_generator.py
=================================
Generates and validates unique 6-character referral codes.
"""
import random
import re
import string

CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


class ReferralCodeGenerator:
    """Generate and validate unique referral codes."""

    @staticmethod
    def generate(db, max_attempts: int = 10) -> str:
        """Generate a unique 6-character referral code (uppercase letters + digits).

        Args:
            db: SQLAlchemy database session.
            max_attempts: Maximum number of attempts before raising an error.

        Returns:
            A unique 6-character referral code.

        Raises:
            RuntimeError: If unable to generate a unique code after max_attempts.
        """
        from app.modules.users.models import User

        chars = string.ascii_uppercase + string.digits
        for _ in range(max_attempts):
            code = "".join(random.choices(chars, k=6))
            existing = db.query(User).filter(User.referral_code == code).first()
            if not existing:
                return code
        raise RuntimeError("Failed to generate a unique referral code after max attempts")

    @staticmethod
    def validate(code: str) -> bool:
        """Validate that a referral code matches the expected format.

        Args:
            code: The referral code to validate.

        Returns:
            True if the code matches ^[A-Z0-9]{6}$.
        """
        return bool(CODE_PATTERN.match(code))
