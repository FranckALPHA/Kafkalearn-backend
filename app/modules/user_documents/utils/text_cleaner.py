import re
import unicodedata

class TextCleaner:
    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        text = unicodedata.normalize("NFKD", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def truncate_for_prompt(text: str, max_chars: int = 3000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."
