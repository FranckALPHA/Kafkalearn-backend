import json
import re
from typing import Dict, Any

class JSONValidator:
    REQUIRED = {
        "epreuve": ["key_points", "concepts", "tips", "methodologie", "notions_prerequis"],
        "lecon": ["summary", "concepts", "key_points", "tips", "notions_prerequis"],
    }
    DEFAULTS = {
        "key_points": [], "concepts": [], "tips": [], "summary": "",
        "methodologie": "", "notions_prerequis": [], "difficulte_detail": {},
    }

    @classmethod
    def parse_and_validate(cls, raw_text: Any, analysis_type: str) -> Dict[str, Any]:
        if isinstance(raw_text, dict):
            data = raw_text
        else:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            try:
                data = json.loads(cleaned)
            except (json.JSONDecodeError, AttributeError) as e:
                raise ValueError(f"JSON invalide ou type incorrect: {e}")

        if not isinstance(data, dict):
            raise ValueError("Le JSON doit être un objet")
        for field in cls.REQUIRED.get(analysis_type, []):
            if field not in data:
                data[field] = cls.DEFAULTS.get(field, None)
        for field in ["key_points", "concepts", "tips", "notions_prerequis"]:
            if field in data and not isinstance(data[field], list):
                data[field] = []
            if field in data and isinstance(data[field], list):
                data[field] = data[field][:10]
        for field in ["summary", "methodologie"]:
            if field in data and isinstance(data[field], str):
                data[field] = data[field][:2000]
        return data
