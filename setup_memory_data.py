import sys
import os
from pathlib import Path

# Ajouter le chemin du projet au PYTHONPATH
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.modules.epreuves.models import Document
from app.modules.users.models import User
from app.modules.memory.jobs.tasks import generate_memory_items_task
import hashlib

def setup_data():
    db = SessionLocal()
    try:
        # 1. Trouver le SuperAdmin
        sa = db.query(User).filter(User.email == "etogafranck449@gmail.com").first()
        if not sa:
            print("[-] SuperAdmin non trouvé")
            return

        # 2. Créer un document de type 'lecon'
        pdf_path = "data/epreuves/Histoire-Géographie/93b2c489_Cours d'histoire géographie.pdf"
        if not os.path.exists(pdf_path):
            print(f"[-] Fichier non trouvé: {pdf_path}")
            return

        with open(pdf_path, "rb") as f:
            content = f.read()
            h = hashlib.sha256(content).hexdigest()

        # Vérifier si déjà existant
        existing = db.query(Document).filter(Document.hash_contenu == h).first()
        if existing:
            doc = existing
            print(f"[+] Document déjà existant ID: {doc.id}")
        else:
            doc = Document(
                nom_original=os.path.basename(pdf_path),
                nom_affiche="Cours Histoire-Géo Test",
                matiere="Histoire-Géographie",
                niveau="Terminale",
                annee=2026,
                type_doc="lecon",
                poids_octets=len(content),
                hash_contenu=h,
                is_validated=True,
                ingest_status="completed",
                texte_extrait="Ceci est un cours d'histoire géographie sur le Cameroun. Les notions abordées sont la colonisation, l'indépendance et le développement économique.",
                chemin_final=pdf_path
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            print(f"[+] Document créé ID: {doc.id}")

        # 3. Déclencher la génération Memory (via la task Celery mais en direct pour le test)
        # Note: On simule le texte car l'extraction réelle peut être longue
        print("[*] Génération des items Memory...")
        
        # On va appeler la task en synchrone pour le test
        result = generate_memory_items_task(
            document_id=doc.id,
            section_title="Introduction",
            texte_section=doc.texte_extrait,
            langue="fr"
        )
        print(f"[+] Items générés: {result}")
        
        return doc.id
    finally:
        db.close()

if __name__ == "__main__":
    setup_data()
