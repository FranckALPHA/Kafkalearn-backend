"""
modules/core/i18n.py
====================
Chargement des traductions JSON.
"""
import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"
_translations = {}


def load_locales():
    global _translations
    for lang_file in LOCALES_DIR.glob("*.json"):
        lang = lang_file.stem
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        except Exception:
            pass


load_locales()


def t(key: str, lang: str = "fr", **kwargs) -> str:
    """Traduit une clé. Ex: t('auth.invalid_credentials', 'fr')"""
    keys = key.split(".")
    current = _translations.get(lang, _translations.get("fr", {}))

    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, "")
        else:
            return key

    if not current:
        return key

    try:
        return current.format(**kwargs)
    except KeyError:
        return current
