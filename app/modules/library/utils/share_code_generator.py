import secrets
import string
import re


class ShareCodeGenerator:
    PREFIX = "AST"
    SUFFIX_LENGTH = 6

    @classmethod
    def generate(cls, db) -> str:
        from app.modules.library.models import PedagogicalAsset
        chars = string.ascii_uppercase + string.digits
        for _ in range(10):
            suffix = "".join(secrets.choice(chars) for _ in range(cls.SUFFIX_LENGTH))
            candidate = f"{cls.PREFIX}-{suffix}"
            if not db.query(PedagogicalAsset).filter(PedagogicalAsset.lien_partage == candidate).first():
                return candidate
        raise RuntimeError("Impossible de générer un code unique")

    @staticmethod
    def validate(code: str) -> bool:
        return bool(re.match(r"^AST-[A-Z0-9]{6}$", code.upper()))

    @staticmethod
    def get_asset_by_code(code: str, db):
        from app.modules.library.models import PedagogicalAsset
        if not ShareCodeGenerator.validate(code):
            return None
        return db.query(PedagogicalAsset).filter(
            PedagogicalAsset.lien_partage == code.upper(),
            PedagogicalAsset.is_public == True,
        ).first()
