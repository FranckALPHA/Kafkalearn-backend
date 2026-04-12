from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.core.config import SECRET_KEY
import os


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_superadmin(
    db: Session = Depends(get_db),
):
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    security = HTTPBearer()
    creds = await security()
    try:
        payload = decode_token(creds.credentials, expected_type="access")
        user = db.query(User).filter(User.id == payload.get("sub"), User.is_active == True).first()
        if not user or user.role not in ("superadmin", "admin"):
            raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


def verify_worker_token(x_worker_token: str = Header(None)):
    expected = os.getenv("WORKER_TOKEN", "default-worker-token")
    if x_worker_token != expected:
        raise HTTPException(status_code=403, detail="INVALID_WORKER_TOKEN")


def verify_cron_secret(x_cron_secret: str = Header(None)):
    expected = os.getenv("INGEST_CRON_SECRET", "default-cron-secret")
    if x_cron_secret != expected:
        raise HTTPException(status_code=403, detail="INVALID_CRON_SECRET")


def get_ingest_service(db: Session = Depends(get_db)):
    from app.modules.ingest.services.ingest_service import IngestService
    return IngestService(db=db)


def get_worker_coordinator(db: Session = Depends(get_db)):
    from app.modules.ingest.services.worker_coordinator_service import WorkerCoordinatorService
    return WorkerCoordinatorService(db=db)


def get_folder_scan_service(db: Session = Depends(get_db)):
    from app.modules.ingest.services.folder_scan_service import FolderScanService
    return FolderScanService(db=db)


def get_metadata_queue_service(db: Session = Depends(get_db)):
    from app.modules.ingest.services.metadata_queue_service import MetadataQueueService
    return MetadataQueueService(db=db)
