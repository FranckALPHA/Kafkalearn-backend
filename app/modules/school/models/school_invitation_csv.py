from sqlalchemy import ForeignKey, TIMESTAMP, func
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
# UUID already imported
from sqlalchemy.orm import relationship

from app.core.database import Base


class SchoolInvitationCSV(Base):
    __tablename__ = "school_invitations_csv"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(8), ForeignKey("schools.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nb_lignes_total = Column(Integer, nullable=False)
    nb_ajoutes = Column(Integer, default=0)
    nb_existants = Column(Integer, default=0)
    nb_erreurs = Column(Integer, default=0)
    erreurs_detail = Column(JSONB, default=list, nullable=True)

    school = relationship("School")
    admin = relationship("User")
