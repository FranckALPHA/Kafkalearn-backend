from datetime import datetime, timedelta

from sqlalchemy import Column, String, Integer, Boolean, TIMESTAMP, ForeignKey, UniqueConstraint, Index, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SchoolMember(Base):
    __tablename__ = "school_members"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(8), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_ecole = Column(
        String(15),
        default="eleve",
        nullable=False,
        server_default="eleve",
    )
    invited_via = Column(String(20), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    school = relationship("School", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint("role_ecole IN ('eleve', 'admin')", name="ck_role_ecole"),
        CheckConstraint("invited_via IN ('code', 'csv', 'admin_direct')", name="ck_invited_via"),
        UniqueConstraint("school_id", "user_id", name="idx_school_user_unique"),
        Index("idx_school_member_user_active", "user_id", "is_active"),
    )

    def serialize_profile(self, mask_email: bool = True) -> dict:
        email = self.user.email if self.user else None
        if mask_email and email:
            parts = email.split("@")
            if len(parts) == 2:
                local = parts[0]
                if len(local) > 3:
                    masked_local = local[:3] + "***"
                else:
                    masked_local = "***"
                email = f"{masked_local}@{parts[1]}"

        return {
            "id": self.id,
            "school_id": self.school_id,
            "user_id": str(self.user_id),
            "role_ecole": self.role_ecole,
            "invited_via": self.invited_via,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "is_active": self.is_active,
            "user": {
                "id": str(self.user.id) if self.user else None,
                "nom": self.user.nom if self.user else None,
                "prenom": self.user.prenom if self.user else None,
                "email": email,
                "photo_url": self.user.photo_url if self.user else None,
            } if self.user else None,
            "is_actif_7j": self._is_actif_7j(),
        }

    def _is_actif_7j(self) -> bool:
        if self.updated_at is None:
            return False
        return self.updated_at > datetime.utcnow() - timedelta(days=7)
