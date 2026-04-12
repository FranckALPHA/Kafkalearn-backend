import unicodedata
import re


class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def token_overlap(text1: str, text2: str, min_overlap: float = 0.6) -> bool:
        t1 = set(TextNormalizer.normalize(text1).split())
        t2 = set(TextNormalizer.normalize(text2).split())
        if not t1 or not t2:
            return False
        return len(t1 & t2) / len(t1 | t2) >= min_overlap

    @staticmethod
    def substring_match(haystack: str, needle: str, min_length: int = 4) -> bool:
        if len(needle) < min_length:
            return False
        return TextNormalizer.normalize(needle) in TextNormalizer.normalize(haystack)
