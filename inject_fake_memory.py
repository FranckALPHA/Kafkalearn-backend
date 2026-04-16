import sys
import os
import json

# Setup PYTHONPATH
sys.path.append(os.getcwd())

from app.core.database_init import init_db
from app.core.database import SessionLocal
from app.modules.memory.models import MemoryItem, MemorySection

def inject():
    db = SessionLocal()
    try:
        # Trouver la section créée précédemment
        section = db.query(MemorySection).filter(MemorySection.document_id == 135).first()
        if not section:
            print("[-] Section not found for doc 135. Run generate_memory_for_135.py first.")
            return

        print(f"[*] Injection d'items fake dans la section ID: {section.id}")
        
        items = [
            {
                "item_type": "flashcard",
                "content": {
                    "fr": {"recto": "Quelle est la capitale du Cameroun ?", "verso": "Yaoundé"},
                    "en": {"recto": "What is the capital of Cameroon?", "verso": "Yaoundé"}
                }
            },
            {
                "item_type": "qcm",
                "content": {
                    "fr": {
                        "question": "En quelle année le Cameroun a-t-1 obtenu son indépendance ?",
                        "options": ["1958", "1960", "1961", "1972"],
                        "bonne_reponse": "1960",
                        "explication": "Le Cameroun français est devenu indépendant le 1er janvier 1960."
                    }
                }
            }
        ]

        for item_data in items:
            new_item = MemoryItem(
                section_id=section.id,
                item_type=item_data["item_type"],
                content_json=item_data["content"],
                fingerprint=f"fake_{item_data['item_type']}_{section.id}"
            )
            db.add(new_item)
        
        section.generation_status = "complete"
        section.nb_items = len(items)
        db.commit()
        print("[+] Items injectés avec succès.")

    finally:
        db.close()

if __name__ == "__main__":
    inject()
