from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class SchoolInvitationCSV(Base, TimestampMixin):
    __tablename__ = "school_invitations_csv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(8), nullable=False)
    admin_id = Column(UUID(as_uuid=True), nullable=False)
    nb_lignes_total = Column(Integer, nullable=False)
    nb_ajoutes = Column(Integer, default=0)
    nb_existants = Column(Integer, default=0)
    nb_erreurs = Column(Integer, default=0)
    erreurs_detail = Column(JSONB, default=list, nullable=True)

    school = relationship("School")
    admin = relationship("User")
