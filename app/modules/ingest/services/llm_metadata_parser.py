"""
services/llm_metadata_parser.py
===============================
Parser LLM de metadata pour les documents ingérés.
Fallback quand le parsing du nom du fichier échoue.

Utilise un JSON de référence (matières, classes, séries du programme camerounais)
pour normaliser les réponses du LLM.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

METADATA_REF_PATH = Path(__file__).parent.parent / "utils" / "metadata_ref.json"


def _load_ref() -> dict:
    """Charge le fichier de référence metadata."""
    with open(METADATA_REF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_with_ref(raw_value: str, ref_key: str) -> Optional[str]:
    """Normalise une valeur brute via les alias du référentiel."""
    ref = _load_ref()
    if not raw_value:
        return None

    aliases = ref.get(f"alias_{ref_key}", {})
    valid_values = ref.get(ref_key + "s", [])

    # Check direct alias
    lower = raw_value.lower().strip()
    if lower in aliases:
        return aliases[lower]

    # Check exact match in valid values
    for v in valid_values:
        if v.lower() == lower:
            return v

    # Fuzzy: check if raw_value is contained in any valid value
    for v in valid_values:
        if lower in v.lower() or v.lower() in lower:
            return v

    return raw_value


async def extract_metadata_llm(
    texte_document: str,
    nom_fichier: str,
) -> Dict[str, Any]:
    """
    Extrait les metadata d'un document via le LLM.
    Fallback utilisé quand le parsing du nom du fichier ne donne rien.

    Le LLM reçoit :
    - Le nom du fichier
    - Les 2000 premiers caractères du texte extrait
    - Le référentiel complet (matières, niveaux, séries, types)

    Retourne :
    {
        "matiere": "Mathematiques",
        "niveau": "Tle",
        "serie": "C",
        "type_doc": "epreuve",
        "notion_principale": "Derivees",
        "annee": 2024,
        "confidence": 0.85
    }
    """
    from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
    from app.core.config import OPENROUTER_API_KEYS

    ref = _load_ref()

    prompt = f"""Tu es un expert en analyse de documents scolaires camerounais.
Analyse ce document et extrais ses metadata.

Référentiel officiel du programme camerounais :
Matières: {', '.join(ref['matieres'])}
Niveaux: {', '.join(ref['niveaux'])}
Séries Tle: {', '.join(ref['series'].get('Tle', []))}
Séries 1ere: {', '.join(ref['series'].get('1ere', []))}
Types de document: {', '.join(ref['types_doc'])}

Document :
Nom du fichier: {nom_fichier}
Contenu (extrait):
{texte_document[:2000]}

Retourne UNIQUEMENT un JSON valide avec cette structure exacte :
{{
  "matiere": "<une des matières du référentiel, ou 'Autre'>",
  "niveau": "<un des niveaux du référentiel, ou 'Non specifie'>",
  "serie": "<une série valide pour ce niveau, ou null>",
  "type_doc": "<un type du référentiel>",
  "notion_principale": "<le concept principal du document>",
  "annee": <annee au format YYYY ou 2024 par defaut>,
  "confidence": <confiance entre 0.5 et 1.0>,
  "raison": "<pourquoi ces choix en 1 phrase>"
}}
"""

    try:
        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
        response = await client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
            response_format="json",
        )

        text = response.get("text", "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[-2].strip()
            if text.startswith("json"):
                text = text[4:].strip()

        result = json.loads(text)

        # Normaliser via le référentiel
        result["matiere"] = _normalize_with_ref(result.get("matiere", ""), "matiere") or "Autre"
        result["niveau"] = _normalize_with_ref(result.get("niveau", ""), "niveau") or "Non specifie"
        result["type_doc"] = _normalize_with_ref(result.get("type_doc", ""), "type_doc") or "epreuve"

        # Valider la série
        serie = result.get("serie", "")
        niveau = result["niveau"]
        valid_series = ref.get("series", {}).get(niveau, [])
        if serie and valid_series and serie not in valid_series:
            result["serie"] = None

        return result

    except Exception as e:
        logger.error(f"LLM metadata extraction failed: {e}")
        return {
            "matiere": "Autre",
            "niveau": "Non specifie",
            "serie": None,
            "type_doc": "epreuve",
            "notion_principale": "",
            "annee": 2024,
            "confidence": 0.0,
            "raison": f"LLM failed: {e}",
        }
