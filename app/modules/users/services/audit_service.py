"""
services/audit_service.py
=========================
Service pour la journalisation d'audit et la consultation des logs.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.modules.users.models import AuditLog
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)

VALID_SEVERITIES = {"info", "warning", "critical"}


class AuditService(BaseService):
    """Service pour consigner et consulter les journaux d'audit."""

    def log_action(
        self,
        action: str,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[UUID | str] = None,
        actor_id: Optional[UUID | str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info",
    ) -> AuditLog:
        """
        Cree une entree dans le journal d'audit.

        Args:
            action: Type d'action (login_failed, password_changed, profile_updated, etc.).
            resource: Ressource concernee (users, payments, documents, etc.).
            resource_id: Identifiant de la ressource.
            user_id: UUID de l'utilisateur cible (si applicable).
            actor_id: UUID de l'utilisateur ayant effectue l'action (si different).
            details: Contexte detaille de l'action.
            ip: Adresse IP de la requete.
            user_agent: User-Agent du navigateur.
            severity: Niveau de severite ('info', 'warning', 'critical').

        Returns:
            L'entree AuditLog creee.
        """
        if severity not in VALID_SEVERITIES:
            logger.warning(f"Invalid severity '{severity}', defaulting to 'info'.")
            severity = "info"

        # Convertir les string UUID en objets UUID si necessaire
        if isinstance(user_id, str):
            try:
                from uuid import UUID as UUIDType
                user_id = UUIDType(user_id)
            except ValueError:
                user_id = None

        if isinstance(actor_id, str):
            try:
                from uuid import UUID as UUIDType
                actor_id = UUIDType(actor_id)
            except ValueError:
                actor_id = None

        entry = AuditLog(
            user_id=user_id,
            actor_id=actor_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip,
            user_agent=user_agent,
            severity=severity,
        )
        self.db.add(entry)
        self.db.flush()

        logger.debug(
            f"Audit log: {action} on {resource} ({severity}) "
            f"for user {user_id}"
        )

        return entry

    def get_user_audit_log(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retourne les dernieres entrees d'audit pour un utilisateur.

        Args:
            user_id: UUID de l'utilisateur.
            limit: Nombre maximum d'entrees a retourner.

        Returns:
            Liste de dictionnaires contenant les entrees d'audit recentes.
        """
        entries = (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .all()
        )

        return [
            {
                "id": entry.id,
                "action": entry.action,
                "resource": entry.resource,
                "resource_id": entry.resource_id,
                "details": entry.details or {},
                "ip_address": entry.ip_address,
                "user_agent": entry.user_agent,
                "severity": entry.severity,
                "created_at": (
                    entry.created_at.isoformat() if entry.created_at else None
                ),
            }
            for entry in entries
        ]

    def get_recent_audit_events(
        self,
        severity: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retourne les evenements d'audit recents avec filtres optionnels.

        Args:
            severity: Filtrer par niveau de severite.
            action: Filtrer par type d'action.
            limit: Nombre maximum d'entrees.

        Returns:
            Liste de dictionnaires d'entrees d'audit.
        """
        query = self.db.query(AuditLog)

        if severity:
            query = query.filter(AuditLog.severity == severity)
        if action:
            query = query.filter(AuditLog.action == action)

        entries = (
            query.order_by(desc(AuditLog.created_at))
            .limit(limit)
            .all()
        )

        return [
            {
                "id": entry.id,
                "user_id": str(entry.user_id) if entry.user_id else None,
                "actor_id": str(entry.actor_id) if entry.actor_id else None,
                "action": entry.action,
                "resource": entry.resource,
                "resource_id": entry.resource_id,
                "details": entry.details or {},
                "severity": entry.severity,
                "created_at": (
                    entry.created_at.isoformat() if entry.created_at else None
                ),
            }
            for entry in entries
        ]
