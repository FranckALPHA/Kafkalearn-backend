#!/usr/bin/env python3
"""
Test de configuration LLM
"""

import os
import sys
from pathlib import Path

# Charger les variables d'environnement
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

print("=== Test de configuration LLM ===")
print(
    f"OPENROUTER_API_KEY_1: {'SET' if os.getenv('OPENROUTER_API_KEY_1') else 'NOT SET'}"
)
print(
    f"OPENROUTER_API_KEY_2: {'SET' if os.getenv('OPENROUTER_API_KEY_2') else 'NOT SET'}"
)
print(
    f"OPENROUTER_API_KEY_3: {'SET' if os.getenv('OPENROUTER_API_KEY_3') else 'NOT SET'}"
)
print(
    f"OPENROUTER_API_KEY_4: {'SET' if os.getenv('OPENROUTER_API_KEY_4') else 'NOT SET'}"
)
print(f"OLLAMA_URL: {os.getenv('OLLAMA_URL', 'NOT SET')}")

# Tester l'import du client LLM
try:
    from app.modules.skills.utils.llm_client import LLMClient, LLMProvider

    print("\n=== Test d'import LLMClient ===")
    print("Import réussi")

    # Tester la création du client
    try:
        client = LLMClient()
        print("Création du client LLM réussi")

        # Tester une requête simple
        print("\n=== Test de requête LLM ===")
        import asyncio

        async def test_request():
            try:
                result = await client.generate(
                    messages=[{"role": "user", "content": "Test"}],
                    system_instruction="Réponds 'OK'",
                    temperature=0.1,
                    max_tokens=10,
                )
                print(f"Résultat: {result}")
                if result.get("error_code"):
                    print(f"Erreur: {result.get('error_code')}")
                else:
                    print("Requête LLM réussie!")
            except Exception as e:
                print(f"Erreur lors de la requête: {e}")

        asyncio.run(test_request())

    except Exception as e:
        print(f"Erreur lors de la création du client: {e}")

except Exception as e:
    print(f"Erreur d'import: {e}")
    import traceback

    traceback.print_exc()
