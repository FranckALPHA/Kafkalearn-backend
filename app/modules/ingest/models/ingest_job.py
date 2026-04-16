import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    CheckConstraint,
    Index,
    TIMESTAMP,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, default=func.now(), onupdate=func.now(), nullable=False
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_type = Column(String(20), nullable=False)
    status = Column(String(15), default="pending", nullable=False)
    nb_fichiers_total = Column(Integer, default=0)
    nb_traites = Column(Integer, default=0)
    nb_succes = Column(Integer, default=0)
    nb_echecs = Column(Integer, default=0)
    nb_doublons = Column(Integer, default=0)
    erreurs_detail = Column(JSONB, default=list, nullable=True)
    dossier_scanne = Column(String(500), nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('single_file','folder_scan','csv_batch','worker_embed')",
            name="ck_ingest_job_type",
        ),
        CheckConstraint(
            "status IN ('pending','running','complete','partial','failed')",
            name="ck_ingest_job_status",
        ),
        CheckConstraint("nb_fichiers_total >= 0", name="ck_ingest_nb_fichiers_total"),
        CheckConstraint("nb_traites >= 0", name="ck_ingest_nb_traites"),
        CheckConstraint("nb_succes >= 0", name="ck_ingest_nb_succes"),
        CheckConstraint("nb_echecs >= 0", name="ck_ingest_nb_echecs"),
        CheckConstraint("nb_doublons >= 0", name="ck_ingest_nb_doublons"),
        Index("idx_ingest_job_status_created", "status", "created_at"),
        Index("idx_initiator", "initiated_by"),
    )

    initiator = relationship("User", foreign_keys=[initiated_by])

    def serialize_report(self) -> dict:
        return {
            "id": self.id,
            "initiated_by": str(self.initiated_by),
            "job_type": self.job_type,
            "status": self.status,
            "nb_fichiers_total": self.nb_fichiers_total,
            "nb_traites": self.nb_traites,
            "nb_succes": self.nb_succes,
            "nb_echecs": self.nb_echecs,
            "nb_doublons": self.nb_doublons,
            "erreurs_detail": self.erreurs_detail,
            "dossier_scanne": self.dossier_scanne,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
