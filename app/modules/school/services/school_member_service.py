"""
services/school_member_service.py
=================================
Service de gestion des membres d'une ecole : liste, import CSV, profil.
"""
import logging
from typing import List, Optional, Dict, Any

from redis import Redis
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.modules.school.models.school import School
from app.modules.school.models.school_member import SchoolMember
from app.modules.school.models.school_invitation_csv import SchoolInvitationCSV
from app.modules.school.services.base import SchoolBaseService
from app.modules.school.utils.csv_parser import CSVParser, CSVParseError
from app.modules.school.utils.constants import SCHOOL_MAX_CSV_LINES, SCHOOL_MAX_CSV_SIZE_MB
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)


class SchoolMemberService(SchoolBaseService):
    """Service de gestion des membres d'une ecole."""

    # ─── Lister les membres ────────────────────────────────────────────

    async def lister_membres(
        self,
        school_id: str,
        is_admin: bool,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> dict:
        """Liste les membres d'une ecole avec pagination et recherche."""
        if not is_admin:
            raise HTTPException(403, "Accès admin requis")

        query = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.is_active == True,  # noqa: E712
            )
        )

        if search:
            from app.modules.users.models.user import User as UserModel
            query = (
                query.join(UserModel, SchoolMember.user_id == UserModel.id)
                .filter(
                    UserModel.email.ilike(f"%{search}%")
                    | UserModel.prenom.ilike(f"%{search}%")
                )
            )

        total = query.count()
        members = (
            query.order_by(SchoolMember.joined_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "members": [m.serialize_profile(mask_email=not is_admin) for m in members],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        }

    # ─── Import CSV ────────────────────────────────────────────────────

    async def importer_csv(
        self,
        school_id: str,
        admin_id: str,
        file_content: bytes,
        filename: str,
    ) -> dict:
        """Importe des membres depuis un fichier CSV."""
        # Verifier que l'appelant est admin
        admin_member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == admin_id,
                SchoolMember.role_ecole == "admin",
            )
            .first()
        )
        if admin_member is None:
            raise HTTPException(403, "Accès admin requis")

        # Valider le fichier
        CSVParser.validate_file(file_content, filename)

        # Parser le CSV
        try:
            valid_rows, parse_errors = CSVParser.parse(file_content)
        except CSVParseError as e:
            raise HTTPException(400, str(e))

        if not valid_rows:
            raise HTTPException(400, "Aucune ligne valide dans le fichier CSV")

        if len(valid_rows) > SCHOOL_MAX_CSV_LINES:
            raise HTTPException(
                400, f"Limite de {SCHOOL_MAX_CSV_LINES} lignes dépassée"
            )

        # Recuperer l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school is None:
            raise HTTPException(404, "Ecole introuvable")

        stats = {"ajoutes": 0, "existants": 0, "erreurs": 0}
        erreurs_detail: List[Dict[str, Any]] = []

        for row in valid_rows:
            try:
                # Verifier si l'utilisateur existe deja
                existing_user = (
                    self.db.query(User).filter(User.email == row["email"]).first()
                )

                if existing_user:
                    # Utilisateur existant : verifier s'il est deja dans l'ecole
                    already = self._user_already_in_school(school_id, existing_user.id)
                    if already:
                        stats["existants"] += 1
                        continue

                    # Ajouter comme membre
                    self._add_member(school_id, existing_user.id, "csv")
                    stats["existants"] += 1
                else:
                    # Nouvel utilisateur : creer un compte minimal
                    new_user = self._create_invited_user(
                        email=row["email"],
                        prenom=row.get("prenom", "Élève"),
                        nom=row.get("nom", ""),
                    )
                    self.db.add(new_user)
                    self.db.flush()

                    # Ajouter comme membre
                    self._add_member(school_id, new_user.id, "csv")
                    stats["ajoutes"] += 1

                # Envoi email d'invitation en background via Celery
                try:
                    from app.modules.school.jobs.tasks import send_school_invitation_email_task
                    send_school_invitation_email_task.delay(
                        user_id=new_user.id,
                        school_name=school.nom,
                        invitation_code=school.code_invitation,
                    )
                except Exception:
                    pass  # Notification non critique
                    logger.info(
                        "Created invited user %s for school %s", new_user.email, school_id
                    )

            except Exception as e:
                stats["erreurs"] += 1
                erreurs_detail.append(
                    {"email": row["email"], "raison": str(e), "ligne": row.get("ligne")}
                )

        # Ajouter les erreurs de parsing
        for err in parse_errors:
            erreurs_detail.append(err)
            stats["erreurs"] += 1

        # Mettre a jour le compteur d'eleves actifs de l'ecole
        school.nb_eleves_actifs += stats["ajoutes"]

        # Creer l'entree de log CSV
        invitation_log = SchoolInvitationCSV(
            school_id=school_id,
            admin_id=admin_id,
            nb_lignes_total=len(valid_rows),
            nb_ajoutes=stats["ajoutes"],
            nb_existants=stats["existants"],
            nb_erreurs=stats["erreurs"],
            erreurs_detail=erreurs_detail if erreurs_detail else None,
        )
        self.db.add(invitation_log)
        self.db.commit()

        return {
            "message": "Import CSV termine",
            "stats": stats,
            "school_id": school_id,
            "total_traite": len(valid_rows),
            "log_id": invitation_log.id,
        }

    # ─── Profil d'un membre ────────────────────────────────────────────

    async def obtenir_profil_membre(
        self, school_id: str, target_user_id: str, admin_id: str
    ) -> dict:
        """Recupere le profil cognitif complet d'un membre."""
        # Verifier que l'appelant est admin
        admin_member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == admin_id,
                SchoolMember.role_ecole == "admin",
            )
            .first()
        )
        if admin_member is None:
            raise HTTPException(403, "Accès admin requis")

        # Verifier que le membre cible est dans l'ecole
        member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == target_user_id,
            )
            .first()
        )
        if member is None:
            raise HTTPException(404, "Membre introuvable dans cette ecole")

        user = member.user
        if user is None:
            raise HTTPException(404, "Utilisateur introuvable")

        return {
            "member": member.serialize_profile(mask_email=False),
            "user_profile": {
                "id": str(user.id),
                "email": user.email,
                "prenom": user.prenom,
                "nom": user.nom,
                "classe": user.classe,
                "serie": user.serie,
                "langue": user.langue,
                "streak_jours": user.streak_jours,
                "score_global": user.score_global,
                "total_sessions_etude": user.total_sessions_etude,
                "total_heures_etude": user.total_heures_etude,
                "nb_quiz_reussis": user.nb_quiz_reussis,
                "nb_quiz_echoues": user.nb_quiz_echoues,
                "niveau_estime": user.niveau_estime,
                "matiere_forte": user.matiere_forte,
                "matiere_faible": user.matiere_faible,
                "plan_effectif": user.plan_effectif,
            },
        }

    # ─── Helpers internes ──────────────────────────────────────────────

    def _user_already_in_school(self, school_id: str, user_id: str) -> bool:
        """Verifie si un utilisateur est deja membre de l'ecole."""
        existing = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == user_id,
            )
            .first()
        )
        return existing is not None

    def _add_member(
        self, school_id: str, user_id: str, invited_via: str = "csv"
    ) -> SchoolMember:
        """Ajoute un utilisateur comme membre de l'ecole."""
        member = SchoolMember(
            school_id=school_id,
            user_id=user_id,
            role_ecole="eleve",
            invited_via=invited_via,
        )
        self.db.add(member)
        return member

    def _create_invited_user(
        self, email: str, prenom: str, nom: str = ""
    ) -> User:
        """Cree un utilisateur minimal pour une invitation CSV."""
        import uuid as _uuid

        user = User(
            id=_uuid.uuid4(),
            email=email,
            prenom=prenom,
            nom=nom,
            plan_effectif="school",
            is_active=True,
            email_verified=False,
        )
        return user
