from sqlalchemy import Column, Integer, String, Text, CheckConstraint, Index, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class WorkerJob(Base):
    __tablename__ = "worker_jobs"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type = Column(
        String(15),
        nullable=False,
    )
    status = Column(
        String(15),
        default="pending",
        nullable=False,
    )
    worker_id = Column(String(100), nullable=True)
    nb_chunks_generes = Column(Integer, nullable=True)
    erreur = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint("job_type IN ('ocr','embed','both')", name="ck_wj_job_type"),
        CheckConstraint("status IN ('pending','downloaded','processing','complete','failed')", name="ck_wj_status"),
        Index("idx_worker_job_status_created", "status", "created_at"),
        Index("idx_doc_status", "document_id", "status"),
    )

    document = relationship("Document")
