"""
utils/code_generator.py
=======================
Génération sécurisée de codes uniques (école, invitation).
"""
import secrets
import string


class CodeGenerator:
    @staticmethod
    def generate_school_id(length: int = 4) -> str:
        """Génère un ID école unique (format: SCH-XXXX)."""
        chars = string.ascii_uppercase + string.digits
        suffix = "".join(secrets.choice(chars) for _ in range(length))
        return f"SCH-{suffix}"

    @staticmethod
    def generate_invitation_code() -> str:
        """Génère un code d'invitation unique (format: XXX-XXX)."""
        prefix = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
        suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(3))
        return f"{prefix}-{suffix}"

    @staticmethod
    def validate_invitation_code(code: str) -> bool:
        """Valide le format d'un code d'invitation."""
        import re
        return bool(re.match(r"^[A-Z]{3}-[A-Z0-9]{3}$", code))
