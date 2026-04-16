import sys
import os
import uuid
import json

# Setup PYTHONPATH
sys.path.append(os.getcwd())

# CRITIQUE: Importer init_db pour charger TOUS les modèles avant d'utiliser SQLAlchemy
from app.core.database_init import init_db 

from app.core.database import SessionLocal
from app.modules.ingest.services.ingest_service import IngestService
from app.modules.ingest.models import IngestJob
from app.modules.users.models import User

def force_ingest():
    db = SessionLocal()
    try:
        # 1. Get SA
        sa = db.query(User).filter(User.email == "etogafranck449@gmail.com").first()
        if not sa:
            print("[-] SA not found")
            return

        # 2. Create Job
        job_id = str(uuid.uuid4())
        job = IngestJob(
            id=job_id,
            initiated_by=sa.id,
            job_type="single_file",
            status="pending",
            nb_fichiers_total=1,
        )
        db.add(job)
        db.commit()
        print(f"[+] Job created: {job_id}")

        # 3. Path
        pdf_path = "data/epreuves/Histoire-Géographie/93b2c489_Cours d'histoire géographie.pdf"
        
        # 4. Ingest Sync
        service = IngestService(db=db)
        print("[*] Starting sync ingestion...")
        
        force_meta = {
            "type_doc": "lecon",
            "matiere": "Histoire-Géographie",
            "niveau": "Terminale",
            "notion_principale": "Introduction"
        }
        
        result = service.process_single_ingest_sync(
            job_id=job_id,
            file_path=pdf_path,
            nom_original="cours_test.pdf",
            uploaded_by=sa.id,
            force_metadata=force_meta
        )
        
        print(f"[+] Ingestion result: {result}")
        return result.get("document_id")

    except Exception as e:
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    force_ingest()
