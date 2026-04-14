"""
models/ingest_job.py — ajouté au modèle existant
================================================
Modèle pour tracker les documents bloqués dans le pipeline ingest.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class IngestStepLog(Base):
    """
    Tracke chaque étape du pipeline ingest pour chaque document.
    Si une étape échoue, le document est bloqué et retryable par cron.
    """
    __tablename__ = "ingest_step_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=True, index=True)
    folder_path = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)

    # Étape actuelle : text_extract, metadata_parse, db_insert, memory_queue, done
    current_step = Column(String(30), nullable=False, default="pending")

    # Statut : pending, running, completed, blocked, failed
    step_status = Column(String(20), nullable=False, default="pending")

    # Erreur
    error_message = Column(Text, nullable=True)

    # Retry
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime, nullable=True, index=True)

    # Metadata extrait
    extracted_metadata = Column(Text, nullable=True)  # JSON
    extract_method = Column(String(20), nullable=True)  # filename, llm

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
