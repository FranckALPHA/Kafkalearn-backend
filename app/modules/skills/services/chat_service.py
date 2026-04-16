"""
services/chat_service.py
========================
Gestion des sessions et messages de chat.
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.skills.models import ChatSession, ChatMessage
from app.modules.skills.services.base import SkillsBaseService
from app.modules.skills.services.base_skill import SkillResult

logger = logging.getLogger(__name__)


class ChatService(SkillsBaseService):
    """Gestion des sessions de conversation et historique."""

    async def creer_session(
        self,
        user_id: str,
        titre: str = "Nouvelle session",
        matiere: Optional[str] = None,
    ) -> ChatSession:
        """Crée une nouvelle session de chat."""
        from uuid import UUID

        session = ChatSession(
            id=uuid.uuid4(),
            user_id=UUID(user_id),
            titre=titre[:255],
            matiere=matiere,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def ajouter_message_pair(
        self,
        session_id: str,
        user_content: str,
        assistant_result: SkillResult,
        skill_type: str,
        matiere: Optional[str] = None,
        niveau: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ajoute un échange complet (user + assistant) à la session."""
        from uuid import UUID

        session_uuid = UUID(session_id)

        # Message utilisateur
        user_msg = ChatMessage(
            session_id=session_uuid,
            role="user",
            content=user_content,
            matiere=matiere,
            niveau=niveau,
        )
        self.db.add(user_msg)
        self.db.flush()

        # Message assistant
        content = ""
        if assistant_result.data:
            content = (
                assistant_result.data.get("titre", "")
                or assistant_result.data.get("content", "")
                or str(assistant_result.data)
            )
        elif hasattr(assistant_result, "content"):
            content = assistant_result.content
        elif assistant_result.json_data:
            content = str(assistant_result.json_data)

        assistant_msg = ChatMessage(
            session_id=session_uuid,
            role="assistant",
            content=content[:1000],  # Limiter la longueur
            skill_utilise=skill_type,
            output_type=assistant_result.output_type,
            file_url=assistant_result.file_url,
            json_data=assistant_result.json_data,
            matiere=matiere,
            niveau=niveau,
            latence_ms=assistant_result.latence_ms,
            erreur_code=assistant_result.erreur_code,
        )
        self.db.add(assistant_msg)

        # Mettre à jour la session
        session = (
            self.db.query(ChatSession).filter(ChatSession.id == session_uuid).first()
        )
        if session:
            session.nb_messages += 2
            session.increment_generation(success=assistant_result.success)
            session.add_message_preview(user_content)
            if matiere and not session.matiere:
                session.matiere = matiere
            if skill_type and not session.skill_predominant:
                session.skill_predominant = skill_type

        self.db.commit()

        return {
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "session_id": session_id,
        }

    def get_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Récupère une session avec vérification de propriété."""
        from uuid import UUID

        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == UUID(session_id),
                ChatSession.user_id == UUID(user_id),
            )
            .first()
        )

    def get_user_sessions(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Liste les sessions d'un utilisateur."""
        from uuid import UUID

        sessions = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.user_id == UUID(user_id),
                ChatSession.is_archived == False,
            )
            .order_by(
                ChatSession.is_pinned.desc(),
                ChatSession.updated_at.desc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [s.serialize_list_item() for s in sessions]

    def get_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les messages d'une session."""
        from uuid import UUID

        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == UUID(session_id))
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [m.serialize_for_chat() for m in messages]

    def archive_session(self, session_id: str, user_id: str) -> bool:
        """Archive une session."""
        from uuid import UUID

        session = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == UUID(session_id),
                ChatSession.user_id == UUID(user_id),
            )
            .first()
        )
        if session:
            session.is_archived = True
            self.db.commit()
            return True
        return False

    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Supprime définitivement une session."""
        from uuid import UUID

        result = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == UUID(session_id),
                ChatSession.user_id == UUID(user_id),
            )
            .delete()
        )
        self.db.commit()
        return result > 0

    def update_session_title(self, session_id: str, user_id: str, titre: str) -> bool:
        """Met à jour le titre d'une session."""
        from uuid import UUID

        session = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == UUID(session_id),
                ChatSession.user_id == UUID(user_id),
            )
            .first()
        )
        if session:
            session.titre = titre[:255]
            self.db.commit()
            return True
        return False

    def pin_session(self, session_id: str, user_id: str, pinned: bool = True) -> bool:
        """Épingle ou désépingle une session."""
        from uuid import UUID

        session = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == UUID(session_id),
                ChatSession.user_id == UUID(user_id),
            )
            .first()
        )
        if session:
            session.is_pinned = pinned
            self.db.commit()
            return True
        return False
