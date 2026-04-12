"""
utils/reference_generator.py
============================
Generation de references uniques pour transactions.
"""
import secrets
import string


class ReferenceGenerator:
    PREFIXES = {"individual": "TRX", "school": "SCH", "transfer": "TRF"}

    @staticmethod
    def generate(tx_type: str = "individual", length: int = 8) -> str:
        prefix = ReferenceGenerator.PREFIXES.get(tx_type, "TRX")
        chars = string.ascii_uppercase + string.digits
        suffix = "".join(secrets.choice(chars) for _ in range(length))
        return f"{prefix}-{suffix}"
