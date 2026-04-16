import sys
import os

# Setup PYTHONPATH
sys.path.append(os.getcwd())

from app.core.database_init import init_db
from app.core.database import SessionLocal
from app.modules.epreuves.models import Document
from app.modules.memory.jobs.tasks import generate_memory_items_task

def generate():
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == 135).first()
        if not doc:
            print("[-] Doc 135 not found")
            return

        print(f"[*] Génération Memory pour le document: {doc.nom_affiche}")
        
        # On utilise une partie du texte extrait pour la génération
        texte = doc.texte_extrait or "Ceci est un cours sur l'histoire du Cameroun..."
        
        # Appel de la task Celery en synchrone (direct)
        result = generate_memory_items_task(
            document_id=doc.id,
            section_title="Histoire du Cameroun",
            texte_section=texte[:5000],
            langue="fr"
        )
        print(f"[+] Résultat: {result}")

    except Exception as e:
        print(f"[-] Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    generate()
